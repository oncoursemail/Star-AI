--!strict
-- CutsceneService (server ModuleScript, ServerScriptService): the server decides WHEN a cutscene plays and for
-- whom; clients only play it. The remote carries ("play", name, origin, token) to clients and accepts exactly one
-- message back: ("finished", token, state), type-checked, matched to the player's open cutscene, rate limited.
--   * names come from an allow list (config.cutscenes) with a cooldown per player,
--   * one cutscene per player at a time; a deadline (length + grace) closes it even if the client never answers,
--   * optional freeze: the server zeroes WalkSpeed/JumpHeight for the cutscene and restores them afterwards,
--   * actor templates are built on the server (CreateHumanoidModelFromDescriptionAsync is server-only) and parented to
--     ReplicatedStorage.StarCutsceneActors, where clients clone them locally;
--   * describe(avatar) turns a plain avatar table (Dynamic Head, eyebrows, hair, layered clothing ids, skin colour)
--     into a HumanoidDescription. Any catalog item loads for an NPC; free items keep a game's actors purchase-free.

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

export type CutsceneConfig = { length: number, cooldown: number, freeze: boolean? }
export type Config = { cutscenes: { [string]: CutsceneConfig }, grace: number }
export type Avatar = {
	head: number?, -- a Dynamic Head asset id (FaceControls: expressions)
	brows: number?, -- eyebrow accessory of that head (moves with the brow FACS values)
	hair: { number }?,
	layered: { { id: number, kind: string, order: number? } }?, -- kind: Enum.AccessoryType name (Jacket, Pants, ...)
	skin: Color3?,
	shirt: number?, -- classic clothing under the layers
	pants: number?,
}
type Open = { name: string, token: string, deadline: number, walkSpeed: number?, jumpHeight: number? }

local CutsceneService = {}
CutsceneService.REMOTE_NAME = "StarCutsceneEvent"
CutsceneService.ACTORS_FOLDER = "StarCutsceneActors"
CutsceneService.config = { cutscenes = {}, grace = 5 } :: Config

local remote: RemoteEvent? = nil
local open: { [Player]: Open } = {}
local lastPlayed: { [Player]: { [string]: number } } = {}
local lastMessage: { [Player]: number } = {}
local finishedEvent = Instance.new("BindableEvent")
CutsceneService.Finished = finishedEvent.Event -- (player, name, state)

local function humanoidOf(player: Player): Humanoid?
	local character = player.Character
	return character and character:FindFirstChildOfClass("Humanoid")
end

local function close(player: Player, state: string)
	local entry = open[player]
	if not entry then
		return
	end
	open[player] = nil
	local humanoid = humanoidOf(player)
	if humanoid then
		if entry.walkSpeed then
			humanoid.WalkSpeed = entry.walkSpeed
		end
		if entry.jumpHeight then
			humanoid.JumpHeight = entry.jumpHeight
		end
	end
	finishedEvent:Fire(player, entry.name, state)
end

-- Server gameplay calls this (a trigger zone, a quest step, a boss intro). Returns (ok, reason).
function CutsceneService.play(player: Player, name: string, origin: CFrame): (boolean, string?)
	local r = remote
	if not r then
		return false, "CutsceneService.start() was not called"
	end
	local settings = CutsceneService.config.cutscenes[name]
	if not settings then
		return false, "not an allowed cutscene"
	end
	if open[player] then
		return false, "already in a cutscene"
	end
	local now = os.clock()
	local history = lastPlayed[player] or {}
	lastPlayed[player] = history
	if history[name] and now - history[name] < settings.cooldown then
		return false, "cooldown"
	end
	history[name] = now
	local token = string.sub(HttpService:GenerateGUID(false), 1, 32)
	local entry: Open = { name = name, token = token, deadline = now + settings.length + CutsceneService.config.grace }
	if settings.freeze then
		local humanoid = humanoidOf(player)
		if humanoid then
			entry.walkSpeed = humanoid.WalkSpeed
			entry.jumpHeight = humanoid.JumpHeight
			humanoid.WalkSpeed = 0
			humanoid.JumpHeight = 0
		end
	end
	open[player] = entry
	r:FireClient(player, "play", name, origin, token)
	task.delay(settings.length + CutsceneService.config.grace, function()
		local still = open[player]
		if still and still.token == token then
			close(player, "timeout")
		end
	end)
	return true, nil
