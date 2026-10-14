# Luau checker false-positive corpus — first measured CI run

## Reproducible sources

- 37 original non-spec `.luau` files from `examples/roblox/` and
  `examples/roblox-templates/`, and 9 authored Luau code fences from
  three maintained service skill packs = **46 snippets**, read in-place by
  `tests/test_luau_checker_false_positives.py`.
- Each snippet is checked with `lint(external=False, safety_checks=True,
  server_security=True)`, `inspect_safety`, `lint_server_trust`, and
  `check_luau_api` with the deliberately **small** checked-in API dump.
  The combined linter duplicates safety findings by design.
- Source identities, checker, rule and line are emitted in failing CI.
  All accepted advisories are explicitly allowlisted by
  `(checker, file, rule)` with a per-entry verdict and reason.

## Baseline and targeted remediation

First GitHub Linux Python workflow on commit `318f12e7` failed as expected:
**108 unclassified findings** across 46 source snippets, measured from the
failing test output (not inferred from source patterns).

| Checker entrypoint | Before fixes | Expected after narrow fixes |
| --- | ---: | ---: |
| `luau_lint_all_modes` | 15 | 7 |
| `luau_safety` | 1 | 1 |
| `luau_server_security` | 0 | 0 |
| `roblox_api_checker` (small fixture) | 92 | 92 |
| **Total observations, duplicates included** | **108** | **100** |

Seven `loop-connection` advisories stem from one-time finite `for`
registration loops (including cases in which the heuristic incorrectly
extended the loop past its end). The linter now limits its repeat-leak
warning to `while` and `repeat` loops. One `touched-debounce` warning
on the explicitly guarded `KillService` was removed by acknowledging
a last-hit map used together with a cooldown constant and conditional.

**Confirmed small-scope false positives:** 8 before, 0 after *if*
the follow-up GitHub checker confirms the two fixes. Rate:
`8 / 46 = 0.1739` findings per snippet initially; anticipated
`0 / 46 = 0` after. This is not a model correctness probability.

The remaining 92 API advisories are **not** counted as confirmed
engine errors or confirmed false positives: the tiny API fixture does
not contain all genuine Roblox classes, services, members or inherited
members. They are accepted only as *fixture-limited noise* pending a
full current Studio API dump. Six touch-handler advisories rely on
a different server-owned helper or idempotent state guard, beyond
this lexical scanner's local proof; they remain explicitly classified
as accepted noise rather than silently suppressed. Two observations
of a genuine chained server `WaitForChild` without timeouts (one
in combined lint, one in safety) remain true-positive advisories.

## Per-file, per-rule accepted findings

| Checker | Source | Rule | Verdict | Reason |
| --- | --- | --- | --- | --- |
| luau_lint_all_modes | `examples/roblox-templates/obby/ServerScriptService/CheckpointService.luau` | `touched-debounce` | accepted_noise | Touched callback delegates deduplication or rate guards to another server-owned function; lexical evidence incomplete. |
| luau_lint_all_modes | `examples/roblox-templates/obby/ServerScriptService/FinishService.luau` | `touched-debounce` | accepted_noise | Touched callback delegates deduplication or rate guards to another server-owned function; lexical evidence incomplete. |
| luau_lint_all_modes | `examples/roblox-templates/tycoon/ServerScriptService/Plots.luau` | `touched-debounce` | accepted_noise | Drop ownership is consumed before callback; one-shot state acts as idempotency guard. |
| luau_lint_all_modes | `examples/roblox-templates/tycoon/ServerScriptService/Tycoon.server.luau` | `server-waitforchild-chain` | true_positive | Chained WaitForChild lacks explicit bounded timeouts; flag remains actionable. |
| luau_lint_all_modes | `examples/roblox/obby/ServerScriptService/ObbyServer.server.luau` | `touched-debounce` | accepted_noise | Touched callback delegates deduplication or rate guards to another server-owned function; lexical evidence incomplete. |
| luau_safety | `examples/roblox-templates/tycoon/ServerScriptService/Tycoon.server.luau` | `server-waitforchild-chain` | true_positive | Chained WaitForChild lacks explicit bounded timeouts; flag remains actionable. |
| roblox_api_checker | `examples/roblox-templates/obby/ServerScriptService/CourseBuilder.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/obby/ServerScriptService/CourseBuilder.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/obby/ServerScriptService/PlayerData.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/obby/ServerScriptService/PlayerData.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/obby/ServerScriptService/PlayerData.luau` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `examples/roblox-templates/obby/ServerScriptService/TouchValidation.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/obby/StarterPlayer/StarterPlayerScripts/StageHud.client.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/rounds/ServerScriptService/ArenaFactory.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/rounds/ServerScriptService/ArenaFactory.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/rounds/ServerScriptService/RoundServer.server.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/rounds/ServerScriptService/RoundServer.server.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/rounds/ServerScriptService/RoundServer.server.luau` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `examples/roblox-templates/rounds/StarterPlayer/StarterPlayerScripts/RoundHud.client.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/simulator/ServerScriptService/Simulator.server.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/simulator/ServerScriptService/Simulator.server.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/simulator/ServerScriptService/Simulator.server.luau` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `examples/roblox-templates/simulator/ServerScriptService/SimulatorService.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/simulator/StarterPlayer/StarterPlayerScripts/Simulator.client.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/simulator/StarterPlayer/StarterPlayerScripts/Simulator.client.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/PlayerData.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/PlayerData.luau` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/Plots.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/Plots.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/Tycoon.server.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/Tycoon.server.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox-templates/tycoon/ServerScriptService/Tycoon.server.luau` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `examples/roblox-templates/tycoon/StarterPlayer/StarterPlayerScripts/Hud.client.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox-templates/tycoon/StarterPlayer/StarterPlayerScripts/Hud.client.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox/obby/ServerScriptService/ObbyServer.server.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox/obby/ServerScriptService/ObbyServer.server.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox/shop/ServerScriptService/ShopServer.server.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox/shop/ServerScriptService/ShopServer.server.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `examples/roblox/shop/ServerScriptService/ShopServer.server.luau` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `examples/roblox/shop/StarterPlayer/StarterPlayerScripts/ShopClient.client.luau` | `unknown-class` | accepted_noise | Small test API dump omits this Roblox class; requires full local Studio dump. |
| roblox_api_checker | `examples/roblox/shop/StarterPlayer/StarterPlayerScripts/ShopClient.client.luau` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `star/skill_packs/roblox-datastore-service-patterns/SKILL.md#luau-1` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `star/skill_packs/roblox-datastore-service-patterns/SKILL.md#luau-2` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `star/skill_packs/roblox-datastore-service-patterns/SKILL.md#luau-3` | `unknown-service` | accepted_noise | Small test API dump omits this Roblox service; verify with full local dump. |
| roblox_api_checker | `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md#luau-2` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |
| roblox_api_checker | `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md#luau-3` | `unknown-member` | accepted_noise | Small API dump lacks this member/inherited type; receiver and real API remain unverified. |

No source script is run in CI. Existing checkers are heuristic and
standalone Luau cannot verify Roblox engine semantics; claim only
reproducible offline observations. Native analyzer and Studio runs were
not used for the corpus.
