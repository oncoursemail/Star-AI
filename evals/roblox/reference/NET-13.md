```luau
local Wallet = {}

function Wallet.add(store: any, key: string, delta: number): (boolean, number?)
	local valid = type(delta) == "number" and delta == delta and delta ~= math.huge and delta ~= -math.huge and delta == math.floor(delta)
	local newBalance: number? = nil
	local ok = pcall(function()
		store:UpdateAsync(key, function(old)
			if not valid then
				return nil
			end
			local result = (old or 0) + delta
			if result < 0 then
				return nil
			end
			newBalance = result
			return result
		end)
	end)
	if not ok or newBalance == nil then
		return false, nil
	end
	return true, newBalance
end

return Wallet
```
