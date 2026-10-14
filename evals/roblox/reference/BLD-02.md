```luau
--!strict
local GRID = 4
local ROOM = 24
local WALL_HEIGHT = 12
local WALL_THICKNESS = 2
local FLOOR_THICKNESS = 1
local DOOR_WIDTH = 8
local DOOR_HEIGHT = 8

local function snap(v: number): number
	return math.floor(v / GRID + 0.5) * GRID
end

local function makePart(model: Model, name: string, size: Vector3, position: Vector3): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Anchored = true
	part.CanCollide = true
	part.Material = Enum.Material.Concrete
	part.Size = size
	part.Position = position
	part.Parent = model
	return part
end

local model = Instance.new("Model")
model.Name = "Room"
local half = ROOM / 2
local y = WALL_HEIGHT / 2

makePart(model, "Floor", Vector3.new(ROOM, FLOOR_THICKNESS, ROOM), Vector3.new(0, -FLOOR_THICKNESS / 2, 0))
makePart(model, "WallBack", Vector3.new(ROOM, WALL_HEIGHT, WALL_THICKNESS), Vector3.new(0, y, -half + WALL_THICKNESS / 2))
makePart(model, "WallLeft", Vector3.new(WALL_THICKNESS, WALL_HEIGHT, ROOM), Vector3.new(-half + WALL_THICKNESS / 2, y, 0))
makePart(model, "WallRight", Vector3.new(WALL_THICKNESS, WALL_HEIGHT, ROOM), Vector3.new(half - WALL_THICKNESS / 2, y, 0))

local side = (ROOM - DOOR_WIDTH) / 2
local zFront = half - WALL_THICKNESS / 2
makePart(model, "WallFrontLeft", Vector3.new(side, WALL_HEIGHT, WALL_THICKNESS), Vector3.new(-(DOOR_WIDTH / 2 + side / 2), y, zFront))
makePart(model, "WallFrontRight", Vector3.new(side, WALL_HEIGHT, WALL_THICKNESS), Vector3.new(DOOR_WIDTH / 2 + side / 2, y, zFront))
makePart(model, "DoorLintel", Vector3.new(DOOR_WIDTH, WALL_HEIGHT - DOOR_HEIGHT, WALL_THICKNESS),
	Vector3.new(0, DOOR_HEIGHT + (WALL_HEIGHT - DOOR_HEIGHT) / 2, zFront))

model.Parent = workspace
model:PivotTo(CFrame.new(snap(0), 0, snap(0)))
```
