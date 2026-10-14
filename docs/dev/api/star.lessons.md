# `star.lessons`

Source: `star/lessons.py`

Lessons: what STAR learns from use, kept with provenance and used in later answers.

The model's weights never change. "Learning" here is a loop over local records:

  capture   after each turn, with regular expressions and a few SQLite rows (no model call):
            the owner's stated preferences and corrections, a retry after a failure, a Luau
            check that failed and was repaired, a documentation search that found nothing,
            and thumbs up/down on an answer;
  trust     a durable statement in the OWNER'S OWN WORDS is accepted at once for that project
            (unless the owner chose "review everything"); everything inferred, summarised by a
            model, or taken from tool output, web pages, documentation or files is a CANDIDATE
            and is never given to the model as knowledge until the owner approves it;
  use       accepted lessons are recalled into the next turns of the same project through the
            reviewed-knowledge section of the turn context, ranked, de-duplicated and bounded.

A lesson is an ordinary row of `notes` (star/knowledge.py) whose `status` is set. `reviewed`
remains the single flag every reader checks, and this module is the only writer that sets it
for a lesson. A lesson is text and nothing else: no code path reads one to change a setting
or a permission, and text that asks for either, or that carries a key or password, is refused.

## Constants

`STATUSES`, `OWNER`, `MANUAL`, `CONTEXT`, `INFERRED`, `SOURCE_TYPES`, `DIGESTIBLE`, `RECALLED_KINDS`, `STANDING_KINDS`, `MAX_TEXT`, `MAX_EVIDENCE`, `RECALL_SCAN`, `LESSONS_HEADING`, `RECALL_CLIP`, `LINE_OVERHEAD`, `RECALL_QUICK`, `RECALL_FULL`, `LIST_WINDOW`, `MACHINE_MADE`, `MAX_MACHINE_WAITING`, `TYPED_SENTENCES`, `TYPED_CHARS`, `LESSON_ACTIONS`, `REVIEW_OPERATIONS`

## Classes

### `LessonRefused`(ValueError)

Text that may not become a lesson. `reason` is secret | permission | size.

#### `__init__`

```python
def __init__(self, reason: str, message: str)
```

### `Statement`

### `Lesson`

#### `public`

```python
def public(self) -> dict
```

What the review page may show. Nothing here is a secret: text and evidence were filtered on entry.

### `Captured`

### `LessonStore`

Lesson records on top of the project knowledge database.

`record(project, kind)` is called for `lesson_captured`, `lesson_accepted` and
`lesson_used`, so the local analytics counts come from real events only.

#### `__init__`

```python
def __init__(self, home: Path | None=None, *, knowledge: KnowledgeStore | None=None, record=None)
```

#### `close`

```python
def close(self) -> None
```

#### `get`

```python
def get(self, project: str, lesson_id: int) -> Lesson
```

#### `list`

```python
def list(self, project: str, status: str | None=None, *, limit: int=200) -> list[Lesson]
```

#### `counts`

```python
def counts(self, project: str) -> dict
```

Lessons of this project by status, plus how often accepted ones were placed in a turn.

#### `capture_owner`

```python
def capture_owner(self, *, project: str, kind: str, text: str, message: str, source: str, evidence: str='', auto_accept: bool=True) -> Captured
```

A durable statement the owner typed. `text` must be the owner's own words: it has to
appear in `message`, the chat message it was taken from, or nothing is stored as theirs.

#### `capture_inferred`

```python
def capture_inferred(self, *, project: str, kind: str, text: str, source_type: str, source: str, evidence: str='') -> Captured
```

Anything STAR worked out, or took from a tool, a page, the documentation or a file.
Always a candidate: there is no argument that makes this path trusted.

#### `approve`

```python
def approve(self, project: str, lesson_id: int, *, human_approved: bool=False, text: str | None=None, kind: str | None=None, keep_both: bool=False) -> Lesson
```

The owner accepts a lesson, optionally with their own wording. Restoring a replaced
lesson passes keep_both so it does not in turn retire the newer one.

#### `edit`

```python
def edit(self, project: str, lesson_id: int, *, human_approved: bool=False, text: str, kind: str | None=None) -> Lesson
```

Change the wording. An accepted lesson stays accepted (the owner wrote the new words);
a candidate stays a candidate until it is approved.

#### `reject`

```python
def reject(self, project: str, lesson_id: int, *, human_approved: bool=False) -> Lesson
```

Stop using a lesson and keep the record, so the same capture is not offered again.

#### `delete`

```python
def delete(self, project: str, lesson_id: int, *, human_approved: bool=False) -> None
```

Remove a lesson and its use count for good.

#### `withdraw`

```python
def withdraw(self, project: str, source_type: str, source: str) -> int
```

Drop a still-unreviewed capture whose signal was taken back (a removed thumb).

#### `export`

```python
def export(self, project: str) -> dict
```

Every lesson of one project, with provenance, as plain data for the owner to keep.

#### `page`

```python
def page(self, project: str) -> list[Lesson]
```

What the review page shows: the newest lessons of every status (LIST_WINDOW each),
newest first. Loading "the newest 200 of anything" would let waiting notes push an
accepted lesson off the page while it is still used in answers.

#### `recall`

```python
def recall(self, project: str, prompt: str, *, limit: int=6, max_chars: int=1400) -> list[Lesson]
```

