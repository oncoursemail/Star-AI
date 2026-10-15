# Sources for roblox-purchases-badges

Reviewed against official Creator Hub on 2026-10-13; original guidance and illustrative Luau (not verified in Roblox Studio). The current BadgeService reference deprecates AwardBadge; AwardBadgeAsync is preferred.

| ID | Rules and supported API claim | Official source |
|---|---|---|
| S1 | 1, 2, 3, 5, 7: ProcessReceipt, product prompts and non-authoritative finished event | https://create.roblox.com/docs/production/monetization/developer-products |
| S2 | 2: MarketplaceService.ProcessReceipt callback and signature | https://create.roblox.com/docs/reference/engine/classes/MarketplaceService |
| S3 | 3, 4, 5: durable PurchaseId and reward idempotency | https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing |
| S4 | 1, 8: passes, ownership checks and pass prompts | https://create.roblox.com/docs/production/monetization/passes |
| S5 | 4, 6: GlobalDataStore.UpdateAsync transformation | https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore |
| S6 | 9: AwardBadge deprecated; UserHasBadgeAsync and AwardBadgeAsync | https://create.roblox.com/docs/reference/engine/classes/BadgeService |
| S7 | 10: case-sensitive leaderstats Folder and value objects | https://create.roblox.com/docs/players/leaderboards |
| S8 | 2: PurchaseGranted and NotProcessedYet enum | https://create.roblox.com/docs/reference/engine/enums/ProductPurchaseDecision |
| S9 | 6: bounded retries and uncertain write outcomes | https://create.roblox.com/docs/cloud-services/data-stores/best-practices |
| S10 | 1, 3: server authority for client-supplied requests | https://create.roblox.com/docs/scripting/security/client-server-boundary |
