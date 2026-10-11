--!strict
-- Build isolated server-owned plots, droppers, collectors and purchase prompts.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Economy = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Economy"))

export type Plot = {
	owner: Player?,
	spawn: SpawnLocation,
	title: TextLabel,
	collector: Part,
	drops: Folder,
	models: Folder,
	prompts: { [string]: ProximityPrompt },
	rebirthPrompt: ProximityPrompt,
	activeDrops: { [BasePart]: string },
	dropCount: number,
	running: { [string]: boolean },
	generation: number,
	onPurchase: ((Player, string) -> ())?,
	onRebirth: ((Player) -> ())?,
	onCollect: ((Player, string) -> ())?,
	center: Vector3,
}

local Plots = {}
local plots: { Plot } = {}
local assigned: { [Player]: Plot } = {}

local function block(parent: Instance, name: string, size: Vector3, position: Vector3, color: Color3): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.Color = color
	part.Material = Enum.Material.SmoothPlastic
	part.Parent = parent
	return part
end

local function clearDrops(plot: Plot)
	for part in pairs(plot.activeDrops) do
		part:Destroy()
	end
	plot.activeDrops = {}
	plot.dropCount = 0
end

function Plots.reset(plot: Plot)
	plot.generation += 1
	clearDrops(plot)
	for _, model in ipairs(plot.models:GetChildren()) do
		model:Destroy()
	end
	plot.running = {}
end

local function spawnDrop(plot: Plot, item: Economy.Item, index: number)
	if plot.dropCount >= Economy.MAX_ACTIVE_DROPS then
		return
	end
	local part = Instance.new("Part")
	part.Name = item.id .. "_cash"
	part.Size = Vector3.new(2, 2, 2)
	part.Position = plot.center + Vector3.new(-22 + (index - 1) * 14, 10.5, 9)
	part.Color = Color3.fromRGB(244, 196, 66)
	part.Material = Enum.Material.Metal
	part.Anchored = false
	part.CanCollide = true
	part.CanTouch = true
	part.Parent = plot.drops

	plot.activeDrops[part] = item.id
	plot.dropCount += 1
	-- An untrusted client never owns the physics simulation for money parts.
	pcall(function()
		part:SetNetworkOwner(nil)
	end)
	task.delay(20, function()
		if plot.activeDrops[part] ~= nil then
			plot.activeDrops[part] = nil
			plot.dropCount -= 1
			part:Destroy()
		end
	end)
end

local function startDropper(plot: Plot, item: Economy.Item, index: number)
	local x = -22 + (index - 1) * 14
	local base = plot.center
	local support = block(plot.models, item.id .. "_frame", Vector3.new(3, 11, 3),
		base + Vector3.new(x, 6, 16), Color3.fromRGB(62, 74, 94))
	support.CanCollide = false
	local nozzle = block(plot.models, item.id .. "_nozzle", Vector3.new(5, 2, 12),
		base + Vector3.new(x, 13, 11), Color3.fromRGB(105, 123, 151))
	nozzle.CanCollide = false

	plot.running[item.id] = true
	local generation = plot.generation
	task.spawn(function()
		while plot.owner ~= nil and plot.generation == generation and plot.running[item.id] do
			task.wait(item.interval)
			if plot.owner ~= nil and plot.generation == generation and plot.running[item.id] then
				spawnDrop(plot, item, index)
			end
		end
	end)
end

function Plots.refresh(plot: Plot, state: Economy.State)
	if plot.owner == nil then
		return
	end
	for index, item in ipairs(Economy.all()) do
		local prompt = plot.prompts[item.id]
		if prompt then
			prompt.Enabled = Economy.canBuy(state, item.id)
		end
		if state.owned[item.id] and not plot.running[item.id] then
			startDropper(plot, item, index)
		end
	end
	plot.rebirthPrompt.Enabled = Economy.canRebirth(state)
	plot.rebirthPrompt.ActionText = "Rebirth for $" .. tostring(Economy.rebirthPrice(state.rebirths))
end

