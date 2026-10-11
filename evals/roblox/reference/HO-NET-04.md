The server owns the recipe table. `craft` validates both arguments first, checks every ingredient for all the crafts, and only then changes the inventory, so a failure can never leave a half-paid craft behind.

```luau
--!strict
local Crafting = {}

type Recipe = { cost: { [string]: number }, yield: number }

local RECIPES: { [string]: Recipe } = {
	plank = { cost = { wood = 2 }, yield = 4 },
	torch = { cost = { plank = 1, coal = 1 }, yield = 2 },
	bridge = { cost = { plank = 6, rope = 2 }, yield = 1 },
}

local MAX_TIMES = 20

function Crafting.craft(inventory: { [string]: number }, recipeId: any, times: any): (boolean, string?)
	if type(recipeId) ~= "string" then
		return false, "unknown recipe"
	end
	local recipe = RECIPES[recipeId]
	if recipe == nil then
		return false, "unknown recipe"
	end
	if type(times) ~= "number" or times ~= times or times < 1 or times > MAX_TIMES or times ~= math.floor(times) then
		return false, "times must be a whole number from 1 to " .. MAX_TIMES
	end
	for item, perCraft in recipe.cost do
		if (inventory[item] or 0) < perCraft * times then
			return false, "not enough " .. item
		end
	end
	for item, perCraft in recipe.cost do
		local left = (inventory[item] or 0) - perCraft * times
		inventory[item] = if left > 0 then left else nil
	end
	inventory[recipeId] = (inventory[recipeId] or 0) + recipe.yield * times
	return true, nil
end

return Crafting
```
