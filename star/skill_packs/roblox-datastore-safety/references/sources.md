# Sources for roblox-datastore-safety

Official Roblox Creator Documentation (CC-BY-4.0), checked against the STAR Knowledge index (creator-docs af5f853).

| Claim in the skill | Documentation page |
|---|---|
| Retry transient failures; prefer UpdateAsync over SetAsync; reduce and distribute requests | https://create.roblox.com/docs/cloud-services/data-stores/best-practices |
| UpdateAsync reads and writes a key atomically and can abandon the write by returning nil; session locking with a lock id in the key's metadata | https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing |
| Request queues of 30; dropped requests fail with codes 301-306; throttling by request type | https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits |
| Per-key size limit (4,194,304 characters) | https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits |
| DataModel:BindToClose: bound functions run in parallel, the server waits 30 seconds | https://create.roblox.com/docs/reference/engine/classes/DataModel |
| Data stores overview, set versus update | https://create.roblox.com/docs/cloud-services/data-stores |
| ProcessReceipt and purchase decisions | https://create.roblox.com/docs/production/monetization/developer-products |

API names verified with the knowledge service /api-lookup on 2026-10-10: DataStoreService:GetDataStore, GlobalDataStore:UpdateAsync,
DataStoreService:GetRequestBudgetForRequestType, DataModel:BindToClose, Players.PlayerRemoving, MarketplaceService.ProcessReceipt.
