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

    -- These run with the staged offline Engine stand-in, not in Roblox Studio.
    ["headless IsA recognizes Part ancestors"] = function()
        local block = Instance.new("Part")
        assert(block.ClassName == "Part" and block:IsA("Part"))
        assert(block:IsA("FormFactorPart") and block:IsA("BasePart"))
        assert(block:IsA("PVInstance") and block:IsA("Instance") and block:IsA("Object"))
        assert(not block:IsA("Model") and not block:IsA("SpawnLocation"))
    end,
    ["headless IsA recognizes SpawnLocation and Model ancestors"] = function()
        local spawn = Instance.new("SpawnLocation")
        assert(spawn.ClassName == "SpawnLocation" and spawn:IsA("SpawnLocation"))
        assert(spawn:IsA("Part") and spawn:IsA("BasePart") and spawn:IsA("PVInstance"))
        assert(not spawn:IsA("Model"))
        local model = Instance.new("Model")
        assert(model.ClassName == "Model" and model:IsA("Model"))
        assert(model:IsA("PVInstance") and model:IsA("Instance") and model:IsA("Object"))
        assert(not model:IsA("Part") and not model:IsA("BasePart"))
    end,
    ["headless IsA recognizes Workspace ancestors"] = function()
        assert(workspace.ClassName == "Workspace" and workspace:IsA("Workspace"))
        assert(workspace:IsA("WorldRoot") and workspace:IsA("Model"))
        assert(workspace:IsA("PVInstance") and workspace:IsA("Instance") and workspace:IsA("Object"))
        assert(not workspace:IsA("BasePart"))
    end,
    ["headless IsA rejects unsupported and malformed queries"] = function()
        local block = Instance.new("Part")
        assert(not pcall(function() block:IsA("UnsupportedFutureClass") end))
        assert(not pcall(function() block:IsA("") end))
        assert(not pcall(function() block:IsA(nil) end))
        assert(not pcall(function() block:IsA(123) end))
        assert(not pcall(function() block:IsA({}) end))
    end,
    ["headless Instance.new rejects unsupported classes"] = function()
        for _, className in ipairs({ "UnmodeledService", "Object", "Instance", "PVInstance", "BasePart", "FormFactorPart", "WorldRoot", "Workspace" }) do
            assert(not pcall(function() Instance.new(className) end), className)
        end
        assert(not pcall(function() Instance.new("") end))
        assert(not pcall(function() Instance.new(nil) end))
        assert(not pcall(function() Instance.new(123) end))
    end,
}
