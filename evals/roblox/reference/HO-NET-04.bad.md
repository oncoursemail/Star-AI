The handler takes the ingredients one by one and then adds the result.

```luau
local Crafting = {}

local RECIPES = {
	plank = { cost = { wood = 2 }, yield = 4 },
	torch = { cost = { plank = 1, coal = 1 }, yield = 2 },
	bridge = { cost = { plank = 6, rope = 2 }, yield = 1 },
}

function Crafting.craft(inventory: { [string]: number }, recipeId: any, times: any): (boolean, string?)
	local recipe = RECIPES[recipeId]
	if not recipe then
		return false, "unknown recipe"
	end
	for item, perCraft in recipe.cost do
		local need = perCraft * times
		if (inventory[item] or 0) < need then
			return false, "not enough " .. item
		end
		inventory[item] -= need
		if inventory[item] == 0 then
			inventory[item] = nil
		end
	end
	inventory[recipeId] = (inventory[recipeId] or 0) + recipe.yield * times
	return true
end

return Crafting
```
