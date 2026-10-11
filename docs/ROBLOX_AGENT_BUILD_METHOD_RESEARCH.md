# Token-efficient, test-gated Roblox game building

Status: research and proposed protocol, NOT a claim that the implementation or live tests exist. Target: ~10 generated tokens/sec; ~32k model context.

## Repository evidence (read from `star/claude-integration-20261010` on 2026-10-11)

- `star/studio_loop.py:549-562`: `GuardedStudio` checks its verdict, tracks changes in a journal, and supports guarded editing. At `:661-683` live playtest input is refused because it cannot be atomically tied to the exact requested playtest; do NOT describe this as an available automation path.
- `star/policy.py:14-27,42-46,61-72`: read/edit/playtest/Luau classes; `execute_luau` requires explicit permission and Edit DataModel. Do not bypass the approval system for automated tests.
- `star/studio_remote.py:19-29,154-191`: pinned test-place/blank-place operation and `PinnedSession` checks; the connection is not an unrestricted executor.
- `star/roblox_pipeline.py:17-23,37-83,98-148,158-238`: `ServerScriptService.Tests` ModuleScripts ending `.spec`, structured test result marker `STAR_TEST_RESULT`, report validation (nonempty consistent cases), approved private place, saved version, exact-version tests. Published pipeline is distinct from an interactive Studio playtest.
- `docs/ROBLOX_ACCESS.md:181-196,253-256`: rechecks identity, journals and undo; connector lessons include `game.`-prefixed script paths, stale output lines and per-session undo. Use run markers, not undifferentiated output.
- `AGENTS.md:13-14`: never mark unexecuted tests passed or expose unrestricted Luau in ordinary edit mode.
- There is NO evidence from these reads that STAR currently executes multi-client `StudioTestService` scenarios or reliably automates touch/click interactions. Treat such test-driving as a proposed privileged plugin/test harness, requiring a separate security review.

## 1. The executable protocol

**Rule:** the model produces short plans and *one scoped change at a time*. Tools verify everything they can without consuming another model generation. Hard-fail closed on missing evidence.

0. **Connect, authorize and fingerprint.** Inspect connector capabilities, selected `studio_id`, permitted place identity, engine session, Edit/Play state and writable scope. If identity or authorization is unknown, read only. Record initial instance-tree inventory, script/source hashes, baseline log cursor/run marker and screenshot. A changed engine session invalidates edit assumptions.
1. **Specify a tiny complete product.** In at most ~300 generated tokens produce: core loop, win/lose, lobby/spawn, UI, number of players, persistence policy, explicit non-goals. Fix a maximum scope (e.g. single map, 2-3 mechanics, 1 primary UI). No 'entire AAA game' planning.
2. **Compile acceptance contracts before building.** Each milestone is a record `{id, prereqs, owned_paths, outputs, checks, timeout_s, max_repairs, rollback}`. Checks carry `signal` (tree/script/static/solo-server/solo-client/multiclient/screenshot) and machine-verifiable expected value. Explicitly record which checks cannot be automated on the present connector. A not-run check is UNKNOWN, not PASS.
3. **Build a compact repository/instance map.** Use a deterministic index: paths, classes, relevant script names + top-level functions, hashes, service dependencies, remotes, attributes and recent failure summaries. Retrieve only impacted source, not every script. Retrieve approved skill snippets by exact applicability, never a giant skill dump.
4. **Select the next smallest dependency-unblocked milestone.** Prefer an observable vertical slice: map shell -> spawn -> one interaction -> server state -> client display -> lifecycle -> polish. Limit a transaction to one mechanic or related small set of instance paths. Specify rollback before editing.
5. **Preflight before generating source.** Compare expected script hashes; ensure required parent instances and class names exist; check remote/attribute naming contracts, ownership boundaries, no duplicate listeners. If preflight fails, refresh facts first, *do not ask model to write guessed repairs*.
6. **Generate minimal patch with tests.** Reuse validated deterministic templates for spawns, remotes, state machines and UI frame structure. Prefer <~150 changed Luau lines per attempt and 1-3 files (heuristic, benchmark). For each behavior generate one positive and one negative assertion first. Use server-authoritative rewards/economy and client-only display.
7. **Static gate.** Parse/analyze Luau when a trusted analyzer exists; otherwise don't claim compilation. Validate instance/class schemas, unique names, required paths, RemoteEvent/RemoteFunction types, scripts in intended containers, duplicate connections, unreachable references and basic geometry (anchoring/collisions/spawn clear). Fail => stop before playtest.
8. **Apply guarded transaction.** Only through permitted Studio connector and place/session-pinned edits; CAS old source hash for script replacement. Journal paths and source hashes. An ambiguous tool outcome is UNKNOWN: inspect actual tree/hash before retry, never blindly replay writes.
9. **Cheap Edit DataModel gate.** Read only affected subtree plus properties and hashes, compare against contract. This is faster than a full test session. If it fails, roll back the transaction and repair the minimal diff.
10. **Runtime gate.** Start a distinct test with unique marker. Require marker visibility and session identity. Read only log lines belonging to this run; capture server+client errors separately when available. Wait for bounded settling and explicit completion of timed assertions. On crash/time-out/no marker, report UNKNOWN/FAIL, never PASS.
11. **Behavior gate.** Execute test harness assertions inside the correct execution context. Studio's built-in MCP `start_stop_play` is a solo Play Client; multi-client proofs require an independently authorized Studio plugin using `StudioTestService` (if developed) or manual verification. Never claim a simulated user input was exercised if no supported tool exists.
12. **Visual gate, only when relevant.** Compare screenshot to explicit reference/layout contracts: HUD visible within viewport, safe inset, buttons not occluded, spawn and destination visible, contrasting text. Screenshot is evidence for appearance only, not persistence/security. Run visuals at the end of a functional slice, not per source edit.
13. **Accept or repair.** PASS requires all mandatory checks executed, matching target + session + source hashes, no new relevant errors, valid test evidence. On failure: classify (schema, syntax, context, runtime, assertion, visual, security), provide the model only failed assertion, relevant 20-80 source lines and minimal tree context. At most 2 model-assisted repair attempts per milestone; after two failures revert to known-good state, split milestone, or request owner guidance. Never keep building atop a failing gate.
14. **Persist compact state outside model context.** After each accepted milestone write machine-readable `build_state.json` and a short prose checkpoint (200-400 tokens): spec version, accepted milestone IDs, current target IDs/session, tree inventory hash, script hashes, owned path set, last run marker and test outcomes, known issues, rollback pointer, next task. Keep test logs/screenshot paths as artifacts (not inline). Retrieve selective evidence next turn.
15. **Final release gate.** Re-run all accepted contracts against the final state; fresh solo session and (where supported) 2-client session; reconnect/reset; screenshot at desktop+small screen; verify safe persistence policies, rollback, no unresolved ERROR/UNKNOWN. Export evidence manifest. Owner controls publishing; do not silently publish.

