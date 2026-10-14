--!strict
-- VfxService (server ModuleScript, ServerScriptService): the only path from a client's request to an effect
-- every client renders. The server never trusts the client's position, ability or timing:
--   * the request carries only an ability name and a style name (strings, length-checked, from allow lists),
--   * the origin is the caster's own character position on the server (a target point is clamped to range),
--   * per-player cooldown and a token bucket limit spam; a dead or missing character is refused,
--   * only players near the effect are told (relevance radius), and gameplay damage never depends on VFX.
-- Clients render with VfxClient + VfxComposer. Server gameplay code calls VfxService.playAt(...) directly.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local VfxService = {}

export type Config = {
	abilities: { [string]: number }, -- allowed ability -> cooldown seconds
	styles: { string }, -- allowed style names
	range: number, -- max distance of a requested target point from the caster
	relevance: number, -- only players this close receive the effect
	burst: number, -- token bucket size per player
	refill: number, -- tokens per second
}

VfxService.config = {
	abilities = { energy_burst = 3, impact_hit = 0.4 },
	styles = { "anime_energy", "cartoon_soft", "realistic_fire", "scifi_neon", "pixel_retro" },
	range = 60,
	relevance = 400,
	burst = 4,
	refill = 1,
} :: Config

local REMOTE_NAME = "StarVfxEvent"
local remote: RemoteEvent? = nil
local lastUse: { [Player]: { [string]: number } } = {}
local tokens: { [Player]: { amount: number, at: number } } = {}

local function takeToken(player: Player): boolean
	local now = os.clock()
	local bucket = tokens[player]
	if not bucket then
		bucket = { amount = VfxService.config.burst, at = now }
		tokens[player] = bucket
	end
	bucket.amount = math.min(VfxService.config.burst, bucket.amount + (now - bucket.at) * VfxService.config.refill)
	bucket.at = now
	if bucket.amount < 1 then
		return false
	end
	bucket.amount -= 1
	return true
end

local function rootOf(player: Player): BasePart?
	local character = player.Character
	if not character then
		return nil
	end
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	if not humanoid or humanoid.Health <= 0 then
		return nil
	end
	local root = character:FindFirstChild("HumanoidRootPart")
	return if root and root:IsA("BasePart") then root else nil
end

local function groundBelow(position: Vector3, ignore: Instance?): CFrame
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = if ignore then { ignore } else {}
	local hit = workspace:Raycast(position + Vector3.new(0, 2, 0), Vector3.new(0, -20, 0), params)
	local y = if hit then hit.Position.Y else position.Y - 3
	return CFrame.new(position.X, y, position.Z)
end

-- Send an effect to every client near `origin`. speed is 1 in gameplay; the Studio lab may pass a slower speed.
function VfxService.playAt(ability: string, style: string, origin: CFrame, casterUserId: number?, speed: number?)
	local r = remote
	if not r then
		return
	end
	local seed = math.random(1, 2 ^ 30)
	local playSpeed = math.clamp(speed or 1, 0.05, 1)
	for _, player in Players:GetPlayers() do
		local root = rootOf(player)
		if not root or (root.Position - origin.Position).Magnitude <= VfxService.config.relevance then
			r:FireClient(player, ability, style, origin, casterUserId or 0, seed, playSpeed)
		end
	end
end

local function onRequest(player: Player, ability: unknown, style: unknown, target: unknown)
	if type(ability) ~= "string" or #ability > 40 or type(style) ~= "string" or #style > 40 then
		return
	end
	local cooldown = VfxService.config.abilities[ability]
	if cooldown == nil or not table.find(VfxService.config.styles, style) then
		return
	end
	local root = rootOf(player)
	if not root or not takeToken(player) then
		return
	end
	local uses = lastUse[player]
	if not uses then
		uses = {}
		lastUse[player] = uses
	end
	local now = os.clock()
	if now - (uses[ability] or -math.huge) < cooldown then
		return
	end
	uses[ability] = now
	local point = root.Position
	if typeof(target) == "Vector3" then
		local offset = (target :: Vector3) - root.Position
		if offset.Magnitude == offset.Magnitude then -- not NaN
			point = root.Position + (if offset.Magnitude > VfxService.config.range then offset.Unit * VfxService.config.range else offset)
		end
	end
	VfxService.playAt(ability, style, groundBelow(point, player.Character), player.UserId, 1)
end

function VfxService.start(): RemoteEvent
	local existing = ReplicatedStorage:FindFirstChild(REMOTE_NAME)
	local r: RemoteEvent
	if existing and existing:IsA("RemoteEvent") then
		r = existing
	else
		r = Instance.new("RemoteEvent")
		r.Name = REMOTE_NAME
		r.Parent = ReplicatedStorage
	end
	remote = r
	r.OnServerEvent:Connect(onRequest)
	Players.PlayerRemoving:Connect(function(player: Player)
		lastUse[player] = nil
		tokens[player] = nil
	end)
	return r
end

return VfxService
