# STAR: faster verified learning and a multi-Studio experiment farm

*Research and implementation note — 2026-10-11. Candidate source change, not a shipped Windows release.*

## Executive decision

STAR already has `star/agent_runtime.py` (parallel task DAG), `star/lessons.py` and
`star/lesson_digest.py` (project-scoped learning with review), `star/eval_runner.py`
(quality-focused suite runner), `star/frontier_lab.py`/`star/eval_gate.py` (comparative
promotion gates), and `star/studio.py` (official Roblox MCP). **Do not invent a second
memory store, silently retrain the model, run arbitrary Luau, or multiply expensive
GPU inference calls before benchmarking.** Connect those components using verified
trial records. Parallelize independent Studio *observations*, independent research,
and independent Studio *test sessions* only after an owner-approved plugin adapter
and actual Windows acceptance exist.

This change adds `star/studio_parallel.py`: a real, bounded, read-only MCP
observation farm across multiple already-open, explicitly chosen Studio IDs.
It does not start Studio processes, edit places, invoke Luau, start playtests, or
claim a successful observation is a gameplay pass. It **does** overlap I/O for
separate Studios, fail closed on stale selection, serialize calls to each Studio,
count warning/error-looking output lines, hash rather than expose console text,
contain exceptions, measure observed wall latency, and generate only *reviewable*
recurrence candidates. Repeatedly reading an unchanged buffered console is not
new evidence; identical hashes do not generate a new finding.

## Primary sources and non-obvious constraints

