---
name: roblox-purchases-badges
description: Server-safe Roblox developer product receipts, game-pass ownership, BadgeService and leaderstats patterns.
---
# roblox-purchases-badges
## When to use
For Roblox purchases, game passes, badges and leaderboard stats. For prices and fairness see `design-economy-and-fair-monetisation`; for client trust see `roblox-secure-remotes`. API mechanics only; this pack is OFF by default.

## Ten concrete rules
1. Grant paid rewards on the server. `PromptProductPurchase` and `PromptGamePassPurchase` only show prompts, not authority to award. [S1][S4]
2. Set **one** `MarketplaceService.ProcessReceipt` callback for the game. It returns `Enum.ProductPurchaseDecision.PurchaseGranted` or `NotProcessedYet`. [S1][S2][S8]
3. Resolve `PlayerId`; allowlist `ProductId` server-side; require a nonempty `PurchaseId`. Missing player, invalid receipt or unknown product => `NotProcessedYet`. [S1][S3]
4. Persist grant and `PurchaseId` in **one** `GlobalDataStore:UpdateAsync` transform; its callback must not yield or perform external side effects, and may re-run. [S3][S5]
5. A repeated `PurchaseId` returns the unchanged record and `PurchaseGranted` with **no second grant**. If persistence fails, return `NotProcessedYet`. [S1][S3]
6. Wrap writes in `pcall`, retry transient failures in order with bounded backoff; failed responses can have unknown write outcomes, so retry idempotently. [S5][S9]
7. `PromptProductPurchaseFinished` does **not** establish a granted product; use `ProcessReceipt` to grant consumables. [S1]
8. Protect `UserOwnsGamePassAsync(userId, passId)` with `pcall`, cache verified ownership per-player only while valid, clear it on departure. `PromptGamePassPurchaseFinished` is a prompt result; for high-value access refresh the ownership query rather than trusting the event alone. [S4]
9. Use `BadgeService:UserHasBadgeAsync` and `BadgeService:AwardBadgeAsync` in `pcall` after server eligibility checks. The older `AwardBadge` method is deprecated. [S6]
10. Create a `Folder` named exactly `leaderstats` under each Player; put `IntValue`/`NumberValue` stats inside. Display stats reflect trusted server state, not proof of payment. [S7]

## Strict Luau skeleton
```luau
--!strict
-- ServerScriptService/Purchases.server.luau. Replace example product ID.
local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("PurchaseProfilesV1")
local productCoins: {[number]: number} = {[10101] = 100}
type Record = {Coins: number, ReceiptIds: {[string]: boolean}}

local function processReceipt(receipt): Enum.ProductPurchaseDecision
    local player = Players:GetPlayerByUserId(receipt.PlayerId)
    local coins = productCoins[receipt.ProductId]
    local purchaseId = receipt.PurchaseId
    if not player or not coins or typeof(purchaseId) ~= "string" or #purchaseId == 0 then
        return Enum.ProductPurchaseDecision.NotProcessedYet
    end
    for attempt = 1, 3 do
        local ok, saved = pcall(function()
            return store:UpdateAsync("Player_" .. player.UserId, function(old)
                if old == nil then old = {Coins = 0, ReceiptIds = {}} end
                if typeof(old) ~= "table" or typeof(old.Coins) ~= "number"
                    or typeof(old.ReceiptIds) ~= "table" then return nil end
                if old.ReceiptIds[purchaseId] then return old end
                local receiptIds = table.clone(old.ReceiptIds)
                receiptIds[purchaseId] = true
                local nextRecord = table.clone(old)
                nextRecord.Coins = old.Coins + coins
                nextRecord.ReceiptIds = receiptIds
                return nextRecord -- Grant and PurchaseId in ONE write.
            end)
        end)
        if ok then
            if typeof(saved) ~= "table" then
                return Enum.ProductPurchaseDecision.NotProcessedYet
            end
            local stats = player:FindFirstChild("leaderstats")
            local display = stats and stats:FindFirstChild("Coins")
            if display and display:IsA("IntValue") then display.Value = saved.Coins end
            return Enum.ProductPurchaseDecision.PurchaseGranted
        end
        if attempt < 3 then task.wait(math.min(2 ^ attempt, 4)) end
    end
    return Enum.ProductPurchaseDecision.NotProcessedYet
end
MarketplaceService.ProcessReceipt = processReceipt
```
The product ID is illustrative. Load saved profiles and hydrate leaderstats separately; this is **not** a complete session-locking or data-migration system. Do not prune receipt history without a durable replay ledger, because old receipts can be delivered again.

## Prompt and awards
- A LocalScript may call `MarketplaceService:PromptProductPurchase(player, productId)` or `MarketplaceService:PromptGamePassPurchase(player, passId)`; never grant directly from the prompt. [S1][S4]
- Handle pass prompt completion server-side, refresh `UserOwnsGamePassAsync` as appropriate, and invalidate temporary caches when membership changes. [S4]
- Before a badge award, check `GetBadgeInfoAsync` for enabled state if applicable; shield `UserHasBadgeAsync` and `AwardBadgeAsync` calls with `pcall`. [S6]

## Three common mistakes
1. Granting consumables from a prompt-finished event.
2. Writing the grant and PurchaseId in separate requests or applying a second grant on retry.
3. Using a client-owned leaderboard value or a pass prompt as a receipt.

## Checklist
- [ ] One receipt handler; valid PlayerId, ProductId, PurchaseId.
- [ ] Same receipt twice grants exactly once; retries are ordered and bounded.
- [ ] Failures defer receipts; never acknowledge an unconfirmed write.
- [ ] Pass and badge checks are server-owned and protected with pcall.
- [ ] Test rejoin, duplicate delivery, malformed stored records and two-server races.

## Sources
See [references/sources.md](references/sources.md) for [S1]–[S10]. This sample is illustrative, not Studio tested.
