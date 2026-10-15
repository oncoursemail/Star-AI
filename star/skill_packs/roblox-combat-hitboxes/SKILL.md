---
name: roblox-combat-hitboxes
description: Opt-in Roblox combat recipes for server-authoritative melee hitboxes, hitscan raycasts, damage, cooldowns and hit validation with typed Luau.
---
# roblox-combat-hitboxes
## When to use
Use for Roblox melee hitboxes, swords, punches, guns, hitscan or spatial-query hit detection, damage, attack cooldowns and validating a hit the client reports. Not for animation timing or particle effects; those have their own packs.

## Ten concrete rules
1. The server decides hits and damage. The client sends intent (attack pressed, aim direction); never accept "I hit X for N damage". [S1][S2]
2. For melee volumes use WorldRoot:GetPartBoundsInBox or GetPartBoundsInRadius; they test bounding boxes. Use GetPartsInPart when the exact shape matters. [S3]
3. Spatial queries return parts, not characters: map each part to its Model, find the Humanoid and keep a per-swing set so one target is hit once. [S3][S9]
4. Build OverlapParams or RaycastParams with FilterType Exclude and the attacker's character in FilterDescendantsInstances. Cap MaxParts. [S4][S5]
5. Hitscan with workspace:Raycast(origin, direction, params); direction length is the range, and the result is nil when nothing is hit. [S5][S6]
6. Treat every remote argument as hostile: check typeof, then bounds written so NaN fails (`if not (m >= lo and m <= hi)`). [S2]
7. Rate-limit on the server with os.clock per player, and clear the table in PlayerRemoving. [S2][S8]
8. Server and client positions differ by latency: allow a tolerance when comparing a reported origin with the server character, and check only static geometry for walls. [S2]
9. Humanoid:TakeDamage respects a ForceField; check Health > 0 and team rules before applying it. [S7][S8]
10. Play swing sounds and effects on the client at once for feel; the server result stays authoritative. [S10]

## Three correct Luau examples
Each is independent. Examples 1 and 2 are server Scripts; example 3 is a LocalScript. Create the RemoteEvent named Fire in ReplicatedStorage.

### Example 1: melee box in front of the attacker
~~~luau
--!strict
local params = OverlapParams.new()
params.FilterType = Enum.RaycastFilterType.Exclude
params.MaxParts = 50
local SIZE = Vector3.new(5, 5, 6)

local function humanoidsInFront(character: Model): { Humanoid }
	local root = character:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") then
		return {}
	end
	params.FilterDescendantsInstances = { character }
	local box = root.CFrame * CFrame.new(0, 0, -SIZE.Z / 2)
	local seen: { [Humanoid]: boolean } = {}
	local hits: { Humanoid } = {}
	for _, part in workspace:GetPartBoundsInBox(box, SIZE, params) do
		local model = part:FindFirstAncestorOfClass("Model")
		local humanoid = if model then model:FindFirstChildOfClass("Humanoid") else nil
		if humanoid and not seen[humanoid] and humanoid.Health > 0 then
			seen[humanoid] = true
			table.insert(hits, humanoid)
		end
	end
	return hits
end

return humanoidsInFront
~~~
Negative Z is the facing direction, so the box sits in front of the root part. [S3][S4]

### Example 2: server-validated hitscan
~~~luau
--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local fire = ReplicatedStorage:WaitForChild("Fire") :: RemoteEvent
local RANGE, COOLDOWN, DAMAGE = 300, 0.25, 15
local lastShot: { [Player]: number } = {}

fire.OnServerEvent:Connect(function(player: Player, direction: unknown)
	if typeof(direction) ~= "Vector3" then
		return
	end
	local length = direction.Magnitude
	if not (length >= 0.5 and length <= 1.5) then
		return -- also rejects NaN
	end
	local now = os.clock()
	if now - (lastShot[player] or 0) < COOLDOWN then
		return
	end
	local character = player.Character
	local head = if character then character:FindFirstChild("Head") else nil
	if not character or not head or not head:IsA("BasePart") then
		return
	end
	lastShot[player] = now
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { character }
	local result = workspace:Raycast(head.Position, direction.Unit * RANGE, params)
	local model = if result then result.Instance:FindFirstAncestorOfClass("Model") else nil
	local humanoid = if model then model:FindFirstChildOfClass("Humanoid") else nil
	if humanoid and humanoid.Health > 0 then
		humanoid:TakeDamage(DAMAGE)
	end
end)

Players.PlayerRemoving:Connect(function(player: Player)
	lastShot[player] = nil
end)
~~~
The origin comes from the server's own character, so only the direction is trusted, after checks. [S2][S5][S6]

### Example 3: client sends only an aim direction
~~~luau
--!strict
local UserInputService = game:GetService("UserInputService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local fire = ReplicatedStorage:WaitForChild("Fire") :: RemoteEvent

UserInputService.InputBegan:Connect(function(input: InputObject, processed: boolean)
	if processed or input.UserInputType ~= Enum.UserInputType.MouseButton1 then
		return
	end
	local camera = workspace.CurrentCamera
	local mouse = UserInputService:GetMouseLocation()
	local ray = camera:ViewportPointToRay(mouse.X, mouse.Y)
	fire:FireServer(ray.Direction)
end)
~~~
GetMouseLocation ignores the top inset and ViewportPointToRay expects viewport pixels, so they pair. [S11][S12]

## Three common mistakes
1. Touched-based weapon hitboxes: Touched fires only from physical movement, not when a CFrame is set into overlap. [S13]
2. Letting the client name the target, the damage or the shot origin without server checks. [S1][S2]
3. Damaging once per body part instead of once per Humanoid per swing. [S3]

## Checklist
- [ ] The client sends intent only; the server owns targets, damage and ammo.
- [ ] Every remote argument is type-checked and range-checked in a NaN-safe way.
- [ ] Per-player cooldowns live on the server and are cleared on leave.
- [ ] The attacker is excluded from queries and each Humanoid is hit once.
- [ ] Alive, team and ForceField rules are checked before damage.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S13]. Sizes, ranges and cooldowns are illustrative.