### Context and token policy

32k tokens is a *capacity ceiling*, not a prompt target. Suggested per-turn allocation: stable safety/tool contract 1-2k, current milestone 200-400, selected repo-map 400-800, relevant code 1-3k, error evidence 200-600, response budget 500-1200; leave remainder unused. Character limits are not token limits. Avoid sending the full instance tree, screenshots, massive logs, previous agent chatter, or all skill files to the local text model. Keep tool schemas byte-stable for cache friendliness. At 10 tokens/s, every avoidable 600 generated tokens costs ~60 seconds. Costs and limits are proposed engineering heuristics; validate with measurements.

### Halt / repair decision table

| Observation | Next action |
|---|---|
| Missing permission/place identity/session changed | halt writes, reconnect and reauthorize |
| Static schema/path/hash mismatch | refresh facts, no playtest |
| Wrong engine context or unsafe target | deny and audit, do not self-repair guard |
| Runtime error or failed assertion | stop, bounded failing evidence -> minimal patch -> recheck |
| Missing/stale test marker, tool timeout | UNKNOWN; read state, reconcile before retry |
| Same failure after 2 repairs | rollback, decompose, owner decision |
| Screenshot looks wrong but functional gate passed | scoped visual patch, rerun affected visual + smoke tests |
| All required checks green and no relevant new errors | accept, checkpoint |

## 2. Ten common failure modes and cheapest deterministic checks

