# Open pull-request board — 2026-10-13 (America/Chicago)

**Snapshot:** 46 open PRs (40 draft, 6 ready) as retrieved via the GitHub open-pulls API on 2026-10-14 UTC. This report freezes the pre-report-PR list; counts exclude the draft PR that carries this file. This is a read-only triage recommendation, not a merge authorization or a code review.

**Method / certainty.** Numbers, title, draft/ready, target branch, head SHA, additions/deletions/changed files, and replacement statements were read from GitHub PR metadata and descriptions. Mergeability comes from `mergeable_state` on each PR; `unknown` is not equivalent to `clean`. Individual head-commit GitHub check-runs were read for five columns; `PASS` means the named check reported success, `FAIL` failure, `RUN` in progress, `CANCEL` most recent attempt cancelled, `—` no separate named check on that head. Two same-name successful check-runs are shown once; absent Luau/Windows/Protected checks are **not** presumed green. PR #152 is the continuously updated `star/next` -> `main` integration and its latest Linux/React checks were cancelled after earlier successful checks.

**Inferences:** Lane is derived **only** from branch-name prefix: `star/chatgpt-*` = ChatGPT*, `*claude*` = Claude*, other branch = Owner?* (unverified author, possibly another assistant). Shared-path codes denote potential edit overlap, not demonstrated merge conflicts; only actual `dirty` mergeability signals a conflict. Changed lines use GitHub `additions` / `deletions`, not unique logical lines. `#152` has 660 changed files against `main`, naturally overlapping most `star/next` work; its broad diff is intentionally excluded from peer-overlap codes.

## Priority: five PRs to review next
1. **#276** — one-file green Windows timeout-test correction affecting #270 verification; address the residual wall-clock-flake finding before integration.
2. **#268** — green Studio Lab foundation that #277 and #292 explicitly stack on; review base identity and Play safeguards first.
3. **#266** — green resource-admission layer used by the parallel Studio Lab; validate placement/slot safety before #277.
4. **#280** — green opt-in native Luau preflight evidence; coordinate its shared preflight code with #279 and #293.
5. **#272** — four-file green training data lineage/contamination safety; approve integrity before model-training expansions.

## Complete open PR inventory

