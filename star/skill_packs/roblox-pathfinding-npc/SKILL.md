---
name: roblox-pathfinding-npc
description: Opt-in Roblox NPC movement recipes with PathfindingService paths, waypoints, blocked-path recovery, chase and modifiers in typed Luau.
---
# roblox-pathfinding-npc
## When to use
Use for Roblox NPCs that walk, patrol or chase with PathfindingService: computing paths, following waypoints, recovering from blocked paths and steering paths with costs and PathfindingModifier regions. Not for player input.

## Ten concrete rules
1. Create a path once with PathfindingService:CreatePath({AgentRadius, AgentHeight, AgentCanJump, AgentCanClimb, WaypointSpacing, Costs}). [S1][S2]
2. Path:ComputeAsync yields and can fail: pcall it and continue only when Status is Enum.PathStatus.Success. [S1][S3]
3. Path:GetWaypoints returns PathWaypoints (Position, Action, Label) from start to finish; the first is the start. [S1][S4]
4. When a waypoint's Action is Enum.PathWaypointAction.Jump, jump before moving to it. [S1][S5]
5. Humanoid:MoveTo times out after 8 seconds and MoveToFinished then passes false: treat it as stuck and re-plan. [S6]
6. On Path.Blocked, re-plan only when the blocked index is at or ahead of the next waypoint; disconnect when done. [S1][S3]
7. Costs keys are Enum.Material names or modifier labels; math.huge means non-traversable. [S1][S7]
8. Mark regions with an anchored, CanCollide false part holding a PathfindingModifier; PassThrough paths through blockers like doors. [S1][S7]
9. Run NPCs on the server and call SetNetworkOwner(nil) on the unanchored root so clients cannot move it. [S8][S9]
10. Start and finish must be within 3,000 studs in a straight line; re-plan at intervals, not every frame. [S1]

## Three correct Luau examples
Each is an independent server Script; example 2 sits inside the NPC model.

### Example 1: follow a path with timeout and blocked recovery
~~~luau
--!strict
local PathfindingService = game:GetService("PathfindingService")
local npc = workspace:WaitForChild("Guard") :: Model
local humanoid = npc:WaitForChild("Humanoid") :: Humanoid
local root = npc:WaitForChild("HumanoidRootPart") :: BasePart
root:SetNetworkOwner(nil)
local path = PathfindingService:CreatePath({ AgentRadius = 2, AgentHeight = 5 })

local function walkTo(goal: Vector3): boolean
	local ok = pcall(path.ComputeAsync, path, root.Position, goal)
	if not ok or path.Status ~= Enum.PathStatus.Success then
		return false
	end
	local waypoints = path:GetWaypoints()
	local index = 2 -- waypoint 1 is where the NPC stands
	local blocked = false
	local connection = path.Blocked:Connect(function(blockedIndex: number)
		blocked = blocked or blockedIndex >= index
	end)
	while index <= #waypoints and not blocked do
		local waypoint = waypoints[index]
		if waypoint.Action == Enum.PathWaypointAction.Jump then
			humanoid.Jump = true
		end
		humanoid:MoveTo(waypoint.Position)
		if not humanoid.MoveToFinished:Wait() then
			break -- timed out
		end
		index += 1
	end
	connection:Disconnect()
	return index > #waypoints
end

while not walkTo(Vector3.new(40, 3, 40)) do
	task.wait(1)
end
~~~
False means re-plan; the loop yields between attempts. [S1][S6]

### Example 2: chase the nearest player, straight when visible
~~~luau
--!strict
local Players = game:GetService("Players")
local PathfindingService = game:GetService("PathfindingService")
local npc = script.Parent :: Model
local humanoid = npc:WaitForChild("Humanoid") :: Humanoid
local root = npc:WaitForChild("HumanoidRootPart") :: BasePart
local path = PathfindingService:CreatePath()
local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Exclude
local SIGHT = 80

local function nearest(): BasePart?
	local best: BasePart?, bestDistance = nil, SIGHT
	for _, player in Players:GetPlayers() do
		local character = player.Character
		local part = if character then character:FindFirstChild("HumanoidRootPart") else nil
		local target = if character then character:FindFirstChildOfClass("Humanoid") else nil
		if part and part:IsA("BasePart") and target and target.Health > 0 then
			local distance = (part.Position - root.Position).Magnitude
			if distance < bestDistance then
				best, bestDistance = part, distance
			end
		end
	end
	return best
end

while humanoid.Health > 0 do
	local target = nearest()
	if target then
		params.FilterDescendantsInstances = { npc, target.Parent :: Instance }
		local offset = target.Position - root.Position
		if not workspace:Raycast(root.Position, offset, params) then
			humanoid:MoveTo(target.Position) -- in sight
		elseif pcall(path.ComputeAsync, path, root.Position, target.Position)
			and path.Status == Enum.PathStatus.Success then
			local step = path:GetWaypoints()[2]
			if step then
				humanoid.Jump = step.Action == Enum.PathWaypointAction.Jump
				humanoid:MoveTo(step.Position)
			end
		end
	end
	task.wait(0.25)
end
~~~
Four re-plans a second follow a moving target without per-frame requests. [S1][S6][S10]

### Example 3: avoid a hazard and path through a door
~~~luau
--!strict
local PathfindingService = game:GetService("PathfindingService")

local function region(around: BasePart, label: string?, passThrough: boolean)
	local zone = Instance.new("Part")
	zone.Anchored = true
	zone.CanCollide = false
	zone.Transparency = 1
	zone.CFrame = around.CFrame
	zone.Size = around.Size + Vector3.new(4, 4, 4)
	local modifier = Instance.new("PathfindingModifier")
	if label then
		modifier.Label = label
	end
	modifier.PassThrough = passThrough
	modifier.Parent = zone
	zone.Parent = workspace
end

region(workspace:WaitForChild("Lava") :: BasePart, "DangerZone", false)
region(workspace:WaitForChild("Door") :: BasePart, nil, true)

local path = PathfindingService:CreatePath({ Costs = { DangerZone = math.huge } })
local ok = pcall(path.ComputeAsync, path, Vector3.zero, Vector3.new(60, 0, 0))
print(ok and path.Status == Enum.PathStatus.Success)
~~~
The label must match a Costs key; the door still blocks players. [S1][S7][S11]

## Three common mistakes
1. MoveTo straight through walls instead of following waypoints. [S1]
2. Ignoring ComputeAsync errors, Status, the MoveTo timeout or Path.Blocked. [S1][S3][S6]
3. Computing a new path every frame for every NPC. [S1]

## Checklist
- [ ] ComputeAsync is in pcall and Status is checked.
- [ ] Jump waypoints make the Humanoid jump.
- [ ] MoveToFinished false and Path.Blocked trigger a re-plan.
- [ ] Costs keys match materials or modifier labels.
- [ ] The NPC root is server owned; re-planning is throttled.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S11]. Sizes and intervals are illustrative.