Accepted lessons of this project for one turn: those about the prompt first, then the
standing preferences and corrections, newest first, without repeats, within a budget.

#### `mark_used`

```python
def mark_used(self, project: str, lessons: list[Lesson]) -> None
```

Count one use for each lesson that was placed in the context of an answered turn.

## Functions

### `has_secret`

```python
def has_secret(text: str) -> bool
```

True when the text carries something that looks like a key, token or password.

### `grants_permission`

```python
def grants_permission(text: str) -> bool
```

True when the text reads as an attempt to widen what STAR may do or to change its settings.

### `redact`

```python
def redact(text: str, limit: int=MAX_EVIDENCE) -> str
```

Evidence shown at review: bounded, with anything key-like removed.

### `check_lesson_text`

```python
def check_lesson_text(text, *, limit: int=MAX_TEXT) -> str
```

Return the cleaned text of a lesson, or raise LessonRefused.

### `subject_tokens`

```python
def subject_tokens(text: str) -> frozenset[str]
```

The words a lesson is about: identifiers and nouns, without polarity or filler.

### `subject_key`

```python
def subject_key(text: str) -> str
```

### `same_subject`

```python
def same_subject(first: frozenset[str], second: frozenset[str]) -> bool
```

Two lessons are about the same thing when at least three quarters of the shorter one's
subject words are shared, and those are at least half of the longer one's. Deliberately
strict: a lesson retired by mistake stops being used, while two lessons that overlap are
both visible on the review page. The second condition keeps a short remark ("I prefer
gold accents") from retiring a long decision that only mentions the same two words.

### `own_words`

```python
def own_words(message: str) -> str
```

The part of a message the owner wrote as prose: no code fences, no quoted lines.

### `reads_as_typed`

```python
def reads_as_typed(message: str) -> bool
```

True when a chat message is short enough for its statements to be trusted as typed.
Code fences and quoted lines do not count: "fix this" above a long script is still short.

### `owner_statements`

```python
def owner_statements(message: str, *, after_answer: bool=False) -> list[Statement]
```

Stated preferences and corrections in one chat message. Conservative on purpose:
a missed statement costs nothing, a wrong one would follow the owner into later chats.

### `describe_source`

```python
def describe_source(source_type: str, source: str) -> str
```

One plain sentence about where a lesson came from.

### `context_lines`

```python
def context_lines(lessons: list[Lesson]) -> str
```

The lines a turn carries, one lesson per line (a decision typed on several lines is
joined). The id is the provenance: the review page shows where each came from.

### `guard_sections`

```python
def guard_sections(sections) -> list[tuple[str, str]]
```

Only the section written by this module may look like lessons.

The heading asks the model to apply what follows, which no other reference text is
allowed to ask. A stored note, a web result or a documentation passage that repeats the
heading or a "[#12 preference]" line would borrow that standing, so both are rewritten
in every other section. The text itself stays, as the reference material it is.

### `capture_turn`

```python
def capture_turn(store: LessonStore, *, project: str, chat_id: str | None, owner_text: str, turn: dict | None=None, grounding=None, messages=None, auto_accept: bool=True) -> dict
```

Record what one finished turn taught. Regular expressions and a few rows; never a model call.

`turn` is Conversations.turn_context(): the message being answered and the turn before it.
Returns counts for the interface: {'accepted': n, 'candidates': n, 'refused': n, 'replaced': n,
'ids': [...]}, plus 'not_kept': n when statements of the owner were refused by the content rules.

### `record_feedback`

```python
def record_feedback(store: LessonStore, *, project: str, chat_id: str, message_id: int, value: str, question: str, answer: str) -> Captured | None
```

A thumb on an answer becomes a candidate (the lesson would be drawn from the model's
own answer, so it is inferred). Changing or removing the thumb withdraws an unreviewed one.

### `record_correction`

```python
def record_correction(home: Path, store: LessonStore, *, project: str, chat_id: str, message_id: int, value: str, correction: str, question: str, answer: str) -> dict | None
```

Thumbs-down plus the owner's correction (W8): a regression-test candidate (star/corrections.py) and a lesson
candidate in the owner's words, both waiting for review. Any other thumb withdraws an unreviewed one.

### `learning_status`

```python
def learning_status(home: Path, project: str) -> dict
```

Counts for the interface (pending badge, review page). Zeroes when nothing was ever stored.

### `write_export`

```python
def write_export(destination: Path, data: dict) -> dict
```

Save an export where the owner chose. Returns a nonsecret receipt for the interface.

### `handle_action`

```python
def handle_action(home: Path, project: str, action: str, body: dict) -> dict
```

The lesson actions of the desktop bridge. Every change is an explicit owner action from
the interface; none of them can touch settings, permissions or another project.

### `import_lessons`

```python
def import_lessons(path: Path, *, home: Path | None=None) -> dict
```

Import a star-lessons-v1 file as candidates, without overwriting local records.

### `import_bundled_lessons`

```python
def import_bundled_lessons(home: Path, version: str, *, enabled: bool=False, bundle: Path | None=None) -> dict
```

Opt-in once per app version; all new records still need review.

### `main`

```python
def main(argv=None) -> int
```

CLI: python -m star.lessons import FILE [--home DATA_FOLDER].