| PR | Title | Lane* | State | Base | Mergeability | Linux | Windows | React | Luau | Protected | Head | Diff: files (+/-) | Shared paths | Replaced by | Lead's next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #68 | feat: integrate Roblox architecture intelligence, Blender assets and quality gates | ChatGPT* | Draft | `star/next` | unknown | PASS | PASS | PASS | — | — | `43235de3` | 16 (+1502/-3) | I, K, ARCH | #233 | Superseded; lead may close after checking #233 |
| #105 | Integration: source-provenanced Asset Forge tools with deterministic terrain previews | ChatGPT* | Draft | `star/next` | dirty | PASS | PASS | PASS | — | — | `122ae3ad` | 6 (+617/-1) | I | — | Needs rebase: dirty Asset Forge integration |
| #109 | Integration: bounded specialist research, parallel teams and reviewed tool discovery | ChatGPT* | Draft | `star/next` | dirty | PASS | PASS | PASS | — | — | `1a9f3b3c` | 18 (+1709/-24) | A, D, S, F, C | — | Needs rebase: dirty, heavily shared runtime files |
| #147 | Evaluation-driven code generation fixes (draft: gain not proven yet) | Owner?* | Draft | `star/next` | unknown | PASS | — | PASS | — | — | `ed6dd6ba` | 19 (+11304/-89) | A, D, S, G | #185 | Superseded; lead may close after checking #185 |
| #148 | Training-data generator and curation pipeline (draft: no kept examples yet) | Owner?* | Draft | `star/next` | unstable | PASS | — | FAIL | — | — | `124bf5e3` | 28 (+3942/-0) | — | — | Hold: React failure, zero demonstrated real examples |
| #152 | STAR next: merged work after v0.9.0 | Owner?* | Draft | `main` | unstable | CANCEL | PASS | CANCEL | PASS | PASS | `64c1982c` | 660 (+87630/-587) | — | — | Owner decision: main-base integration, cancelled latest L/R |
| #173 | [Draft] Repair #145: reapply sandboxed Luau execution on current integration base | ChatGPT* | Draft | `star/next` | unknown | PASS | PASS | PASS | — | — | `6a25abd2` | 18 (+1817/-11) | D, T, G, LU, UI | — | Hold: competes with #181 for the same #145 lineage |
| #181 | Run and repair Luau before answering (replaces #145) | ChatGPT* | Draft | `star/next` | unknown | PASS | PASS | PASS | — | — | `c14664b1` | 21 (+2506/-9) | D, T, G, LU, UI | — | Hold: compare #173 and missing native-Studio evidence |
| #185 | Repair PR 147 on verified star/next (supersedes #184) | ChatGPT* | Draft | `star/next` | unknown | PASS | PASS | PASS | — | — | `9c52429f` | 10 (+2019/-89) | A, D, S, G | — | Review next: replacement for #147, high runtime overlap |
| #217 | Issue 120: refuse cleanly and roll back when an upgrade cannot replace STAR | Owner?* | Draft | `star/next` | clean | PASS | PASS | PASS | — | — | `feacd56e` | 4 (+261/-8) | INS | — | Review next: isolated installer rollback |
| #233 | [apply-review-pr68] Reapply architecture/Blender prototype with opt-in and portability fixes | ChatGPT* | Draft | `star/next` | dirty | PASS | PASS | PASS | PASS | PASS | `ff23ab89` | 16 (+1515/-5) | I, K, ARCH, TC | — | Needs rebase: dirty despite replacing #68; repair in place |
| #240 | [AP-KZD9BN-M2] Finish Roblox UI compiler review on current next | ChatGPT* | Draft | `star/next` | unknown | PASS | PASS | PASS | PASS | PASS | `9feba181` | 5 (+543/-36) | — | — | Review next: small UI compiler repair, green |
| #244 | [npc-luau-types-practice-extension] Strict Luau NPC exercises (replaces #241) | ChatGPT* | Draft | `star/next` | unstable | PASS | PASS | PASS | — | FAIL | `de316080` | 3 (+936/-4) | — | — | Owner decision: protected closure FAIL; no guard bypass |
| #245 | [practice-tasks-with-real-tests] 30 executable Roblox exercises (replaces #242) | ChatGPT* | Draft | `star/next` | unstable | PASS | PASS | PASS | PASS | FAIL | `c55ade54` | 34 (+3796/-0) | — | — | Owner decision: protected closure FAIL; no guard bypass |
| #249 | [first-token-speed-audit] Instrument real first-word stages with offline fake | ChatGPT* | Draft | `star/next` | dirty | PASS | PASS | PASS | — | PASS | `2a6fa8e2` | 7 (+411/-9) | A, D, G | — | Needs rebase: dirty first-word speed changes |
| #252 | [practice-tasks-beginner-v2] Thirty new checkable beginner Roblox practice tasks | ChatGPT* | Draft | `star/next` | unstable | PASS | PASS | PASS | — | FAIL | `9f4d405a` | 2 (+2893/-0) | — | — | Owner decision: protected closure FAIL; hold task catalog |
| #254 | Release v1.0.0: version, release notes, website | Owner?* | Draft | `star/next` | clean | PASS | PASS | PASS | — | — | `15ba3216` | 21 (+5898/-57) | F, INS, BUILD | — | Owner decision: release changes must follow acceptance |
| #259 | [roblox-place-serialization-regressions] Verify Roblox place XML and source boundaries | ChatGPT* | Draft | `star/next` | unknown | PASS | PASS | PASS | — | PASS | `fa26420d` | 3 (+248/-7) | — | — | Review next: narrow XML/serialization regression fixes |
| #266 | Resource planner: live admission across brain 1, brain 2 and the PC (wires #206/#207) | Owner?* | Draft | `star/next` | clean | PASS | PASS | PASS | — | — | `5e0657ad` | 32 (+3876/-51) | S | — | Review next: planner admission used by Lab v2 |
| #268 | STAR Studio Lab: plan, apply, playtest, look, fix loop in a real Studio | Owner?* | Ready | `star/next` | clean | PASS | PASS | PASS | — | — | `3e52a4de` | 5 (+1878/-4) | I, LAB, TC | — | Review next: Studio Lab base for #277/#292 |
| #269 | Brain 1 host tuning + scoped sudo allowlist (owner-run) | Owner?* | Draft | `star/next` | clean | PASS | — | PASS | — | — | `a46575cf` | 3 (+719/-0) | — | — | Owner decision: host tuning, no Windows check |
| #270 | Best-of-N for code: generate several, test, keep what works (opt-in) | Owner?* | Draft | `star/next` | clean | PASS | PASS | PASS | — | — | `63ac7ce2` | 7 (+1856/-3) | A, D, S | — | Review next: measured code candidate selection, core overlap |
| #271 | STAR Creator Intelligence: glTF, game-engine dependencies, REA binary evidence + roadmap | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `6a661a12` | 8 (+1208/-3) | TC | — | Review next: read-only creator evidence tools |
| #272 | [gpu-pair-lineage-contamination-regressions] Fail closed on training pair lineage and eval aliases | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `1967906c` | 4 (+250/-11) | — | — | Review next: important training-lineage safety tests |
| #273 | [worked-example-import-provenance-bounds] Bound project corpus and preserve declared evidence | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `0ae24ebd` | 3 (+231/-6) | — | — | Review next: verified-example import limits |
| #274 | Experimental CAG warm-up KV banks: scoped, opt-in slot checkpoints | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `95f1d7c3` | 7 (+836/-4) | D | — | Hold: opt-in KV bank needs owner hardware validation |
| #275 | STAR self-play, sealed skill evolution, and verified-rights training foundations | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `7493709d` | 9 (+1778/-0) | — | — | Hold: self-play/training foundations lack live Studio/GPU proof |
| #276 | Fix nondeterministic Windows audio deadline test without weakening timeout guarantee | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `72ff02d1` | 1 (+5/-1) | — | — | Review next: 1-file deadline flake; deterministic test advised |
| #277 | Studio Lab v2: parallel Studios (2x tested results/h), smarter fixes, 17-spec suite, UI specs | Owner?* | Ready | `star/next` | clean | PASS | PASS | PASS | — | — | `a1d2526e` | 25 (+5270/-4) | I, LAB, PAR, TC | — | Hold: stacked on #268; review after base, ready status |
| #278 | STAR Intelligence Accelerator: free APIs, verified learning, memory, creator engines and performance roadmap | Owner?* | Draft | `star/next` | clean | PASS | — | PASS | — | — | `da1e715c` | 2 (+346/-0) | — | — | Hold: roadmap only; reconcile with active implementation |
| #279 | [roblox-api-confusion-advisory-preflight] Optional source-linked method advisories | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `32fc840f` | 6 (+351/-4) | PRE | — | Review next: preflight corpus; coordinate PRE cluster |
| #280 | [roblox-preflight-native-analyzer-evidence] Explicit fail-closed Luau analyzer evidence | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | PASS | PASS | `8f984d7b` | 5 (+492/-35) | PRE | — | Review next: bounded native Luau evidence; PRE cluster |
| #281 | Discord: opt-in rotating STAR bot activity without privacy leaks or reconnect spam | Owner?* | Draft | `star/next` | clean | PASS | PASS | PASS | — | — | `a58eeb53` | 5 (+265/-3) | BOT, CONF | — | Review next: opt-in Discord presence; BOT overlap |
| #282 | [roblox-worked-examples-stateful-adversarial-tests] Test multi-step obby and shop rules | ChatGPT* | Draft | `star/next` | clean | PASS | — | PASS | PASS | PASS | `3fbae626` | 5 (+411/-4) | — | — | Review next: stateful examples with native specs |
| #283 | Discord bot autostart: Settings > Discord supervisor, single-instance lock, Task Scheduler script | Owner?* | Ready | `star/next` | clean | PASS | PASS | PASS | — | — | `f4d38ef9` | 20 (+1724/-20) | D, S, F, T, BOT | — | Review next: Discord supervisor; BOT and desktop overlap |
| #284 | Roblox field-lesson skill packs from the Paintball port (opt-in) + practice proposals | Owner?* | Ready | `star/next` | clean | PASS | PASS | PASS | — | — | `aeb2326e` | 14 (+1127/-1) | K | — | Review next: sourced Paintball lessons; K overlap |
| #285 | [lessons-docs-schema-validator] Validate all unreviewed lesson documents | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `f1756dcb` | 1 (+214/-0) | — | — | Review next: standalone lesson document validator |
| #286 | [tests-flaky-fresh-chats-ordering] Make tied chat updates deterministic | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `a166fec3` | 2 (+114/-5) | D | — | Review next: small deterministic conversation ordering |
| #287 | Discord: owner Studio Lab screenshots, reference-image critiques and visual corrections | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `3ef1e281` | 10 (+1113/-5) | BOT, CONF | — | Hold: Discord visual tool, BOT overlap and access audit |
| #288 | [tests-wall-clock-sensitive-audit] Replace sleeping tests with controlled clocks and events | ChatGPT* | Draft | `star/next` | unstable | PASS | RUN | PASS | — | PASS | `55eb7b3d` | 6 (+117/-31) | VOICE | — | Hold: Windows build still running on observed head |
| #289 | STAR sees Blender on brain 2: star_blender tool + Lab MCP launcher + lantern demo | Owner?* | Ready | `star/next` | clean | PASS | PASS | PASS | — | — | `91390c56` | 36 (+2901/-3) | D, S | — | Review next: Windows now green; owner Studio/Blender gate review |
| #291 | [luau-lint-rule-test-matrix] Exhaustive rule cases and local-function shadow fix | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | PASS | PASS | `41ffef45` | 3 (+288/-3) | — | — | Review next: Luau lint matrix and native specs green |
| #292 | Studio Lab v3: 3-Studio measurement, measured jump limits, UI fix loop, 43 specs, nightly timer | Owner?* | Ready | `star/next` | clean | PASS | PASS | PASS | — | — | `cb8492e6` | 54 (+9679/-4) | I, LAB, PAR, TC | — | Hold: large #268 -> #277 -> #292 Studio Lab stack |
| #293 | [roblox-module-require-graph-preflight] Optional bounded static ModuleScript dependencies | ChatGPT* | Draft | `star/next` | unstable | PASS | RUN | PASS | — | PASS | `4011b9f7` | 4 (+593/-6) | PRE | — | Hold: Windows running; coordinate PRE cluster |
| #294 | Voice: Star mum persona, read-aloud, push-to-talk calls | Owner?* | Draft | `star/next` | clean | PASS | PASS | PASS | — | — | `6b8cb1f3` | 21 (+1530/-52) | C, VOICE | — | Review next: voice feature; coordinate VOICE test and Composer |
| #295 | [windows-package-data-completeness] Audit static package reads and PyInstaller parity | ChatGPT* | Draft | `star/next` | clean | PASS | PASS | PASS | — | PASS | `1b657b36` | 4 (+261/-1) | BUILD | — | Review next: package completeness and installer build overlap |

