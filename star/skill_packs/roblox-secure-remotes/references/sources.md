# Sources for roblox-secure-remotes

Official Roblox Creator Documentation (CC-BY-4.0), checked against the STAR Knowledge index (creator-docs af5f853).

| Claim in the skill | Documentation page |
|---|---|
| Every piece of data from a client must be validated by the server; context/permission, type and value validation; NaN and inf are valid numbers, use math.isfinite() | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| Check an Instance argument's class and location, not only its type; avoid remotes that take arbitrary paths | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| Server-side rate limiting, token bucket; never rely only on a client-side limit | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| Remote events and callbacks, delivery guarantees, argument limitations | https://create.roblox.com/docs/scripting/events/remote |
| RemoteFunction:InvokeClient risks | https://create.roblox.com/docs/reference/engine/classes/RemoteFunction |
| UnreliableRemoteEvent: payloads over 1000 bytes are dropped; about 500 requests per second per client | https://create.roblox.com/docs/reference/engine/classes/UnreliableRemoteEvent |
| MarketplaceService.ProcessReceipt and Enum.ProductPurchaseDecision | https://create.roblox.com/docs/reference/engine/classes/MarketplaceService and https://create.roblox.com/docs/production/monetization/developer-products |

API names verified with the knowledge service /api-lookup on 2026-10-10: RemoteEvent, UnreliableRemoteEvent, RemoteFunction.InvokeClient,
MarketplaceService.ProcessReceipt, Players.PlayerRemoving, Instance:IsA, Humanoid:TakeDamage, Workspace:GetServerTimeNow.
math.isfinite is quoted from the client-server-boundary page and exists in the server's Luau VM.
