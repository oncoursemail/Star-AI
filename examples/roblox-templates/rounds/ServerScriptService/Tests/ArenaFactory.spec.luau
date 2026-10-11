--!strict
local ServerScriptService = game:GetService("ServerScriptService")
local ArenaFactory = require(ServerScriptService:WaitForChild("ArenaFactory"))

return {
	["lobby spawn is reusable"] = function()
		local first = ArenaFactory.ensureLobby()
		assert(first:IsA("SpawnLocation") and first:IsDescendantOf(workspace))
		assert(ArenaFactory.ensureLobby() == first)
	end,
	["each round creates and destroys only its own map"] = function()
		local first, spawns1 = ArenaFactory.createArena()
		local second, spawns2 = ArenaFactory.createArena()
		assert(first ~= second and first.Parent == workspace and second.Parent == workspace)
		assert(#spawns1 == 12 and #spawns2 == 12)
		for _, pad in ipairs(spawns1) do
			assert(pad:IsDescendantOf(first), "all round spawn pads belong to the map")
		end
		first:Destroy()
		second:Destroy()
		assert(first.Parent == nil and second.Parent == nil, "map instances must be reclaimed")
	end,
}
