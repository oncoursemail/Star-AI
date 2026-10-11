# Sources for game-inventory

Official Roblox Creator Documentation. Engine APIs in the code skeleton are documented by these pages; example-specific schemas, timings, prices and logic are design choices, not Roblox APIs.

- https://create.roblox.com/docs/reference/engine/classes/Tool
- https://create.roblox.com/docs/reference/engine/classes/Backpack
- https://create.roblox.com/docs/reference/engine/classes/ServerStorage
- https://create.roblox.com/docs/reference/engine/classes/RemoteEvent
- https://create.roblox.com/docs/scripting/security/client-server-boundary
- https://create.roblox.com/docs/cloud-services/data-stores
- https://create.roblox.com/docs/reference/engine/classes/Instance
- https://create.roblox.com/docs/reference/engine/classes/Players

See also: https://create.roblox.com/docs/scripting/security/client-server-boundary and https://create.roblox.com/docs/cloud-services/data-stores for validation and persistence guidance.

Shared API names RemoteEvent, DataStoreService:GetDataStore, GlobalDataStore:UpdateAsync and Players.PlayerRemoving (recorded in `roblox-secure-remotes` and `roblox-datastore-safety`) were verified with the knowledge service /api-lookup in the existing packs' source records dated 2026-10-10 or 2026-10-11. Other API names in this new pack are referenced against the linked Creator Documentation; they have **not** been independently queried against /api-lookup for this new pack.
