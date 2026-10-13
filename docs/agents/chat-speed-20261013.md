# chat-speed-20261013 (wave 2026-10-13, board item #79)

Goal: everyday chat (Discord + desktop) much faster. Measure where a short Discord reply's minute goes, then fast path,
prompt/cache fixes, Discord streaming, interactive priority. Lead addendum: STAR should almost never re-read text
(slot/prefix reuse, slot save/restore, tool search, byte-stable prefix, rolling summaries); report turn-2+ first token.
Branch star/chat-speed-20261013 (worktree worktrees/chat-speed, from origin/star/next 6b953ad).

## Where the minute went (recorded server trace, owner's two Discord messages, 18:00-18:02Z)

Bot process started 17:58:49Z (worktrees/discord-finish). Both messages went to **star-fast** (port of star-fast in the
router log), because the bot never asked the server for its model list, so `quick_model()` fell back to the primary.

| | arrived | got a slot | queue | prompt read | answer | total |
|---|---|---|---|---|---|---|
| message 1 | 18:00:10 | 18:01:17 | **67 s** | 154 tok, 3.3 s (46 tok/s) | 14 tok, 3.1 s (4.3 tok/s) | ~73 s |
| message 2 | 18:01:31 | 18:02:07 | **36 s** | 19 tok (rest cached), 1.3 s | 33 tok, 5.0 s (6.4 tok/s) | ~43 s |

- ~90% of the time was **queueing**: both star-fast slots were held by the release eval (creation + holdout in
  parallel; each answer 1,200-1,400 prompt tokens + 700-1,600 generated tokens = 3-5 minutes per request).
- Thinking: **not** a factor. star-fast runs with `reasoning = off` (live models.ini); 14/33 tokens generated.
- Prompt size: **not** a factor for Discord: system prompt + message = 154 tokens, no tools, no docs.
- Prompt reuse already worked on star-fast: message 2 landed on the *other* slot and read only 19 new tokens (RAM prompt
  cache restore). Generation was slow (4-6 tok/s instead of 10.5) because the CPU was shared with the two eval streams.
- Discord overhead: negligible (no measurable gap; the bot answers in one piece, so the owner saw nothing for ~70 s).

## Changes (branch star/chat-speed-20261013)

1. Discord fast path (`star/discord_bot/brain.py`): asks the STAR Server once for its model list (`server_roles.discover`),
   then routes with STAR's own router (`brain_router.select_route`, Auto mode; reuse, no new rules): plain chat ->
   **star-voice/star-quick** (own process + own 2 slots, never queues behind star-fast work), `enable_thinking: false`,
   600-token budget; Roblox/code/docs/research -> star-fast (1,400 tokens, 300 s timeout so a queued answer is not cut at 75 s).
   If star-fast's slots are all busy (one 0.4 s `/slots` probe), general "reasoning" chat moves to the quick model;
   Roblox/code stays and the owner sees "queued behind background work". Quick model missing -> falls back to star-fast.
   No `id_slot` (a pinned request waits for its slot even while another is free; the RAM cache restores from any slot).
   Byte-identical system prompt. `live` hook for the clock/web agent: per-turn text at the very end of the user turn.
2. Streaming (`star/discord_bot/streaming.py` LiveReply, wired in `bot.py`): DM answers are posted at the first token and
   edited at most every 1.2 s (slash `/ask`: the deferred "thinking" message is edited every 1.5 s, then finished in
   place with the buttons). A refused edit switches the live view off and the full answer is sent normally.
3. History trimming in blocks (`core.SessionMemory`): the window used to slide by one exchange per turn after 6 turns,
   which changed the start of every request (full re-read every turn). Now it cuts back to half once, so the next few
   turns share their start.
4. star-voice chat template (`server/brain/templates/mellum-keep-empty-think.jinja`, `models.ini [star-voice]
   chat-template-file`, apply.sh ships templates). Found while measuring: Mellum's template drops the empty think block
   from earlier answers, while the generation prompt (thinking off) ends with one -> every follow-up re-read the previous
   answer (turn 2: 83 tokens read, turn 3: 195). Client-side fixes do not work (llama.cpp strips think tags from input
   content before the template). The fixed template was rendered by the real b11541 engine (temporary llama-server on
   127.0.0.1:8095 with the 0.6B reranker GGUF, /apply-template, removed): turn-2 prompt now starts with
   gen-prompt + answer (PREFIX OK: True). `apply.sh check` passed 18:4xZ. NOT APPLIED: needs a star-brain restart.
   Also copied the live-only `[star-embed-ft1]` section into the repo models.ini so apply.sh does not drop it.
