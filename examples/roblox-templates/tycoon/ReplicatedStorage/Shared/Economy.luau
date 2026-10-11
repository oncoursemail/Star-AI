--!strict
-- Pure economy rules shared for display and server-side decisions. No instances or network calls.
export type Item = {
	id: string,
	name: string,
	price: number,
	income: number,
	interval: number,
	prerequisite: string?,
}
export type State = {
	cash: number,
	rebirths: number,
	owned: { [string]: boolean },
}

local Economy = {}
Economy.MAX_ACTIVE_DROPS = 36
Economy.STARTER_ID = "starter_dropper"

local MAX_CASH = 1_000_000_000_000
local MAX_REBIRTHS = 10_000
local ITEMS: { Item } = {
	{ id = "starter_dropper", name = "Starter Dropper", price = 0, income = 10, interval = 2.5 },
	{ id = "quick_dropper", name = "Quick Dropper", price = 100, income = 25, interval = 2, prerequisite = "starter_dropper" },
	{ id = "steel_dropper", name = "Steel Dropper", price = 500, income = 60, interval = 1.5, prerequisite = "quick_dropper" },
	{ id = "star_dropper", name = "Star Dropper", price = 1800, income = 140, interval = 1, prerequisite = "steel_dropper" },
}
local BY_ID: { [string]: Item } = {}
for _, item in ipairs(ITEMS) do
	BY_ID[item.id] = item
end

local function integer(value: any, maximum: number): number
	if type(value) ~= "number" or value ~= value or value == math.huge or value == -math.huge then
		return 0
	end
	return math.clamp(math.floor(value), 0, maximum)
end

local function copyState(state: State): State
	local owned: { [string]: boolean } = {}
	for id, present in pairs(state.owned) do
		if present then
			owned[id] = true
		end
	end
	return { cash = state.cash, rebirths = state.rebirths, owned = owned }
end

local function copyItem(item: Item): Item
	return {
		id = item.id,
		name = item.name,
		price = item.price,
		income = item.income,
		interval = item.interval,
		prerequisite = item.prerequisite,
	}
end

function Economy.get(itemId: string): Item?
	local item = BY_ID[itemId]
	return if item then copyItem(item) else nil
end

function Economy.all(): { Item }
	local items: { Item } = {}
	for _, item in ipairs(ITEMS) do
		table.insert(items, copyItem(item))
	end
	return items
end

function Economy.newState(): State
	return { cash = 0, rebirths = 0, owned = { starter_dropper = true } }
end

function Economy.fromSaved(value: any): State
	if type(value) ~= "table" then
		return Economy.newState()
	end
	local state: State = {
		cash = integer(value.cash, MAX_CASH),
		rebirths = integer(value.rebirths, MAX_REBIRTHS),
		owned = { starter_dropper = true },
	}
	if type(value.owned) == "table" then
		for _, item in ipairs(ITEMS) do
			if item.id ~= Economy.STARTER_ID and value.owned[item.id] == true
				and (item.prerequisite == nil or state.owned[item.prerequisite] == true) then
				state.owned[item.id] = true
			end
		end
	end
	return state
end

function Economy.serialize(state: State): State
	return Economy.fromSaved(state)
end

function Economy.multiplier(rebirths: number): number
	return 1 + integer(rebirths, MAX_REBIRTHS) * 0.5
end

function Economy.income(itemId: string, rebirths: number): number
	local item = BY_ID[itemId]
	if not item then
		return 0
	end
	return math.floor(item.income * Economy.multiplier(rebirths))
end

function Economy.rebirthPrice(rebirths: number): number
	return 4000 + integer(rebirths, MAX_REBIRTHS) * 1500
end

function Economy.canBuy(state: State, itemId: string): boolean
	local item = BY_ID[itemId]
	return item ~= nil and not state.owned[itemId]
		and (item.prerequisite == nil or state.owned[item.prerequisite] == true)
end

function Economy.nextUnlock(state: State): Item?
	for _, item in ipairs(ITEMS) do
		if Economy.canBuy(state, item.id) then
			return copyItem(item)
		end
	end
	return nil
end

function Economy.buy(state: State, itemId: any): (State?, string)
	if type(itemId) ~= "string" then
		return nil, "bad_request"
	end
	local item = BY_ID[itemId]
	if not item then
		return nil, "unknown_item"
	end
	if state.owned[itemId] then
		return nil, "already_owned"
	end
	if not Economy.canBuy(state, itemId) then
		return nil, "locked"
	end
	if state.cash < item.price then
		return nil, "not_enough_cash"
	end
	local nextState = copyState(state)
	nextState.cash -= item.price
	nextState.owned[itemId] = true
	return nextState, "ok"
end

function Economy.collect(state: State, itemId: string): (State?, string)
	if not BY_ID[itemId] or not state.owned[itemId] then
		return nil, "not_owned"
	end
	local nextState = copyState(state)
	nextState.cash = math.min(MAX_CASH, state.cash + Economy.income(itemId, state.rebirths))
	return nextState, "ok"
end

function Economy.canRebirth(state: State): boolean
	return state.owned.star_dropper == true and state.cash >= Economy.rebirthPrice(state.rebirths)
end

function Economy.rebirth(state: State): (State?, string)
	if not Economy.canRebirth(state) then
		return nil, "not_ready"
	end
	return {
		cash = 0,
		rebirths = math.min(MAX_REBIRTHS, state.rebirths + 1),
		owned = { starter_dropper = true },
	}, "ok"
end

return Economy
