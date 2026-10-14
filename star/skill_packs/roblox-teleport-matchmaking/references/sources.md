# Sources for roblox-teleport-matchmaking

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated; TeleportService.Teleport and TeleportService.ReserveServer are tagged Deprecated, TeleportAsync and ReserveServerAsync are not). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. Teleports cannot be playtested in Studio; these examples have not run in a live game.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Teleport guide: server-only TeleportAsync, groups, reserved servers, teleport data visibility, pcall and retries, TeleportInitFailed, access control | https://create.roblox.com/docs/projects/teleport |
| S2 | TeleportService TeleportAsync, deprecated Teleport, TeleportInitFailed | https://create.roblox.com/docs/reference/engine/classes/TeleportService |
| S3 | TeleportOptions ShouldReserveServer, ReservedServerAccessCode and SetTeleportData | https://create.roblox.com/docs/reference/engine/classes/TeleportOptions |
| S4 | TeleportResult values such as Flooded, Failure and Unauthorized | https://create.roblox.com/docs/reference/engine/enums/TeleportResult |
| S5 | Player GetJoinData, SourcePlaceId, TeleportData and its security limits | https://create.roblox.com/docs/reference/engine/classes/Player |
| S6 | Memory store queues: GetQueue, invisibility timeout, AddAsync, ReadAsync, RemoveAsync, pcall | https://create.roblox.com/docs/cloud-services/memory-stores/queue |
| S7 | Memory store limits and short expirations | https://create.roblox.com/docs/cloud-services/memory-stores |
| S8 | DataModel PrivateServerId and PrivateServerOwnerId (0 for reserved servers) | https://create.roblox.com/docs/reference/engine/classes/DataModel |
| S9 | Players GetPlayerFromCharacter and PlayerRemoving | https://create.roblox.com/docs/reference/engine/classes/Players |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