end

function CutsceneService.playAll(name: string, origin: CFrame): number
	local count = 0
	for _, player in Players:GetPlayers() do
		if CutsceneService.play(player, name, origin) then
			count += 1
		end
	end
	return count
end

function CutsceneService.isPlaying(player: Player): boolean
	return open[player] ~= nil
end

local function onServerEvent(player: Player, action: unknown, token: unknown, state: unknown)
	local now = os.clock()
	if lastMessage[player] and now - lastMessage[player] < 0.25 then
		return -- rate limit
	end
	lastMessage[player] = now
	if action ~= "finished" or type(token) ~= "string" or type(state) ~= "string" then
		return
	end
	local entry = open[player]
	if not entry or entry.token ~= token then
		return
	end
	local reported = if state == "skipped" or state == "finished" or state == "cancelled" then state else "finished"
	close(player, reported :: string)
end

-- A HumanoidDescription for an avatar table. Layered items keep their order (inner first).
function CutsceneService.describe(avatar: Avatar): HumanoidDescription
	local d = Instance.new("HumanoidDescription")
	local skin = avatar.skin or Color3.fromRGB(204, 142, 105)
	d.HeadColor = skin
	d.TorsoColor = skin
	d.LeftArmColor = skin
	d.RightArmColor = skin
	d.LeftLegColor = skin
	d.RightLegColor = skin
	if avatar.head then
		d.Head = avatar.head
	end
	if avatar.shirt then
		d.Shirt = avatar.shirt
	end
	if avatar.pants then
		d.Pants = avatar.pants
	end
	-- one accessory list: rigid hair and eyebrows plus layered clothing (SetAccessories with rigid = true)
	local list = {}
	for _, id in avatar.hair or {} do
		table.insert(list, { AssetId = id, AccessoryType = Enum.AccessoryType.Hair, IsLayered = false })
	end
	if avatar.brows then
		table.insert(list, { AssetId = avatar.brows, AccessoryType = Enum.AccessoryType.Eyebrow, IsLayered = false })
	end
	for index, item in avatar.layered or {} do
		local ok, kind = pcall(function()
			return (Enum.AccessoryType :: any)[item.kind]
		end)
		if ok and kind then
			table.insert(list, { AssetId = item.id, AccessoryType = kind, Order = item.order or index, IsLayered = true })
		end
	end
	if #list > 0 then
		d:SetAccessories(list, true)
	end
	return d
end

-- Builds (once) an R15 actor template from a HumanoidDescription and parents it to ReplicatedStorage. Server only.
function CutsceneService.makeActor(name: string, description: HumanoidDescription?): Model
	local folder = ReplicatedStorage:FindFirstChild(CutsceneService.ACTORS_FOLDER)
	if not folder then
		local made = Instance.new("Folder")
		made.Name = CutsceneService.ACTORS_FOLDER
		made.Parent = ReplicatedStorage
		folder = made
	end
	local existing = (folder :: Instance):FindFirstChild(name)
	if existing and existing:IsA("Model") then
		return existing
	end
	local model = Players:CreateHumanoidModelFromDescriptionAsync(description or Instance.new("HumanoidDescription"), Enum.HumanoidRigType.R15)
	model.Name = name
	local animate = model:FindFirstChild("Animate")
	if animate then
		animate:Destroy()
	end
	local root = model:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		root.Anchored = true
	end
	model.Parent = folder
	return model
end

function CutsceneService.start(): RemoteEvent
	if remote then
		return remote :: RemoteEvent
	end
	local r = ReplicatedStorage:FindFirstChild(CutsceneService.REMOTE_NAME)
	if not r then
		local made = Instance.new("RemoteEvent")
		made.Name = CutsceneService.REMOTE_NAME
		made.Parent = ReplicatedStorage
		r = made
	end
	local event = r :: RemoteEvent
	remote = event
	event.OnServerEvent:Connect(onServerEvent)
	Players.PlayerRemoving:Connect(function(player: Player)
		open[player] = nil
		lastPlayed[player] = nil
		lastMessage[player] = nil
	end)
	return event
end

return CutsceneService
