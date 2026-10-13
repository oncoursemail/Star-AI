# Wall-clock and scheduler-sensitive offline tests

Audited **2026-10-13** from the named test modules and shared helpers.
Risk H = tight elapsed-time bound/false red on loaded CI; M = bounded
process/thread scheduling; L = existing fake clock or very generous bound.
The margin below is the assertion threshold versus its sleep/timeout; n/a
means no numeric duration assertion. Monotonic clocks avoid midnight and
timezone changes, not worker preemption. Old equal datetime timestamps are
covered separately by the frozen-clock chat-order test. Audio understanding
deadline tests belong to their own PR and are not modified here.

| Test | Timer / margin | Failure mode | Risk | Disposition and preserved guarantee |
|---|---|---|---|---|
| test_workbench_core.py::test_timeout_output_file_size_and_resource_limits | 100ms timeout; 90ms–5s elapsed | 10ms lower-bound margin, slow child startup | H | Keep real subprocess cancellation and memory/file checks |
| test_workbench_core.py::test_job_lifecycle_concurrency_output_and_stop | 20s child; 3s startup polling at 20ms | Slow Windows child startup | H | Leave: real subprocess output and stopping is the contract |
| test_workbench_core.py::test_kill_switch_refuses_every_tool_and_stops_active_jobs | 20s child; Event.wait(3s) | OS kill scheduling | M | Leave: must prove genuine child exit |
| test_workbench_core.py::test_memory_limit_actually_prevents_allocation | 3s child timeout | Slow interpreter startup | M | Leave: relies on OS address-space limit |
| test_voice_filecall.py::test_scripted_call_runs_turns_and_a_barge_in_and_saves_everything | Per-turn stage total <2s | Host audio/stream scheduling | M | Leave full threaded call scenario |
| test_voice_filecall.py::test_virtual_speaker_plays_in_real_time_and_stop_cuts_the_recording | Sleeps 250ms, then 500ms; asserts 200–450ms heard (50ms lower margin) | Sleep overshoot affects recorded length | H | FIX injected clock: playback, stop, silent tail and audio length still checked |
| test_voice_call.py::test_speech_starts_on_the_first_sentence_not_after_the_whole_reply | First audio <25% of generation duration | Relative times shift with thread scheduling | H | Leave until scripted token scheduler can be injected |
| test_voice_call.py::test_barge_in_stops_speech_cancels_the_brain_and_keeps_only_what_was_heard | Must play >300ms before interruption, polls to 5s idle | Speaker/brain pacing | M | Leave: still proves cancellation and cut heard-text |
| test_voice_brain.py::test_close_from_another_thread_ends_a_stream_cleanly | 120ms Timer, total <400ms (280ms slack) | Timer callback runs late | H | FIX synchronization Events: close still terminates blocked iterator from other thread |
| test_doc_knowledge.py::test_a_reply_that_trickles_in_is_cut_off_at_the_request_time_limit | 60 x 50ms sleep, 300ms reply deadline, elapsed <1.5s | Delayed mock stream scheduler | H | FIX fake monotonic clock: single 300ms reply budget still enforced |
| test_doc_grounding.py::test_finalize_repairs_only_in_a_deep_turn_with_time_left | 600s budget, started 500s ago | Timing drift across threshold | L | Leave: 100s remaining vs 45s repair reserve |
| test_doc_grounding.py::test_a_repair_that_outlives_the_turn_is_stopped_and_the_answer_survives | 200ms repair allowance vs SlowModel(30s), outer 3s | Busy asyncio timer | H | Leave: cannot weaken actual cancellation guarantee |
| test_doc_grounding.py::test_the_self_check_is_skipped_when_the_turn_is_out_of_time | 5s left vs 10s reserve, 500ms simulated check | Scheduler drift but 5s gap | L | Leave: still proves skipped check does not claim validation |
| test_doc_grounding.py::test_a_check_that_hangs_is_abandoned_before_the_deadline_and_nothing_is_claimed | 200ms review allowance vs 1.5s sleep, outer 1s | Thread-pool and event loop scheduling | H | Leave: keep strict upper bound on cancellation |
| test_doc_grounding.py::test_documentation_events_reach_the_listener_in_order_on_the_loop_thread | asyncio.sleep(0), no elapsed assertion | Cooperative task ordering | L | Leave: intentional deterministic event-loop yield |
| test_night_school.py::test_real_path_backs_off_at_once_when_another_client_appears_and_writes_the_outbox | 1s busy callback, result <20s | Fake-server scheduling | M | Leave cross-request live fake-server occupancy coverage |
| test_night_school.py::test_the_gate_waits_while_the_brain_is_busy_and_needs_ten_quiet_minutes | Injected clock 700/599/601s; no real sleep | None: controlled clock | L | Leave: already deterministic |
| test_instant_route.py::test_decision_overhead_benchmark | 20,000 perf_counter_ns calls; assert >=0 | Hardware makes measured speed vary | L | Leave: benchmark only logs throughput, not a fixed millisecond pass requirement |
| test_warmup.py::test_warm_up_stops_when_a_real_request_starts | Cancel Timer(300ms), completion <3s | Timer callback may be delayed | M | Leave: real running request cancellation needs a handshake refactor |
| test_warmup.py::test_warmer_runs_off_the_calling_thread_and_one_at_a_time | Event.wait(5s) | Slow thread scheduling | M | Leave: event synchronization already present |
| test_redact.py::test_long_input_is_handled_in_linear_time | 2s perf_counter cap on hostile text | CPU contention can cause false red | H | Leave: a fake clock would invalidate the actual regex worst-case time guard |
| test_single_instance.py::test_unreachable_owner_fails_closed | time.sleep monkeypatched to no-op | None: already mocked | L | Leave: existing deterministic test |

**Inventory:** 22 entries, **9 high / 7 medium / 6 low**. The
tests/voice_fakes.py delay, Event.wait, fake playback and polling mechanisms
are shared helpers, not standalone cases. tests/conftest.py contributes no
real-time pass/fail assertion. This lists the timing cases found in the
specified files and their direct helpers, not all tests in the repository.

## Changed-test guarantees and CI measurement

Only three high-risk tests are changed; each uses a fake clock or explicit
threading event, without introducing a new dependency, deleting/skipping tests,
or changing production behavior. The real VirtualSpeaker accepts a clock
argument: exact 250ms and 500ms advances still prove recording truncation and
silence. The real ScriptedBrain stream must still unblock on close from a
different thread, with bounded Event.wait solely to detect a deadlock.
The knowledge-client mocked trickle still must fail within a **single 300ms
total deadline**, despite each byte advancing the virtual clock only 50ms.

Measure the full Linux pytest suite duration from GitHub before and after
this PR; the variation includes runner load and is not a controlled speed
benchmark. No Studio/gameplay or real-service performance claims follow.