local function createPlot(root: Instance, index: number): Plot
	local center = Vector3.new(((index - 1) % 3 - 1) * 90, 0, (math.floor((index - 1) / 3) - 0.5) * 90)
	local folder = Instance.new("Folder")
	folder.Name = "Plot_" .. tostring(index)
	folder.Parent = root

	block(folder, "Foundation", Vector3.new(70, 1, 70),
		center + Vector3.new(0, -0.5, 0), Color3.fromRGB(38, 47, 60))
	local collector = block(folder, "Collector", Vector3.new(60, 1, 12),
		center + Vector3.new(0, 0.6, 9), Color3.fromRGB(49, 166, 117))
	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "OwnerSpawn"
	spawn.Size = Vector3.new(7, 1, 7)
	spawn.Position = center + Vector3.new(-27, 1, -26)
	spawn.Anchored = true
	spawn.Neutral = true
	spawn.Duration = 0
	spawn.Color = Color3.fromRGB(103, 118, 142)
	spawn.Parent = folder

	local titleStand = block(folder, "Sign", Vector3.new(2, 6, 2),
		center + Vector3.new(0, 3, -31), Color3.fromRGB(110, 123, 143))
	local billboard = Instance.new("BillboardGui")
	billboard.Name = "ClaimLabel"
	billboard.Size = UDim2.fromOffset(220, 50)
	billboard.StudsOffsetWorldSpace = Vector3.new(0, 4, 0)
	billboard.AlwaysOnTop = true
	billboard.Parent = titleStand
	local title = Instance.new("TextLabel")
	title.Size = UDim2.fromScale(1, 1)
	title.BackgroundTransparency = 1
	title.TextColor3 = Color3.new(1, 1, 1)
	title.TextScaled = true
	title.Font = Enum.Font.GothamBold
	title.Text = "Unclaimed Plot"
	title.Parent = billboard

	local drops = Instance.new("Folder")
	drops.Name = "Drops"
	drops.Parent = folder
	local models = Instance.new("Folder")
	models.Name = "PurchasedDroppers"
	models.Parent = folder
	local buttons = Instance.new("Folder")
	buttons.Name = "PurchaseButtons"
	buttons.Parent = folder

	local prompts: { [string]: ProximityPrompt } = {}
	for itemIndex, item in ipairs(Economy.all()) do
		if item.id ~= Economy.STARTER_ID then
			local pad = block(buttons, item.id, Vector3.new(11, 1, 8),
				center + Vector3.new(-26 + (itemIndex - 2) * 17, 0.6, -17), Color3.fromRGB(91, 121, 161))
			local prompt = Instance.new("ProximityPrompt")
			prompt.ActionText = "Buy for $" .. tostring(item.price)
			prompt.ObjectText = item.name
			prompt.RequiresLineOfSight = false
			prompt.MaxActivationDistance = 10
			prompt.HoldDuration = 0.15
			prompt.Enabled = false
			prompt.Parent = pad
			prompts[item.id] = prompt
		end
	end
	local rebirthPad = block(buttons, "Rebirth", Vector3.new(11, 1, 8),
		center + Vector3.new(24, 0.6, -17), Color3.fromRGB(175, 132, 69))
	local rebirthPrompt = Instance.new("ProximityPrompt")
	rebirthPrompt.ActionText = "Rebirth"
	rebirthPrompt.ObjectText = "Reset for higher income"
	rebirthPrompt.RequiresLineOfSight = false
	rebirthPrompt.MaxActivationDistance = 10
	rebirthPrompt.HoldDuration = 0.25
	rebirthPrompt.Enabled = false
	rebirthPrompt.Parent = rebirthPad

	local plot: Plot = {
		owner = nil,
		spawn = spawn,
		title = title,
		collector = collector,
		drops = drops,
		models = models,
		prompts = prompts,
		rebirthPrompt = rebirthPrompt,
		activeDrops = {},
		dropCount = 0,
		running = {},
		generation = 0,
		onPurchase = nil,
		onRebirth = nil,
		onCollect = nil,
		center = center,
	}
	for itemId, prompt in pairs(prompts) do
		prompt.Triggered:Connect(function(player: Player)
			if player == plot.owner and plot.onPurchase then
				plot.onPurchase(player, itemId)
			end
		end)
	end
	rebirthPrompt.Triggered:Connect(function(player: Player)
		if player == plot.owner and plot.onRebirth then
			plot.onRebirth(player)
		end
	end)
	collector.Touched:Connect(function(part: BasePart)
		local itemId = plot.activeDrops[part]
		if itemId == nil then
			return
		end
		-- Remove first: one physical drop can trigger Touched multiple times.
		plot.activeDrops[part] = nil
		plot.dropCount -= 1
		part:Destroy()
		if plot.owner ~= nil and plot.onCollect then
			plot.onCollect(plot.owner, itemId)
		end
	end)
	return plot
end

function Plots.create()
	if #plots > 0 then
		return
	end
	local root = Instance.new("Folder")
	root.Name = "TycoonPlots"
	root.Parent = workspace
	for index = 1, 6 do
		table.insert(plots, createPlot(root, index))
	end
end

function Plots.claim(
	player: Player,
	onPurchase: (Player, string) -> (),
	onRebirth: (Player) -> (),
	onCollect: (Player, string) -> ()
): Plot?
	if assigned[player] then
		return assigned[player]
	end
	for _, plot in ipairs(plots) do
		if plot.owner == nil then
			plot.owner = player
			plot.onPurchase = onPurchase
			plot.onRebirth = onRebirth
			plot.onCollect = onCollect
			plot.title.Text = "Claimed Plot"
			assigned[player] = plot
			player.RespawnLocation = plot.spawn
			return plot
		end
	end
	return nil
end

function Plots.release(player: Player)
	local plot = assigned[player]
	if plot == nil then
		return
	end
	Plots.reset(plot)
	plot.owner = nil
	plot.onPurchase = nil
	plot.onRebirth = nil
	plot.onCollect = nil
	plot.title.Text = "Unclaimed Plot"
	for _, prompt in pairs(plot.prompts) do
		prompt.Enabled = false
	end
	plot.rebirthPrompt.Enabled = false
	player.RespawnLocation = nil
	assigned[player] = nil
end

return Plots
