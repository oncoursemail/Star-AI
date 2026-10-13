# First visible word: ten-turn offline audit

Reviewed source paths (2026-10-13):
- `star/react_shell.py` `_run_chat`: settings, chat persistence, media, then `run_task`.
- `star/desktop_core.py` `run_task`: history, knowledge, lesson recall, documentation, skills, then provider.
- `star/doc_grounding.py` `prepare_async`: off-loop documentation work.
- `star/agent.py` `execute`/`read_stream`: streamed provider and visible-delta forwarding.
- `scripts/measure_first_token.py`: separate benchmark against a **real** inference server; not run in this no-server task.
- `scripts/audit_first_word_offline.py`: deterministic fake-provider audit through the actual `run_task` path.

## Measured baseline — GitHub Linux, fake streaming provider

The pinned fake replies to **10** sequential user turns. GitHub Actions job [Offline Python checks](https://github.com/oncoursemail/Star-AI/actions/runs/38416473011/job/115362328512) ran a real-timer (`perf_counter_ns`) harness; the authoritative values below are copied from job `115362328512`. These are observations for one CI run, not CPU inference latency nor end-user time to first token on a server. Milliseconds fluctuate with host load. Prompts/answers were not changed by this instrumentation.

| Turn | Prompt chars before | Prompt chars after* | First visible ms | Settings ms | History ms | Knowledge ms | Lessons ms | Docs ms | Skills ms | Remainder ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 871 | 871 | 11.01 | .07 | .53 | .14 | .08 | .24 | .00 | 9.96 |
| 2 | 1029 | 1029 | 4.69 | .06 | .55 | .13 | .08 | .31 | .00 | 3.57 |
| 3 | 1199 | 1199 | 4.51 | .06 | .55 | .13 | .08 | .21 | .00 | 3.48 |
| 4 | 1358 | 1358 | 4.59 | .06 | .55 | .13 | .08 | .23 | .00 | 3.55 |
| 5 | 1519 | 1519 | 5.07 | .06 | .56 | .13 | .08 | .21 | .00 | 4.04 |
| 6 | 1680 | 1680 | 4.59 | .06 | .57 | .13 | .07 | .22 | .00 | 3.54 |
| 7 | 1851 | 1851 | 4.60 | .06 | .58 | .13 | .08 | .20 | .00 | 3.56 |
| 8 | 2014 | 2014 | 4.61 | .06 | .56 | .12 | .08 | .19 | .00 | 3.60 |
| 9 | 2187 | 2187 | 4.64 | .06 | .60 | .13 | .08 | .22 | .00 | 3.56 |
| 10 | 2346 | 2346 | 4.67 | .06 | .56 | .15 | .08 | .21 | .00 | 3.62 |

*“After” is the same unmodified prompt layout as “before” because this PR is **instrumentation only**; it does not include or verify three speed optimizations. Do not treat identical character counts as measured post-optimization results.

## Three next areas, not three validated fixes

1. **Unattributed remainder** (~3.5–4.0 ms steady-state, 9.96 ms on cold first turn). This includes request assembly, lifecycle setup and fake provider callbacks; it is not independently established as avoidable. Add more spans inside `run_task` before optimizing it.
2. **History snapshot** (~0.53–0.60 ms): SQLite conversation read plus checkpoint shaping on every turn. Investigate a cache **only** with exact prompt/history-byte equivalence, complete-turn boundaries and explicit invalidation on chat/lesson changes.
3. **Documentation dispatch** (~0.19–0.31 ms): the fast route with no grounding still goes through `asyncio.to_thread(prepare)`. A possible early no-grounding return could avoid thread dispatch; prove equality on explicit follow-up grounding and error paths before enabling.

Knowledge lookup measured ~0.12–0.15 ms, lesson recall ~0.07–0.08 ms and Settings.load ~0.06–0.07 ms. These are not the top three in this run. Skill selection was disabled by the fast route and was **not benchmarked**; enable explicit skill selection in a future scenario before inferring its cost.

## Certainty and recommendation

**Certain:** All ten fake-model runs reached the first visible `assistant_delta`, recorded prompt lengths and stage durations, and yielded answers in the existing `run_task` path. Linux CI passed 5,899 Python tests on the measured commit. The instrumentation changes neither provider requests nor prompt assembly. The cached-first-token layout tests already exist in `tests/test_first_token.py` and `tests/test_first_token_review.py`.

**Uncertain:** CPU-server true time to first token, whether the remainder is avoidable, a gain from caching/history refactoring, and the effect of full research/agent mode. Separate hosted and llama.cpp measurements are needed.

**Recommendation and smallest next step:** First instrument the 3.5 ms remainder with distinct spans for provider setup, prompt assembly and auxiliary database writes. Then implement one guarded optimization (start with the proven no-grounding branch, with fake-provider prompt/answer equality), rerun exactly these ten prompts before/after in CI, and record signed deltas. Do **not** claim a 3-cost speed gain or alter defaults without this proof.
