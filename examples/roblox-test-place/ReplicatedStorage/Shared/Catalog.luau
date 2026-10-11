--!strict
-- What the shop sells. Shared, so the client can show prices; the server never trusts a price from a client.
export type Item = { id: string, name: string, price: number }

local Catalog = {}

local items: { [string]: Item } = {
	speed_coil = { id = "speed_coil", name = "Speed Coil", price = 50 },
	trail = { id = "trail", name = "Star Trail", price = 120 },
}

function Catalog.get(id: string): Item?
	return items[id]
end

function Catalog.all(): { Item }
	local list: { Item } = {}
	for _, item in pairs(items) do
		table.insert(list, item)
	end
	table.sort(list, function(a: Item, b: Item): boolean
		return a.id < b.id
	end)
	return list
end

return Catalog