## Shared-file overlap key (peer comparisons on `star/next` only)

- **A** = `star/agent.py` — #109, #147, #185, #249, #270. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **D** = `star/desktop_core.py` — #109, #147, #173, #181, #185, #249, #270, #274, #283, #286, #289. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **S** = `star/react_shell.py` — #109, #147, #185, #270, #266, #283, #289. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **F** = `frontend/src/Desktop.tsx` — #109, #254, #283. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **T** = `frontend/src/types.ts` — #173, #181, #283. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **C** = `frontend/src/Composer.tsx` — #109, #294. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **G** = `star/doc_grounding.py` — #147, #173, #181, #185, #249. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **I** = `star/intelligence.py` — #68, #105, #233, #268, #277, #292. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **K** = `star/skill_packs/__init__.py` — #68, #233, #284. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **ARCH** = `star/architecture_pipeline.py`, `star/architecture_quality.py`, `scripts/blender_building.py` — #68, #233. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **LU** = `star/luau_run_client.py and server/knowledge/starkb/luaurun.py` — #173, #181. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **LAB** = `star/studio_lab.py and tests/test_studio_lab.py` — #268, #277, #292. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **PAR** = `star/studio_lab_parallel.py` — #277, #292. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **PRE** = `star/roblox_project_preflight.py and tests/test_roblox_project_preflight.py` — #279, #280, #293. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **TC** = `tests/test_agent_tool_catalogue.py` — #233, #268, #271, #277, #292. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **BOT** = `star/discord_bot/bot.py` — #281, #283, #287. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **CONF** = `star/discord_bot/local_config.py` — #281, #287. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **INS** = `installer/STAR.iss` — #217, #254. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **BUILD** = `scripts/build_windows.ps1` — #254, #295. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **VOICE** = `tests/test_voice_brain.py` — #288, #294. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.
- **UI** = `frontend/src/IntegrationPanels.tsx` — #173, #181. Current open PRs share at least one named file; these are potential conflicts, not confirmed textual collisions.

