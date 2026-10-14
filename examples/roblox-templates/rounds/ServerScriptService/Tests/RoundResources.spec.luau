--!strict
local ServerScriptService = game:GetService("ServerScriptService")
local RoundResources = require(ServerScriptService:WaitForChild("RoundResources"))

return {
	["disposes fake map and connections in reverse order"] = function()
		local calls = {}
		local map = { destroyed = 0 }
		local connection = { disconnected = 0 }
		local bag = RoundResources.new()
		bag:add(function()
			map.destroyed += 1
			table.insert(calls, "map")
		end)
		bag:add(function()
			connection.disconnected += 1
			table.insert(calls, "connection")
		end)
		bag:cleanup()
		assert(map.destroyed == 1 and connection.disconnected == 1)
		assert(calls[1] == "connection" and calls[2] == "map")
	end,
	["cleanup is idempotent even after a second round"] = function()
		local disposed = 0
		for _ = 1, 2 do
			local bag = RoundResources.new()
			bag:add(function()
				disposed += 1
			end)
			bag:cleanup()
			bag:cleanup()
		end
		assert(disposed == 2, "each round should dispose once")
	end,
	["a registration after cleanup is immediately disposed"] = function()
		local count = 0
		local bag = RoundResources.new()
		bag:cleanup()
		bag:add(function()
			count += 1
		end)
		assert(count == 1)
	end,
}