| # | Failure | Cheap pre-runtime/during-runtime detector |
|---|---|---|
| 1 | Edited wrong place or Studio instance | compare exact `studio_id`, GameId/PlaceId, engine session before every write |
| 2 | Wrong service/instance class/path | read affected subtree; assert named parent and `ClassName`, not fuzzy path |
| 3 | Lua/Luau syntax or API typo | pinned local Luau analyzer where available; otherwise bounded Studio execution error gate; don't claim static compile without compiler |
| 4 | Required reference/Remote missing or type mismatched | deterministic dependency and remote registry existence/type check |
| 5 | Client/server authority confused | source contract: rewards only in server code; client requests validated on server; reject client-written currency |
| 6 | Player spawn inside/under world or falling | anchor/collision/position/bounds checks on spawn and floor, plus short fresh playtest assertion |
| 7 | Duplicate objects or multiplied event connections after retry | before/after counts + unique marker/tag scan; reconcile ambiguous transactions before applying |
| 8 | Stale output taken as proof | unique per-run server-printed marker and bounded log cursor + assertion run ID |
| 9 | Lifecycle fails after reset/leave or after round restart | deterministic two-cycle state assertion; count listeners, alive scripts, UI instances after each reset |
| 10 | UI appears fine on desktop but clipped/mobile or inaccessible | deterministic bounding-box/viewport and safe-area checks in client, then screenshot at target resolutions |

Note: these are engineering failure categories, not empirically measured 'top ten' from a STAR failure dataset.

## 3. Milestone acceptance catalog

Every item below is an executable *acceptance specification*; integration into a specific Studio plugin is future work. Use common IDs and fixture names; assertions may be implemented using .spec ModuleScripts for safe server checks. Input-driven tests and multi-client tests require a supported approved harness. `P`=programmatic structural, `S`=server runtime, `C`=client runtime, `M`=multiplayer, `V`=visual.

### Obby (8 milestones)

O1 [P]: Workspace.Obby/Stages exists; 6 ordered anchored platforms; SpawnLocation above solid floor; no overlap with hazard.
O2 [S]: fresh character spawns on Stage1 in two successive respawns.
O3 [S,C]: Stage1->Stage2 checkpoint change fires once, never decreases from re-touching Stage1; client stage HUD matches server stage.
O4 [S]: touching a kill part causes precisely one death; respawn uses last confirmed checkpoint.
O5 [S]: touching final goal completes once; no repeated rewards from repeated touch.
O6 [S]: new round/reset clears transient victory flag; checkpoint reset follows explicit spec (no assumed persistence).
O7 [V,C]: stage indicator/finish state remains visible at wide and narrow viewport, no occlusion.
O8 [S,C]: two full clean runs in fresh playtest sessions, zero relevant errors.

### Tycoon (9 milestones)

T1 [P]: plot, claim trigger, 3 locked purchase pads, dropper, collector, HUD and server-side state components exist.
T2 [S,M]: one owner claims a plot; another player cannot claim the same plot concurrently.
T3 [S]: starting cash is deterministic; purchases decrease balance exactly by price and reject insufficient funds.
T4 [S]: remote purchase request rejects spoofed plot, negative/NaN price (if client supplies one), repeated purchases, unknown item IDs and non-owner; server price is authoritative.
T5 [S]: dropper accrues 1 expected income event per interval, with bounded tolerance and no duplicate producer after reset.
T6 [S,C]: collector credits only server-calculated accrued balance; client HUD matches server balance.
T7 [S]: purchases unlock prerequisites in order; buying same object twice grants no extra income/effect.
T8 [M]: owner leaves, plot unclaims, cleaners stop; next owner receives fresh (or specified persisted) state.
T9 [S,C,V]: rejoin/persistence contract exercised only in approved test data environment; HUD fits target viewports and two consecutive clean server cycles pass.

### Round-based minigame (9 milestones)

R1 [P]: lobby, arena, spawn locations, round state component and HUD exist; no spawns in hazards.
R2 [S]: `Waiting -> Intermission -> Active -> Results -> Waiting` is the sole permitted state cycle.
R3 [S]: below minimum player count never starts round; player-count recovery triggers exactly one round.
R4 [S,M]: eligible players transferred once to arena with distinct valid spawns; joining mid-round uses specified policy.
R5 [S]: start timer nonnegative; round ends at timeout or explicit win; both paths yield exactly one results state.
R6 [S]: elimination changes alive set once; no double elimination after duplicate touch events.
R7 [S]: final survivor (or tie) result deterministic, reward once, server-controlled and idempotent.
R8 [M]: participants leave during countdown, active round and results; clean state and valid winner logic.
R9 [S,C,V]: at least two complete cycles, no accumulating connections, clean log, scoreboard/timer visible on narrow viewport.

For O3/O4/O5, T2/T8 and R4/R8, static checks alone are not enough: mark NOT_RUN until real touch/click/multi-client simulation executes.

## 4. Measuring improvement

Run a fixed held-out suite spanning these three game types with 3 seeds/spec variants each, at least 3 repetitions per spec and identical environment, starting place, permissions, model and token budget. Keep baseline and candidate paired. Track:

1. **Complete-game success** = games passing every mandatory executed acceptance criterion / attempted games. Distinguish PASS/FAIL/UNKNOWN/NOT_RUN and forbid NOT_RUN -> PASS.
2. **Milestone pass@1** and **final verified milestone coverage** (passed / mandatory), by signal type.
3. **Human time and wall time to first playable vertical slice and finished acceptance**, p50/p90.
4. **Generated and prompt tokens per accepted milestone**, and **rework tokens / total tokens**; include tool-result text separately.
5. **Repairs per milestone**, % first-pass, % rolled back, % repeated identical error, timeout/unknown rates.
6. **Regression rate** = formerly passing tests that fail after next accepted milestone.
7. **Studio operation safety** = unauthorized writes (must remain zero), stale/mismatched-target refusals, uncertain operations reconciled before retry.
8. **Behavioral correctness** = each game-specific key invariant pass rate (anti-double-reward, authoritative money, two rounds, restart).
9. **Visual fidelity** = tested safe-area/occlusion rate plus blind human rubric on screenshots; never use screenshot alone to claim mechanic correctness.
10. **Long-context recovery** = restart the agent between milestones and measure successful continuation without replaying the full transcript.

Report paired task-level differences and uncertainty, not only pooled totals. Keep new fixtures held out, never let agents alter grading files, log test manifests/version hashes, and reserve at least one independently reviewed real-Studio end-to-end run for deployment approval. A lower token count is NOT an improvement if verified success falls.

## 5. Research basis and applicable limits

- Wang et al., *Voyager* (2023), automatic curriculum, compositional reusable executable skills and iterative environmental verification: https://arxiv.org/abs/2305.16291 . Transfer principle: store **validated small game skills**, not raw untested agent code.
- Shinn et al., *Reflexion* (2023), verbal feedback from an environment to help subsequent attempts: https://arxiv.org/abs/2303.11366 . Transfer principle: preserve one concise failure-specific lesson and evidence; don't burn context on unguided self-criticism.
- Yao et al., *ReAct* (2022/2023), interleave decisions and environment observations: https://arxiv.org/abs/2210.03629 . Use action/observation loops with tool evidence.
- Chen et al., *Teaching Large Language Models to Self-Debug* (2023), execution-feedback driven fixes: https://arxiv.org/abs/2304.05128 . Prefer executable failing test evidence to introspective text.
- Jimenez et al., *SWE-bench* (2023/2024), evaluate coding agents on externally assessed real tasks: https://arxiv.org/abs/2310.06770 . Transfer principle: test independently with immutable fixtures.
- Yang et al., *SWE-agent* (2024), purpose-built agent-computer interfaces: https://arxiv.org/abs/2405.15793 . Transfer principle: targeted inspect/edit/test tools beat unstructured full-state dumps.
- *Aider repository map* documentation: https://aider.chat/docs/repomap.html . Transfer principle: concise dependency-aware map with selective file expansion; not evidence that exact Aider map works on Roblox instance trees.
- *GameGPT*, LLM multi-agent game development proposal: https://arxiv.org/abs/2401.06621 . Inspiration for roles/decomposition, not evidence that multi-agent swarms beat one 10t/s model.
- Roblox Studio testing modes: https://create.roblox.com/docs/studio/testing-modes . Test/Run differ; Roblox recommends multiple contexts.
- Roblox `StudioTestService`: https://create.roblox.com/docs/reference/engine/classes/StudioTestService . Supports plugin-launched scripted multi-client scenarios; do not assume generic Luau/Edit tool exposes plugin security.
- Roblox `TestService`: https://create.roblox.com/docs/reference/engine/classes/TestService . Useful for structured assertions but not proof of a complete client end-to-end game.

## 6. Implementation order, clearly separated from current verified functionality

P0: Add pure schema `BuildContract` + deterministic evaluator, no new Studio permissions. P1: produce run IDs, structured observations, compact checkpoint and resume. P2: use validated .spec harness for server assertions under existing owner-approved private test pipeline. P3: add visual bounding-box tests and screenshot evidence. P4: separately review/authorize a Studio plugin harness using `StudioTestService` for action/multi-client tests. P5: benchmark against frozen acceptance suite; gate any autonomous rollout. Preserve the existing safety approval, place pin, CAS and unknown-outcome semantics throughout.

**Bottom line:** optimize for **verified outcomes per generated token**, not raw lines of Luau or amount of content built per call. Tiny accepted vertical slices + deterministic cheap failures + bounded repair + compact state will usually be a better starting point than simultaneous generation of all map/UI/game systems. This is an engineering hypothesis to test, not a measured STAR speedup.