1. **Official Studio MCP:** [Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp)
   supports one client attached to multiple open Studio instances. After the
   [August 19, 2026 multi-agent update](https://devforum.roblox.com/t/studio-mcp-multi-agent-improvements-and-connected-ai-clients/4820583),
   each tool call is explicitly addressed with `studio_id`; never depend on a
   global active-Studio switch. Discover IDs anew before a batch.
2. **StudioTestService:** [Roblox API](https://create.roblox.com/docs/reference/engine/classes/StudioTestService)
   documents `ExecuteMultiplayerTestAsync(players, args)` with **1–8 simulated
   clients per test session**, and **only one active multiplayer test per Studio**.
   Launching a test requires **plugin security**, and the entrypoint is called
   from a plugin, not an arbitrary server script or general `execute_luau` tool.
   An owner-approved plugin must receive a selected test ID and attest to the
   output of a matching server-side `EndTest` call. `GetTestArgs()` has a
   documented client LocalScript limitation. Do not treat timeouts or other
   unexpected termination as successful tests.
3. **Studio testing modes:** [Creator Hub](https://create.roblox.com/docs/studio/testing-modes)
   distinguishes server-and-clients testing from actual separate Studio windows.
   Simulated clients inside one Studio are **not** an independent multi-Studio
   process farm; reserve per-Studio ownership and per-process resource budgets.
4. **Performance:** [Roblox performance diagnosis](https://create.roblox.com/docs/performance-optimization/identify)
   covers Developer Console, Script Profiler and MicroProfiler. Studio frame rates
   can misrepresent the player client; [hardware validation](https://create.roblox.com/docs/performance-optimization/test-on-hardware)
   is needed for credible graphics/performance claims.
5. **Local inference:** [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
   supports `--parallel`, continuous batching, prompt caching, and metrics.
   [vLLM prefix caching](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/)
   can reduce repeated prompt prefill, **not** decode time; [vLLM inference](https://docs.vllm.ai/en/stable/)
   also offers continuous batching. More workers may be *slower* on a saturated
   single GPU. Use the existing `scripts/benchmark_star.py` and compare real
   end-to-end p50/p95/first-token timing, quality and failure rate on the PC.
6. **Optimization without full fine-tuning:** [DSPy optimizers](https://dspy.ai/3.2.0/learn/optimization/optimizers/)
   and [MIPROv2](https://dspy.ai/3.4.0/api/optimizers/MIPROv2/)
   optimize few-shot demonstrations/instructions against a metric. Train/validate
   on separate cases, use STAR's locked holdout to gate promotion, and never
   treat a model-generated answer as its own gold label.
7. **Efficient experiment allocation:** [Ray Tune ASHA](https://docs.ray.io/en/latest/tune/getting-started.html)
   illustrates stopping clearly underperforming *measured* trials early. This
   is a roadmap idea, **not** a new STAR dependency. Avoid early stopping for
   a one-off visual/artistic review with subjective or noisy measurements.
8. **Async cancellation:** [Python asyncio](https://docs.python.org/3/library/asyncio-task.html)
   supports timeouts and semaphores. Cancellation must propagate and release
   leases; a timeout is missing evidence, not a negative gameplay verdict.

## What is implemented in this PR

`python -m star.studio_parallel` provides the following local-only command:

```powershell
# Open two independent Studio windows, enable their Studio MCP servers, then
# get exact IDs from the existing STAR Studio connection discovery.
py -3.11 -m star.studio_parallel `
  --studio-id "<first-discovered-id>" `
  --studio-id "<second-discovered-id>" `
  --rounds 3 --max-parallel 2 `
  --out "$env:TEMP\star-studio-observations.json"
```

The host supplies all IDs; STAR **never** assumes the first instance is safe.
The tool list and attached instances are freshly discovered before a batch;
absence of a requested ID or any required read tool fails closed. Only
`get_studio_state` and `get_console_output` are called for a selected Studio.
The same Studio is observed sequentially across rounds; unrelated Studios
can overlap up to the bounded concurrency setting (default 2, hard limit 8).
No process spawning is implemented; Windows multiple-process capacity and
Studio MCP readiness must be verified on the actual owner machine.

Evidence JSON reports: source, timestamp, target, real observed wall time,
peak concurrency, observation count, per-Studio status (`observed`,
`timed_out`, `invalid_evidence` or `unavailable`), read-only play state when
recognizable, output-line and alert-line counts, SHA-256 of the buffered
console text, p50/p95 of successful observations, and human-review candidates
when distinct snapshots show repeated alert patterns. It never contains
raw console messages, launcher commands, connector exceptions, scripts,
credentials or claims that Studio gameplay or model training passed.

`candidate_findings` deliberately does not call `LessonStore.approve`,
`Promoter.apply`, `execute_luau`, or any store API. The owner must review the
original Studio output before manually approving a relevant durable lesson.

## Next: real parallel Studio gameplay tests (not implemented)

A real test farm should use a **trusted, host-installed, owner-enabled plugin**
per isolated, disposable test place. Each plugin defines an allowlist of
named suites (no arbitrary Luau supplied by the model) and launches
`StudioTestService:ExecuteMultiplayerTestAsync` from plugin context.
A server-side test fixture reads a run-bound argument, performs deterministic
assertions and calls `EndTest` with an explicit run ID, suite ID, result and
artifact digest. The adapter needs verified `studio_id`, exact place identity,
nonce, deadline, fixture version, cancellation handling, and an authenticated
local result channel. Do **not** assume that unrestricted MCP `execute_luau`
acquires plugin security or that a `start_stop_play` return proves the test
passed. This protocol requires real Windows/Studio validation before enabling
any live tool invocation.

Per Studio: one running multiplayer scenario at a time; up to eight simulated
clients **inside** that scenario. Across Studios: separate explicit IDs,
non-overlapping writable snapshots, per-place/version locks, CPU/RAM/GPU
admission control. Multiple windows on one PC share a GPU and can become
slower as load grows. Choose the concurrency sweet spot empirically. Avoid
launching two writers on the same saved experience/place, regardless of IDs.

### Scenario corpus to implement behind the plugin gate

| Family | Measurable success criteria | Artifacts |
|---|---|---|
| Lobby matchmaking | correct roster and team assignment across 2–8 simulated clients | server assertion receipts |
| Join/leave | disconnect, reconnect and leader handoff preserve expected state | state transitions |
| Replication | server and client agree on authoritative replicated values | per-role state digests |
| Gameplay rounds | countdown, round state and winner obey a fixed oracle | state transition timeline |
| Data safety | test-key or mocked store survives bounded fault simulation | deterministic fixtures only |
| UI layout | no clipping at target viewport sizes; visual reviewer still required | labeled screenshots |
| Physics | predefined moving object stays within tolerance | sampled positions |
| Animation | named tracks load and play at expected markers | track/event trace |
| VFX and lighting | render capture agrees with approved reference thresholds | screenshot/diff metrics |
| Performance | client p95 frame time, memory and join time below device budgets | hardware profiles |
| Security | client cannot award server currency or force privileged effects | rejected remote calls |
| Concurrency | no shared-state races under simultaneous actions | event log and invariants |

Never fabricate screenshot similarity scores, FPS, successful test exits, or
Roblox device compatibility. Tests need user-approved fixture designs, exact
inputs and explicit pass/fail oracles. Prefer deterministic assertions for
Luau/math/replication and visual review for aesthetics.

## Faster learning that remains accurate

### Four feedback stages

1. **Capture (cheap):** preserve task intent, environment/version, tested
   source SHA, asserted outcome, latency, and failure cause. Hash/deduplicate
   repeated evidence and redact secrets. Raw model text is **not** truth.
2. **Compare (parallel when independent):** generate several candidate
   solutions with bounded model/tool budgets; grade against the same
   immutable baseline and fixtures; stop futile candidates early only with
   statistically meaningful evidence. Local 8 GB GPUs might prefer a single
   active model slot and parallel *CPU/tool* activities.
3. **Review and promote:** a candidate improvement must pass static checks,
   offline unit tests, real isolated Studio tests when available, and STAR's
   existing holdout/eval gate. Human approval is still needed for model-inferred
   memory and policy-sensitive or user-facing changes.
4. **Measure regression:** store success %, repeated-run consistency,
   p50/p95 time to first token, wall-clock task completion, peak RAM/VRAM,
   and unattended failure rate before and after changes. Revert on a verified
   regression. A generated summary cannot mark its own evaluation as passed.

### Prioritize useful information, not unbounded data intake

- Project-specific retrieval: remember what the owner actually confirmed;
  de-duplicate semantically equivalent lessons, keep citations and version
  validity, refuse evidence from unrelated games.
- Documentation research: cache official Roblox API facts keyed by engine
  version/URL/retrieval time; revisit only when stale or contradicted.
- Error-driven tests: prioritize distinct failure signatures and untested
  systems, not repeated console polling with unchanged hashes.
- Adaptive resource scheduling: foreground chat gets first access to its
  local model slot; background research and lesson digest stop/cancel on
  live user input. Keep Studio and browser concurrency separate from GPU
  model concurrency.
- Opt-in offline fine-tuning: potentially consider LoRA after gathering a
  licensed, consented, validated dataset, an independent holdout and enough
  hardware. Current per-turn lesson recall **does not change weights**.

### Response-speed investigation: ordered by risk and payback

1. Measure current fastest local model, first token, warm-up and cached
   contexts with existing `scripts/measure_first_token.py` and
   `scripts/benchmark_star.py`, separating model prefill vs decode.
2. Keep stable system prefixes, limit unnecessary context, retrieve only
   ranked project evidence, stream as soon as the first useful token arrives.
3. Parallelize I/O-bound documentation lookups and static analyzer tasks,
   but preserve per-resource ownership and deadlines.
4. Only then test 1, 2 and 4 inference slots with identical prompts and
   a concurrency/failure matrix; reject higher parallelism if latency,
   OOMs, hallucinations or timeouts regress.
5. Record rollback conditions; new prompts/skills/routes do not promote
   themselves and are evaluated on held-out tasks.

## Required acceptance gates

The Python tests below exercise real Studio tool and instance discovery against an offline
connector fake; discovery calls are excluded from observation-call counts. These
commands are acceptance requirements, not evidence of local execution in this repair.


- `python -m compileall -q star main.py`
- `python -m pytest -q` (full repository, network/GPU/keyring-free)
- `python -m pytest -q tests/test_studio_parallel.py`
- `cd frontend && npm run test && npm run build` (no frontend source modified
  by this addition, but integration CI still matters)
- Windows smoke: connect 2 existing Studio processes, gather one round from
  each and verify their IDs and independent read-only responses.
- Windows load: 1/2/4 Studios, three rounds each, monitor CPU/RAM/VRAM and
  confirm concurrency improves **wall time** without making the foreground
  app unresponsive.
- Offline failure drills: stale ID, missing tool, malformed response,
  large console, Studio disconnection, timeout, repeated unchanged log,
  cancellation, launcher unavailable; no raw error leaks.
- When plugin tests are added: per-place guard checks, negative permission
  tests, fixture signatures, honest `EndTest` semantics, failure injection,
  visual evidence and human signoff before allowing edit/play tools.

## Limits and honesty

This feature is a **working source-level read-only multi-Studio observer**,
not an agent that independently opens arbitrary Studio windows or trains its
foundation weights. It does not replace STAR's main evaluation suite or its
protected holdout, and an `observed` status only confirms a bounded response.
No real Roblox Studio, Windows process concurrency, GPU acceleration, memory
promotion or hosted model throughput has been tested by this research patch.
Those claims depend on the owner's Windows acceptance and future adapter work.
