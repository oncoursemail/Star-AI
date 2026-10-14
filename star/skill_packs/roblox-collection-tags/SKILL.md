---
name: roblox-collection-tags
description: Opt-in Roblox recipes for CollectionService tags and instance attributes - one script per behaviour, cleanup, streaming-aware clients and attribute config in typed Luau.
---
# roblox-collection-tags
## When to use
Use when many Roblox instances share one behaviour (lava, doors, coins, spinners, enemies) that would otherwise mean a copied script in each, or need per-object settings through attributes. Covers tags, cleanup, streaming clients and attribute signals.

## Ten concrete rules
1. Tag instances in Studio's Tags section, CollectionService:AddTag or Instance:AddTag, then run one script per tag. [S1][S2]
2. Handle existing and future instances: loop GetTagged and connect GetInstanceAddedSignal, which does not fire for instances that were already tagged. [S1]
3. Clean up in GetInstanceRemovedSignal (tag removed or instance left the DataModel): disconnect connections and clear table entries to avoid leaks. [S1]
4. Server tags replicate to clients. Client-added tags stay local and are dropped when the server changes that instance's tags. [S1]
5. With StreamingEnabled, client added and removed signals fire as tagged parts stream in and out; not every tagged part exists on a client. [S1][S3]
6. Attributes are per-instance settings: SetAttribute creates or changes one, setting nil deletes it, GetAttribute reads it. [S4][S2]
7. Validate attribute values with typeof and use a default; a designer can type anything into the Properties window. [S4]
8. React to changes with GetAttributeChangedSignal(name) or AttributeChanged. [S4]
9. Attribute names use alphanumerics plus . - / _, are at most 100 characters and must not start with RBX. [S2]
10. Keep authority on the server: client changes to tags or attributes do not replicate, so the server never trusts them. [S1][S5]

## Three correct Luau examples
Examples 1 and 3 are server Scripts; example 2 is a LocalScript (cosmetic only).

### Example 1: one script drives every part tagged Lava
~~~luau
--!strict
local CollectionService = game:GetService("CollectionService")
local TAG = "Lava"
local cleanups: { [Instance]: () -> () } = {}

local function attach(instance: Instance)
	if cleanups[instance] or not instance:IsA("BasePart") then
		return
	end
	local cooldown: { [Humanoid]: number } = {}
	local connection = instance.Touched:Connect(function(hit: BasePart)
		local model = hit:FindFirstAncestorOfClass("Model")
		local humanoid = if model then model:FindFirstChildOfClass("Humanoid") else nil
		local now = os.clock()
		if humanoid and now - (cooldown[humanoid] or 0) > 0.5 then
			cooldown[humanoid] = now
			humanoid:TakeDamage(10)
		end
	end)
	cleanups[instance] = function()
		connection:Disconnect()
	end
end

local function detach(instance: Instance)
	local cleanup = cleanups[instance]
	cleanups[instance] = nil
	if cleanup then
		cleanup()
	end
end

CollectionService:GetInstanceAddedSignal(TAG):Connect(attach)
CollectionService:GetInstanceRemovedSignal(TAG):Connect(detach)
for _, instance in CollectionService:GetTagged(TAG) do
	attach(instance)
end
~~~
Connect the signals before the loop; attach ignores an instance it already handles. [S1][S6]

### Example 2: streaming-aware spinners configured by attribute
~~~luau
--!strict
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
type Spin = { speed: number, changed: RBXScriptConnection }
local spinning: { [BasePart]: Spin } = {}

local function speedOf(part: BasePart): number
	local value = part:GetAttribute("DegreesPerSecond")
	return if typeof(value) == "number" then value else 90
end

local function add(instance: Instance)
	if not instance:IsA("BasePart") or spinning[instance] then
		return
	end
	local changed = instance:GetAttributeChangedSignal("DegreesPerSecond"):Connect(function()
		local state = spinning[instance]
		if state then
			state.speed = speedOf(instance)
		end
	end)
	spinning[instance] = { speed = speedOf(instance), changed = changed }
end

local function remove(instance: Instance)
	if instance:IsA("BasePart") and spinning[instance] then
		spinning[instance].changed:Disconnect()
		spinning[instance] = nil
	end
end

CollectionService:GetInstanceAddedSignal("Spinner"):Connect(add)
CollectionService:GetInstanceRemovedSignal("Spinner"):Connect(remove)
for _, instance in CollectionService:GetTagged("Spinner") do
	add(instance)
end

RunService.Heartbeat:Connect(function(dt: number)
	for part, state in spinning do
		part.CFrame *= CFrame.Angles(0, math.rad(state.speed * dt), 0)
	end
end)
~~~
Spinners must be anchored; the local rotation is visual and only for parts streamed in. [S1][S3][S4]

### Example 3: server spawns tagged coins with attribute data
~~~luau
--!strict
local Players = game:GetService("Players")
local folder = workspace:WaitForChild("Coins")

local function spawnCoin(position: Vector3, value: number)
	local coin = Instance.new("Part")
	coin.Shape = Enum.PartType.Ball
	coin.Size = Vector3.one * 2
	coin.Anchored = true
	coin.CanCollide = false
	coin.Position = position
	coin:SetAttribute("Value", value) -- for client labels only
	coin:AddTag("Coin")
	coin.Parent = folder
	local debounce = false
	coin.Touched:Connect(function(hit: BasePart)
		local model = hit:FindFirstAncestorOfClass("Model")
		local player = if model then Players:GetPlayerFromCharacter(model) else nil
		local stats = if player then player:FindFirstChild("leaderstats") else nil
		local coins = if stats then stats:FindFirstChild("Coins") else nil
		if debounce or not coins or not coins:IsA("IntValue") then
			return
		end
		debounce = true
		coins.Value += value -- the server's own number, not the attribute
		coin:Destroy()
	end)
end

spawnCoin(Vector3.new(0, 3, 0), 5)
~~~
Destroy removes the tag's instance, so client effects bound to Coin clean themselves up. [S1][S4][S7]

## Three common mistakes
1. Connecting GetInstanceAddedSignal without looping GetTagged, missing instances that already exist. [S1]
2. Never handling the removed signal, leaking connections when parts are destroyed or stream out. [S1][S3]
3. Trusting an attribute or tag a client changed; it never reached the server. [S1][S5]

## Checklist
- [ ] GetTagged loop plus added and removed signals.
- [ ] Per-instance state is cleaned up on removal.
- [ ] Attribute reads check the type and use a default.
- [ ] Client code tolerates parts streaming in and out.
- [ ] Gameplay values stay on the server.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S7]. Damage and speeds are illustrative.
