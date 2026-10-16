# prefill-while-typing-20261016 (#156, claude): STAR starts thinking while you type

Branch `star/prefill-while-typing-20261016` (worktree `worktrees/prefill-typing`, from origin/star/next 48c21bc8).
Setting: Settings > Answers > **Start thinking while I type** (`prefill_while_typing`, off by default).

## What it does
- Interface (`frontend/src/draftWarm.ts`, used in Desktop.tsx): 600 ms after the last keystroke, if the trimmed draft
  has at least 12 characters and grew by at least 8 since the last one sent (any edit counts), it sends
  `warmDraft {prompt, mode, research}`. Not while a turn runs, in image/team mode, or with attachments.
- Host (`react_shell.py` `warmDraft`): answers at once; `DraftWarmer` (star/prefill_warm.py) runs at most one draft
  request at a time and keeps only the newest pending one. Every real request (WARM_UP_STOPPERS: sendMessage, ...)
  cancels it. The "session capabilities" line is put in front exactly as the turn does (`SESSION_CAPABILITIES`).
- Request (`prefill_warm.warm_draft`): the turn's own start (warmup.request_builder: system message, memory,
  earlier turns) + the draft as the user's words, on the model the router picks for the draft and on the chat's
  slot. Tool turns are warmed only with the tool list the chat last sent to that model (else skipped).
- **Why raw text, not a chat request** (measured, see below): STAR's models are hybrid; llama.cpp reuses a cached
  prompt only up to a saved checkpoint (start of the last user message, and 4 / 4+ubatch tokens before the end of
  a prompt; server-context.cpp in the RAMForge tree). A chat request for the draft ends with `<|im_end|>...
  assistant\n<think>...`, so its end checkpoint lies after the draft and the real turn fell back to the start of the
  message: first version measured **zero** reuse (tokens read after Enter identical on/off). Now the draft is
  rendered by the server's template (`POST /apply-template`), cut right after the owner's words and sent to
  `/v1/completions` (1 token, cache_prompt, same id_slot): its checkpoint lands 4 tokens before the draft's end.
- Budget: STAR Server is asked which slots of that model are generating (look_for_busy_slots). All busy: nothing.
  Some busy: only drafts <= 1,600 chars, into the idle slot (the turn moves there too). Cloud: never.
- Own warm-ups are marked (`providers.own_warm_started/ended`, also used by the post-answer warm-up `_prime`): a
  cancelled warm-up is still read to the end of its batch by the server, and the turn's busy-slot check (issue 118)
  used to take it for another client and moved the chat to the other slot, losing the whole cache (measured). The
  mark lasts while the request runs and 15 s after a cancel.
- Use my GPU: when the PC model is loaded and free, a draft for star-fast goes to the PC (`GpuHelper.warm_begin/
  warm_end`, no lease, never starts the model). The watchdog ignores the card's load while a draft runs (it stopped
  the PC model in the first GPU run: "another program is using the graphics card").
- Answer text: unchanged by construction (the draft request only fills the prompt cache; the turn's own request is
  byte-identical to before). Tests: tests/test_prefill_warm.py (16), frontend/src/draft-warm.test.tsx (3).

## Measurements (2026-10-16 03:20-04:40Z)
Harness (scratchpad, not in the repo): the app's own request builders; per turn first the post-answer warm-up state,
then OFF = the turn's model request at once, ON = the owner "types" it in real time (6 chars/s, 0.8 s pause after
each sentence, code pasted at once), the real DraftWarmer/warm_draft fire on each 600 ms pause, Enter 0.3 s after
the last character (so the last words are never warmed), Enter cancels the draft, then the same turn request.
TTFT = time to the first token of that request (run_task's retrieval/knowledge steps are identical in both and not
included). Server 1 under the quiet lock, but NOT clean: another agent's apprentice job (gen_answers on star-fast,
QLoRA on the PC GPU) ignored the lock until ~04:15Z, star-fast slot 1 hung 03:13-~04:15Z (msg #321).
"6k" chats: 27 earlier turns, the app's 26,000-character window sends ~4.2k tokens of them.

## Numbers (first-token time of the turn's model request; tokens the server read after Enter)
| where | turns | off -> on (median) | tokens read after Enter |
|---|---|---|---|
| server, star-fast, pasted script + question (590-604 chars), short / 2k / 4.2k context | 3 | 5.85 / 5.93 / 6.29 s -> 2.51 / 2.89 / 2.65 s (**-3.0 to -3.6 s**) | 252 -> 89 |
| server, star-fast, typed question (58-105 chars) | 3 | 3.12 -> 2.62 s (one pair -0.10 s) | 104-115 -> 89 |
| server, star-voice, typed question, short context | 5 | 1.94 -> 1.66 s | 112 -> 97 |
| server, star-voice, typed, 2k context | 4 | 2.56 -> 1.95 s | 102 -> 92 |
| server, star-voice, typed, 4.2k context | 2 | 2.33 -> 2.44 s (no gain: the cancelled last draft was still being read) | 104 -> 92 |
| **server, all 17 turns** | 17 | **median -0.41 s, mean -0.93 s** | |
| server, same 11 star-voice turns after an unrelated prompt used the slot | 11 | median -0.16 s (RAM prompt cache brings the history back anyway) | |
| Use my GPU (PC 3060 Ti), star-fast turns | 5 | median -0.32 s, mean -1.04 s; paste 6.02 -> 1.78 s (first PC paste: pages), 2k/4.2k paste 2.16 -> 2.13 / 1.99 -> 1.55 s, typed 2.09 -> 1.94 / 2.00 -> 1.68 s | 104-253 -> 89 |

Of the 20 scripted turns, 4 are tool turns (Studio/workspace wording): not warmed by design when the chat has no
earlier tool request for that model (they are warmed after one). Raw rows: scratchpad server4/fast/cold/gpu4.jsonl.

## Not done / limits
- The ~90-token tail after the owner's words (the STAR CONTEXT block with the time line) is still read after Enter;
  on short messages it is most of the remaining first-token time (about 1.6 s of 1.7 s on star-voice). Next idea:
  shorten that block for plain chat, or warm it when the owner pauses on a finished message.
- With the server's RAM prompt cache a chat's history comes back in well under a second even after another prompt
  used its slot (measured "cold" case = same as warm), so the gain is the owner's own words, not the history.
- Real-window check (clicking in the Qt app) not done; the interface part is covered by vitest with the fake bridge.

## Status log
- 02:05Z claimed #156; read STATE, rules, speed-round3, gpu-helper-switch, chat path.
- 02:20Z probes: cancel keeps 1,927/2,443 tokens; max_tokens 0 still generates 1 token (kept max_tokens 1).
- 02:30-03:50Z first harness runs: contamination (apprentice job, another claude's lock 02:39Z, stuck slot), found
  the own-warm slot move and the checkpoint problem; fixed both; 03:56Z msg #321.
- 04:00-04:40Z measurements with the fixed code (server, GPU).
