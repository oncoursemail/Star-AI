--!strict
local Economy = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("Economy"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

local function richState()
	return Economy.fromSaved({ cash = 20_000, owned = { starter_dropper = true } })
end

local function fullState()
	local state = richState()
	for _, item in ipairs(Economy.all()) do
		if item.id ~= Economy.STARTER_ID then
			local nextState, reason = Economy.buy(state, item.id)
			expect(reason == "ok" and nextState ~= nil, "expected ordered purchase of " .. item.id)
			if nextState == nil then
				error("purchase returned no state")
			end
			state = nextState
		end
	end
	return state
end

return {
	["starter is owned and opens the first purchase"] = function()
		local state = Economy.newState()
		expect(state.cash == 0 and state.owned.starter_dropper, "starter should be free")
		local nextItem = Economy.nextUnlock(state)
		expect(nextItem ~= nil and nextItem.id == "quick_dropper", "only the quick dropper unlocks first")
	end,
	["purchase rejects client supplied price and unknown ids"] = function()
		local state = richState()
		expect(Economy.buy(state, { id = "quick_dropper", price = 0 }) == nil, "only ids are accepted")
		local nextState, reason = Economy.buy(state, "free_everything")
		expect(nextState == nil and reason == "unknown_item", "unknown ids are refused")
	end,
	["prerequisites are enforced before wealth"] = function()
		local nextState, reason = Economy.buy(richState(), "star_dropper")
		expect(nextState == nil and reason == "locked", "cannot skip preceding droppers")
	end,
	["insufficient cash never changes ownership"] = function()
		local original = Economy.newState()
		local nextState, reason = Economy.buy(original, "quick_dropper")
		expect(nextState == nil and reason == "not_enough_cash", "server should check configured price")
		expect(original.cash == 0 and not original.owned.quick_dropper, "failed buy must be pure")
	end,
	["successful purchase debits once without mutating its input"] = function()
		local original = richState()
		local purchased, reason = Economy.buy(original, "quick_dropper")
		expect(reason == "ok" and purchased ~= nil, "first purchase should succeed")
		if purchased == nil then
			error("missing purchased state")
		end
		expect(purchased.cash == 19_900 and purchased.owned.quick_dropper, "configured price should be charged")
		expect(original.cash == 20_000 and not original.owned.quick_dropper, "input must remain unchanged")
		local again, why = Economy.buy(purchased, "quick_dropper")
		expect(again == nil and why == "already_owned", "duplicate purchases cannot charge twice")
	end,
	["collection accepts only unlocked droppers and scales with rebirths"] = function()
		local state = Economy.newState()
		expect(Economy.collect(state, "star_dropper") == nil, "locked dropper cannot credit")
		expect(Economy.collect(state, "invented") == nil, "unknown dropper cannot credit")
		local paid, reason = Economy.collect(state, "starter_dropper")
		expect(paid ~= nil and reason == "ok", "owned dropper should earn")
		if paid == nil then
			error("missing collection state")
		end
		expect(paid.cash == 10 and state.cash == 0, "collect should add base income purely")
		expect(Economy.income("starter_dropper", 2) == 20, "rebirth multiplier should affect income")
	end,
	["rebirth requires last purchase and price then resets progression"] = function()
		expect(Economy.rebirth(richState()) == nil, "cash alone cannot rebirth")
		local state = fullState()
		expect(Economy.canRebirth(state), "final purchase and cash should unlock rebirth")
		local reborn, reason = Economy.rebirth(state)
		expect(reborn ~= nil and reason == "ok", "qualified rebirth should work")
		if reborn == nil then
			error("missing reborn state")
		end
		expect(reborn.cash == 0 and reborn.rebirths == 1, "cash resets and rebirths increment")
		expect(reborn.owned.starter_dropper and not reborn.owned.quick_dropper, "only starter stays owned")
		expect(Economy.multiplier(reborn.rebirths) == 1.5, "rebirth improves income")
		expect(Economy.rebirthPrice(1) > Economy.rebirthPrice(0), "future rebirth costs more")
		expect(state.owned.star_dropper and state.rebirths == 0, "rebirth is pure")
	end,
	["loading repairs malformed and out-of-order saved ownership"] = function()
		local state = Economy.fromSaved({
			cash = -55,
			rebirths = 1.9,
			owned = { star_dropper = true, starter_dropper = false, unknown = true },
		})
		expect(state.cash == 0 and state.rebirths == 1, "numeric values should be sanitized")
		expect(state.owned.starter_dropper and not state.owned.star_dropper, "orphan purchase should be discarded")
		expect(not state.owned.unknown, "unknown item cannot be restored")
		expect(Economy.fromSaved({ cash = math.huge }).cash == 0, "invalid cash should be sanitized")
	end,
	["catalog returns copies and part limit is bounded"] = function()
		local items = Economy.all()
		expect(#items == 4 and items[1].id == Economy.STARTER_ID, "catalog order must be stable")
		items[2].price = 0
		local quick = Economy.get("quick_dropper")
		expect(quick ~= nil and quick.price == 100, "shared price cannot be overwritten by a caller")
		expect(Economy.MAX_ACTIVE_DROPS > 0 and Economy.MAX_ACTIVE_DROPS <= 64, "limit must be small")
	end,
}