## Replacement, hold and dependency evidence
- **#68 -> #233:** #233 body states `Replaces #68`; do not start a third replacement. #233 itself reports `dirty` mergeability.
- **#147 -> #185:** #185 body states `Replaces #147` and `supersedes #184`; #147 is an open, older draft.
- **#173 and #181** both say `Replaces #145`; neither description proves that #181 replaces #173. Compare the two before recommending any closure.
- **#240** states `replaces #224`, **#244** states `replaces #241`, and **#245** states `replaces #242`; those named older PRs are not open.
- **#268 -> #277 -> #292** is a stated *stack*, not a replacement chain; review/install stages in dependency order and never merge this report.
- **#244, #245, #252:** Python/Windows/React checks passed but protected closure **FAILED** on their final heads; needs genuine owner-led policy/PR decision, not a guard bypass.
- **#148:** latest React check failed while Linux passed; no final-head Windows check was present. Real-model curated-example yield remains unproven by the draft's own report.
- **#152:** a separate main-base integration PR, not a normal star/next feature; only the lead should decide release/integration sequencing.

## Legacy leftover verification
- The listed older PRs **#234, #236, #241, #235, #238, #242, #223, #227** were each queried from the GitHub pull API and are **closed, unmerged**; none belongs in the 46-row open inventory.
- **#240** remains open and draft (clean at this snapshot), and already replaces #224. Do not classify it as closed merely because it appeared in an old leftovers list.
- The requested `docs/agents/chatgpt-autopilot-v3.md` was **not found** at either `star/next` or `main`; the specific note could not be read. The explicit leftovers in the task were instead independently checked against their PR metadata.

## Next step for the lead
Review #276's timing-test edge case, then #268 and #266 before the stacked Studio Lab drafts. Resolve protected-evaluation holds through the owner rather than changing guards. No PR was merged, closed, rebased, or edited by this document.
