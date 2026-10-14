# Sources for roblox-luau-specs

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. Examples 1 to 3 were also executed with the standalone Luau 0.691 CLI (example 3 with its two Roblox lookup lines replaced by a relative require): all cases passed, and a deliberately broken expectation failed with the caller's line number. They have not run in a live Roblox Studio session.

The official documentation does not describe TestEZ; the describe/it/expect harness in example 2 is self-contained and makes no claim about any external framework's API. Rules 2 and 6 describe STAR's own conventions (STAR's spec runner executes a returned table of named cases in standalone Luau).

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | ModuleScripts return reusable code; scripts require them | https://create.roblox.com/docs/scripting/module |
| S2 | Luau type checking, strict mode and exported types | https://create.roblox.com/docs/luau/type-checking |
| S3 | os.clock | https://create.roblox.com/docs/reference/engine/libraries/os |
| S4 | task library (not used inside specs) | https://create.roblox.com/docs/reference/engine/libraries/task |
| S5 | Validate client input including NaN | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| S6 | error, assert and pcall | https://create.roblox.com/docs/reference/engine/globals/LuaGlobals |
| S6 | typeof | https://create.roblox.com/docs/reference/engine/globals/RobloxGlobals |
| S7 | Random.new with a seed | https://create.roblox.com/docs/reference/engine/datatypes/Random |
| S8 | Studio testing modes: Server & Clients, network simulation, StudioTestService | https://create.roblox.com/docs/studio/testing-modes |
| S9 | ReplicatedStorage holds shared modules | https://create.roblox.com/docs/reference/engine/classes/ReplicatedStorage |
| S10 | math.clamp | https://create.roblox.com/docs/reference/engine/libraries/math |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
