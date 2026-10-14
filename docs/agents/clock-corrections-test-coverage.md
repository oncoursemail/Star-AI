# Clock and owner-correction regression coverage — 2026-10-13

## Existing tests inspected (GitHub source, no coverage runner)

`tests/test_clock.py` already invoked
`observe_server_date`, `server_offset`, `forget_server_clock`,
`now_line`, `wants_clock`, `run_clock`, and `tool_result`.
It did **not directly call** `local_now`, `sent_line`,
`resolve_zone`, or construct/expect `ClockError` by name.

`tests/test_corrections.py` already executed `CorrectionStore`,
`write_suite`, and `handle_action`, plus application/Discord integrations.
It did **not directly call** `scrub`, `cause_for`, `check_stub`,
or `task_for`.

The new `tests/test_clock_and_corrections_edges.py` explicitly invokes all
**8 direct-path gaps**, and also adds adversarial cases to the 10 previously
exercised APIs/classes. This is a source-based inspection of those two existing
test modules, **not an instrumentation-derived coverage percentage**.

## Deterministic witnesses / mutation rationale

| Test group | What it proves; one plausible mutation that makes it fail |
| --- | --- |
| local_now | Injected aware and naive time works; discarding the injected `now` breaks the equality |
| observe_server_date / server_offset / forget_server_clock | Three server skew values, malformed dates, monotonic TTL and clear; accepting a malformed header or altering TTL breaks a witness |
| now_line / sent_line | Fixed instant, skew threshold and persisted timestamp; changing threshold or replay parsing breaks a comparison |
| resolve_zone / ClockError | UTC aliases, fixed positive/negative offsets, bad offsets, empty/local and IANA lower-case names; removing normalization or range checks breaks fixtures |
| DST transition | New York switches from UTC-05:00 to UTC-04:00 around 2026-03-08 07:00 UTC; fixed-offset handling instead of ZoneInfo fails |
| wants_clock | Three clock intents and three excluded prompts; widening the regular expression to ordinary chat fails |
| run_clock / tool_result | now, convert, add and diff plus wrong types, oversized zone lists and a forced zone-provider failure; allowing an invalid action or swallowing its error fails |
| scrub | Newline normalization, length cap, wrong input type and constructed private-address replacement; removing the limit or redaction fails |
| cause_for | Four named failure classes and the wrong-logic fallback; removing an individual vocabulary pattern fails |
| check_stub | Require/forbid patterns, no invented checks and no false forbid of `task.wait`; reverting punctuation normalization fails |
| CorrectionStore | Scoped CRUD, unique refs, withdrawn candidates, secret-scanner failure, approval gates, dismissed exclusions; dropping any guard breaks an asserted state |
| task_for / write_suite | Both automated and human task shapes; actual `star.evals.load_catalog` validates the produced JSON; changing task fields or allowing malformed suites breaks the test |
| handle_action | Listed counts, invalid operations, malformed payloads and explicit approval; bypassing owner authorization fails |

Clock fixtures substitute `clock.datetime.now`, inject the HTTP wall and
monotonic clock, and never sleep or call the network. IANA DST assertions skip
with an explicit reason when the operating system has no time-zone database.
Corrections fixtures patch the timestamp generator and store all SQLite and
JSON files under pytest's `tmp_path`; no real owner profile, secret store,
`evals/` write, GPU or Studio session is involved.

## Small defect found and repaired

`star/corrections.py` allowed a trailing period or colon from ordinary prose
to be captured as part of the forbidden identifier (for example, the word
`wait.` in “use task.wait instead of wait.”). Because a literal period was then
escaped into the forbidden regex, `wait(1)` could evade that check.
The small change strips trailing `() . :` punctuation before building named
patterns, with a new real-`check_stub` regression. This is a pattern-stub
repair, not a claim that an owner correction has been fully verified.

Python's built-in unittest/stdlib (PSF-2.0, free, lowest upkeep), the existing
pytest fixture/parametrize harness (MIT, free, already required), and new
Hypothesis property fuzzing (MPL-2.0, free but adds dependency and seed
maintenance) were compared. Existing pytest is selected so these deterministic
fixed-clock regressions run on Linux and Windows with no new dependency.

These tests are expected to be fast/offline; execution duration must be
confirmed from GitHub CI, not asserted as a local run.
