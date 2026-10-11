--!strict
-- A tiny playable course created at server startup, without manual Studio-only Instances.
local Workspace = game:GetService("Workspace")

export type Course = {
	spawn: SpawnLocation,
	checkpoints: { [number]: BasePart },
	killParts: { BasePart },
	finish: BasePart,
	respawns: { [number]: CFrame },
}

local CourseBuilder = {}
local PLATFORM_Y = 8
local SPACING = 16

local function makePart(parent: Model, name: string, position: Vector3, size: Vector3, color: Color3, material: Enum.Material): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Anchored = true
	part.Size = size
	part.Position = position
	part.Color = color
	part.Material = material
	part.Parent = parent
	return part
end

function CourseBuilder.build(): Course
	local existing = Workspace:FindFirstChild("STARObbyCourse")
	if existing then
		existing:Destroy()
	end
	local model = Instance.new("Model")
	model.Name = "STARObbyCourse"
	model.Parent = Workspace

	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "Stage1Spawn"
	spawn.Anchored = true
	spawn.Neutral = true
	spawn.Size = Vector3.new(12, 1, 12)
	spawn.Position = Vector3.new(0, PLATFORM_Y, 0)
	spawn.Color = Color3.fromRGB(82, 175, 116)
	spawn.Material = Enum.Material.Grass
	spawn.Parent = model

	local checkpoints: { [number]: BasePart } = {}
	local respawns: { [number]: CFrame } = {
		[1] = CFrame.new(0, PLATFORM_Y + 4, 0),
	}
	local killParts: { BasePart } = {}

	for stage = 2, 4 do
		local x = (stage - 1) * SPACING
		makePart(
			model,
			"Platform" .. tostring(stage),
			Vector3.new(x, PLATFORM_Y, 0),
			Vector3.new(12, 1, 12),
			Color3.fromRGB(106, 133, 201),
			Enum.Material.SmoothPlastic
		)
		checkpoints[stage] = makePart(
			model,
			"Checkpoint" .. tostring(stage),
			Vector3.new(x, PLATFORM_Y + 0.65, -2),
			Vector3.new(5, 0.3, 5),
			Color3.fromRGB(66, 203, 242),
			Enum.Material.SmoothPlastic
		)
		respawns[stage] = CFrame.new(x, PLATFORM_Y + 4, -2)
	end

	makePart(
		model, "FinishPlatform", Vector3.new(4 * SPACING, PLATFORM_Y, 0),
		Vector3.new(12, 1, 12), Color3.fromRGB(106, 175, 136), Enum.Material.Grass
	)
	local finish = makePart(
		model, "FinishGate", Vector3.new(4 * SPACING, PLATFORM_Y + 3.5, 0),
		Vector3.new(1, 6, 10), Color3.fromRGB(245, 197, 71), Enum.Material.SmoothPlastic
	)
	finish.Transparency = 0.25
	finish.CanCollide = false

	for stage = 1, 4 do
		local x = (stage - 1) * SPACING + 4.5
		local strip = makePart(
			model, "KillStrip" .. tostring(stage), Vector3.new(x, PLATFORM_Y + 0.64, 0),
			Vector3.new(1, 0.25, 10), Color3.fromRGB(214, 65, 74), Enum.Material.SmoothPlastic
		)
		table.insert(killParts, strip)
	end
	local lava = makePart(
		model, "Lava", Vector3.new(32, 2, 0), Vector3.new(96, 1, 36),
		Color3.fromRGB(227, 83, 63), Enum.Material.SmoothPlastic
	)
	table.insert(killParts, lava)

	return {
		spawn = spawn,
		checkpoints = checkpoints,
		killParts = killParts,
		finish = finish,
		respawns = respawns,
	}
end

return CourseBuilder
