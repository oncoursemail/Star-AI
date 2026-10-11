# How STAR learns from use

STAR's model is not retrained on this hardware. "Learning" means STAR keeps **lessons**: short, local,
project-scoped notes with a source. It records them after a turn, decides by fixed rules which ones are
trusted, and puts the trusted ones into later answers of the same project. Nothing leaves the PC, and
every lesson can be read, changed, rejected, deleted and exported.

Code: `star/lessons.py` (records, rules, recall), `star/lesson_digest.py` (optional background
summary), `star/desktop_core.py` (`run_task` recall and capture), `star/react_shell.py` (bridge
actions), `frontend/src/LearningPanel.tsx` (review page). Tests: `tests/test_learning_loop.py`,
`frontend/src/learning.test.tsx`. Demo: `python scripts/learning_loop_demo.py`.

## What is captured

After every chat turn (answered, failed or stopped), with regular expressions and a few SQLite rows.
No model is called for this.

| Signal | Example | Lesson kind | Starts as |
|---|---|---|---|
| A stated preference | "Always use camelCase", "From now on ...", "I prefer ..." | preference | accepted (your words) |
| A correction that stands on its own | "No, use task.wait instead of wait." | correction | accepted (your words) |
| A remark that only makes sense next to one answer | "No, make it blue", "I prefer the second option" | correction / preference | candidate |
| A retry after a failure | the same message sent again after a failed turn | pitfall | candidate |
| A Luau check that failed and was repaired | the diagnostic and the changed lines | pitfall | candidate |
| A documentation search that found nothing | the query | fact | candidate |
| A thumb on an answer | thumbs up / down under an answer | fact / pitfall | candidate |

Not captured: text inside code fences or quoted lines, messages over 4,000 characters (a paste is
material, not an instruction), questions, voice-call transcripts, team runs and image prompts.

Each lesson stores: project, text, kind (`preference | correction | pitfall | fact`), status
(`candidate | accepted | rejected | superseded | merged`), `source_type`, `source` (for example
`chat:<chat id>#<message id>` or `luau-check:<chat>#<message>/block1`), a redacted `evidence` excerpt,
`created` and `updated`.

## Trust rules (enforced in code, covered by tests)

1. **Your own words are accepted automatically** for the project they were said in. The text must
   literally appear in the chat message it was taken from (`LessonStore.capture_owner` refuses anything
   else). The setting "Accept my own corrections automatically" (`learning_auto_accept`, default on)
   switches this to "review everything". Only a message short enough to be a typed instruction
   counts: at most 4 sentences and 500 characters outside code fences and quoted lines
   (`reads_as_typed`). In a longer message, which is usually pasted material with a question about
   it, the same sentences are kept as candidates and wait for review. A short paste still looks
   like your own words; "review everything" is the setting for that.
2. **Everything else is a candidate**: anything inferred, summarised by a model, or taken from tool
   output, web pages, documentation or files. `LessonStore.capture_inferred` has no argument that makes a
   lesson trusted. A candidate is never placed in a prompt until you approve it.
3. **Approval is an explicit action**: `approve`, `edit`, `reject` and `delete` require
   `human_approved=True`, which only the review buttons send.
4. **A lesson is text and nothing else.** No code path reads a lesson to change a setting or a
   permission. Text that reads as a grant ("you may edit files", "without asking", "enable studio
   edits", "ignore the rules") or names a setting is refused, and so is anything that looks like a key,
   token or password. Evidence excerpts are redacted the same way.

The single flag every reader checks is still `notes.reviewed`; `star/lessons.py` is the only writer that
sets it for a lesson.

## How lessons are used

`run_task` recalls accepted lessons of the current project into one turn section,
`OWNER'S LESSONS FOR THIS PROJECT`, next to the existing reviewed notes. It goes through
`turn_sections`, so it is appended to the final user turn and the system message stays byte-stable.

- Scope: the project of the turn. Another project never sees them.
- Ranking: lessons that share subject words with the prompt first, then standing preferences,
  corrections and approved decisions, newest first. Pitfalls and facts are only recalled when the
  prompt is about them.
- Supersession: accepting a lesson retires older accepted lessons on the same subject (at least three
  quarters of the shorter one's subject words shared, and at least two). The rule is strict on purpose:
  "use teal accents for the lobby interface" replaces "use gold accents for the lobby interface", while
  "put UI logic in LocalScripts" does not replace "never put game logic in LocalScripts". The chat says
  when a new lesson replaced an older one; the older record is kept under "Set aside" and can be restored
  next to the new one.
- Budget: at most 3 lessons / 360 characters for a quick answer and 8 lessons / 1,200 characters
  otherwise, 240 characters per lesson. The block is read on every turn and is not in the server's
  prompt cache, so on a CPU server each lesson costs time before the first token.
- A lesson is recorded after the answer, so the turn that states it is sent exactly as typed.

## Optional background summary

Some captures are rough ("An answer was marked not helpful"). When at least three are waiting, and
after a turn and its cache warm-up have finished, STAR may send one small request to the fast model
(`star-quick` on a STAR Server, otherwise the configured fast or main model) asking it to reword them.

- Its output is always a candidate (`source_type = summary`) and passes the same content rules.
- Raw captures it used become `merged`; one you already reviewed is left alone.
- One request per run, 6 captures, 420 output tokens, 120 seconds; cancelled by any real request;
  after a failed run automatic runs pause for 15 minutes.
- Off for hosted providers unless `learning_digest_cloud` is turned on, because the captures quote your
  chats. `learning_digest` turns it off entirely. "Summarise raw notes" on the review page runs it once
  on request.

## Review page

Projects, "What STAR has learned": lessons by status (Waiting, Accepted, Set aside) with the pending
count, where each came from, approve / edit / reject / delete (delete asks twice) / restore, export to a
JSON file you choose, and the three settings. Thumbs up and down sit under each stored answer.

Bridge actions: `listLessons`, `reviewLesson {op, id, approved, text?}`, `exportLessons`,
`messageFeedback {messageId, value}`, `digestLessons`; `rememberDecision` still saves a decision you type.

## Counts

Analytics shows counted local events only: lessons captured, lessons accepted, answered turns that had
accepted lessons in their context (the count says a lesson was *in the prompt*, not that the model
followed it), and how many are waiting now.

## Storage and migration

Additive only. `knowledge.sqlite3`: seven nullable columns on `notes` (`status`, `source_type`,
`updated`, `supersedes_id`, `subject`, `evidence`, `merged_into`), table `lesson_use`, table
`store_meta`; decisions approved before this version are labelled as accepted or superseded lessons
without changing what is trusted. `conversations.sqlite3`: table `message_feedback`.
`analytics.sqlite3`: three new event kinds. A database written by this version still opens in the
previous one.
