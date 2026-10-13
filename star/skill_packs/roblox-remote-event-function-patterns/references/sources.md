# Sources for roblox-remote-event-function-patterns

Reviewed on 2026-10-12 against official Roblox Creator Documentation. This is original guidance; no Studio execution or knowledge-service /api-lookup was performed.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Validate client arguments, permissions and per-player rate limits | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| S2 | RemoteEvent FireServer, FireClient and OnServerEvent | https://create.roblox.com/docs/scripting/events/remote |
| S3 | RemoteFunction InvokeServer, OnServerInvoke and InvokeClient cautions | https://create.roblox.com/docs/reference/engine/classes/RemoteFunction |
| S4 | Players.PlayerRemoving cleanup | https://create.roblox.com/docs/reference/engine/classes/Players |
| S1 | Anchored target parts and position | https://create.roblox.com/docs/reference/engine/classes/BasePart |
| S2 | RemoteEvent class members | https://create.roblox.com/docs/reference/engine/classes/RemoteEvent |

These are illustrations of narrow patterns rather than a complete networking framework. STAR's Luau linter is an offline heuristic, not an engine test.
