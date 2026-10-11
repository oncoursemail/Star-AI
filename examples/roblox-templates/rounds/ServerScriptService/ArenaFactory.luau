--!strict
-- Replace this generated arena with a cloned ServerStorage map for a real game.
local ArenaFactory = {}

local function part(parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3): Part
	local block = Instance.new("Part")
	block.Name = name
	block.Size = size
	block.CFrame = cf
	block.Anchored = true
	block.Color = color
	block.Material = Enum.Material.SmoothPlastic
	block.Parent = parent
	return block
end

function ArenaFactory.ensureLobby(): SpawnLocation
	local existing = workspace:FindFirstChild("RoundLobby")
	if existing and existing:IsA("Model") then
		local spawn = existing:FindFirstChild("LobbySpawn")
		if spawn and spawn:IsA("SpawnLocation") then
			return spawn
		end
	end

	local lobby = Instance.new("Model")
	lobby.Name = "RoundLobby"
	part(lobby, "Floor", Vector3.new(64, 2, 64), CFrame.new(0, 0, 0), Color3.fromRGB(57, 66, 83))
	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "LobbySpawn"
	spawn.Size = Vector3.new(8, 1, 8)
	spawn.CFrame = CFrame.new(0, 1.5, 0)
	spawn.Anchored = true
	spawn.Neutral = true
	spawn.Duration = 0
	spawn.Color = Color3.fromRGB(245, 185, 64)
	spawn.Parent = lobby
	lobby.Parent = workspace
	return spawn
end

function ArenaFactory.createArena(): (Model, { BasePart })
	local arena = Instance.new("Model")
	arena.Name = "ActiveRoundArena"
	part(arena, "Floor", Vector3.new(140, 2, 140), CFrame.new(0, 0, 240), Color3.fromRGB(42, 52, 69))

	local spawns: { BasePart } = {}
	for index = 1, 12 do
		local angle = (index - 1) * math.pi / 6
		local position = Vector3.new(math.cos(angle) * 48, 1.4, 240 + math.sin(angle) * 48)
		local pad = part(arena, "Spawn" .. index, Vector3.new(9, 0.8, 9),
			CFrame.new(position), Color3.fromRGB(74, 170, 146))
		table.insert(spawns, pad)
	end

	-- Deliberately simple: eliminate contestants through Humanoid death or
	-- CharacterRemoving. A real minigame can add obstacles or trusted scoring.
	arena.Parent = workspace
	return arena, spawns
end

return ArenaFactory
