```luau
local MarketplaceService = game:GetService("MarketplaceService")
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")

local receipts = DataStoreService:GetDataStore("Receipts")
local balances = DataStoreService:GetDataStore("Balances")
local PRODUCTS = { [1111] = 100, [2222] = 500 }

MarketplaceService.ProcessReceipt = function(info)
	local coins = PRODUCTS[info.ProductId]
	if coins == nil then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local key = tostring(info.PlayerId) .. "_" .. tostring(info.PurchaseId)
	local granted = false
	local ok = pcall(function()
		receipts:UpdateAsync(key, function(old)
			if old ~= nil then
				return old
			end
			granted = true
			return true
		end)
	end)
	if not ok then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	if granted then
		local saved = pcall(function()
			balances:UpdateAsync(tostring(info.PlayerId), function(old)
				return (old or 0) + coins
			end)
		end)
		if not saved then
			pcall(function()
				receipts:RemoveAsync(key)
			end)
			return Enum.ProductPurchaseDecision.NotProcessedYet
		end
	end
	return Enum.ProductPurchaseDecision.PurchaseGranted
end
```
