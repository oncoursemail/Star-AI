# Sources for roblox-marketplace-purchases

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated; MarketplaceService.GetProductInfo is tagged Deprecated and GetProductInfoAsync is not). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session and no real purchase was made.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | ProcessReceipt guarantees, retries, parallel servers, non-deterministic order, PurchaseId and receipt fields | https://create.roblox.com/docs/reference/engine/classes/MarketplaceService |
| S2 | Developer products: grant in ProcessReceipt, never in PromptProductPurchaseFinished | https://create.roblox.com/docs/production/monetization/developer-products |
| S3 | Purchase handling: record PurchaseId, save before PurchaseGranted, atomic update without session locking | https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing |
| S4 | GlobalDataStore UpdateAsync transform and cancel by returning nil | https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore |
| S5 | Players GetPlayerByUserId and PlayerRemoving | https://create.roblox.com/docs/reference/engine/classes/Players |
| S6 | Passes: UserOwnsGamePassAsync in pcall, PromptGamePassPurchaseFinished handled on the server | https://create.roblox.com/docs/production/monetization/passes |
| S7 | ProductPurchaseDecision PurchaseGranted and NotProcessedYet | https://create.roblox.com/docs/reference/engine/enums/ProductPurchaseDecision |
| S8 | Server-side validation of shop purchases | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| S9 | Remote functions and OnServerInvoke | https://create.roblox.com/docs/scripting/events/remote |
| S10 | DataStoreService GetDataStore | https://create.roblox.com/docs/reference/engine/classes/DataStoreService |
| S11 | ReplicatedStorage | https://create.roblox.com/docs/reference/engine/classes/ReplicatedStorage |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