5. Reserved interactive slot: PROPOSED only (comment in models.ini `[star-fast]`): `parallel = 3`, `ctx-size = 98304`,
   plus the convention that batch clients (evals, night school) send at most two star-fast requests at a time. llama.cpp
   has no priority, so this is the only way chat never waits for two long answers. Needs a measurement of 3 parallel
   streams first; release agent applies restarts.

## Measurements

Before = the recorded trace above (owner's messages, star-fast, eval running).
After (18:12:47-18:14:27Z, new code from the PC, light single requests, eval still holding both star-fast slots,
night school on HOLD): `scratchpad/measure_discord.py` = DiscordBrain with streaming, 3-turn casual chat.

| turn | model | first text | total | server: prompt read | generated |
|---|---|---|---|---|---|
| 1 "hey star, how's it going?" | star-voice | 12.2 s | 22.6 s | 162 tok @ 17 tok/s | 42 @ 3.9 tok/s |
| 2 "cool, what can you help me with?" | star-voice | 8.2 s | 54.4 s | 83 tok @ 10 tok/s | 160 @ 3.4 tok/s |
| 3 "thanks!" | star-voice | 9.6 s | 22.9 s | 195 tok @ 20 tok/s | 51 @ 3.8 tok/s |

- No queue any more (the old path waited 36-67 s for a slot before the first token): first text 8-12 s vs 43-73 s for
  the whole (unstreamed) answer. With streaming the owner sees text at that point.
- Still slow in absolute terms because the CPU is saturated by the eval: star-voice reads 10-20 tok/s instead of 109 and
  writes 3.4-3.9 tok/s instead of 25. On an idle box the same requests should take ~1 s to first text
  (star-voice idle: first token 0.6-0.9 s, brain-performance-20261013.md); NOT measured today (eval until ~20:00Z).
- Turns 2-3 re-read the previous answer (83/195 tokens) = the template bug of change 4; after the template is applied
  only the new message should be read (~20-35 tokens). To verify after the restart: rerun measure_discord.py and check
  `prompt eval time` tokens per turn in `journalctl -u star-brain`.

## Lead addendum: "never re-read the same text" (status)

- (1) Prefix reuse: desktop already has it (2026-10-10 first-token work: stable system message, per-turn context last,
  `cache_prompt`, `id_slot` per conversation + issue-118 busy probe, warm-up; turn 2-5 first token 1.2-1.6 s idle).
  Discord: cache_prompt + RAM cache restore (measured 19-token turn 2 on star-fast). Gap found and fixed: star-voice
  template (change 4) and Discord's sliding history (change 3). 24 GB cache-ram is live.
- (2) Slot save/restore: TODO (check b11541 router support next).
- (3) Tool search: TODO (measure desktop tool-schema tokens; note the Qwen template renders tools BEFORE the system
  text, so changing the tool list per turn invalidates the whole prefix; the desktop already keeps a sticky tool list).
- (4) Byte-stable prefix: desktop done (first-token.md); Discord system prompt is a constant; clock/web agent puts the
  time at the end of the user turn (coordinated, `live` hook included).
- (5) Rolling summaries: desktop has compaction checkpoints (conversation_memory.py); Discord keeps 3-6 short turns in RAM.

## Status log
- 18:05Z started, claimed (#79). Read brief, brain-performance notes, discord-finish notes, first-token.md.
- 18:10Z trace analysis (journalctl on server 1, read only): breakdown above.
- 18:12Z live after-measurement (3 light requests on star-voice).
- 18:20-18:40Z template bug found, fixed template verified on the real engine (temp server, removed), apply.sh check ok.
- Tests: tests/test_discord_chat_speed.py (14) + updated test_discord_bot.py; discord venv 51 passed / 1 skipped;
  full suite (audit venv) 6212 passed / 240 skipped (before the last two small test additions).
