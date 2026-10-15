--!strict
-- VfxClient (client ModuleScript, e.g. ReplicatedStorage.StarVfx): renders effects the server sends and sends
-- requests. It checks every value it receives (types, known ability/style, sane speed) before rendering.
-- Custom (generated) abilities and styles register here by name; the server's allow list still decides
-- which names a player may request.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Styles = require(script.Parent:WaitForChild("VfxStyles"))
local Composer = require(script.Parent:WaitForChild("VfxComposer"))

local VfxClient = {}

local abilities: { [string]: Composer.Ability } = table.clone(Composer.ABILITIES)
local styles: { [string]: Styles.Style } = {}
for _, name in Styles.ORDER do
	styles[name] = Styles.get(name)
end

VfxClient.onPlay = nil :: ((name: string, handle: Composer.Handle) -> ())?

function VfxClient.registerAbility(ability: Composer.Ability): boolean
	local ok, problem = Composer.validate(ability)
	if not ok then
		warn("[StarVfx] ability not registered: " .. tostring(problem))
		return false
	end
	abilities[ability.name] = ability
	return true
end

function VfxClient.registerStyle(style: Styles.Style)
	styles[style.name] = style
end

local function render(ability: unknown, style: unknown, origin: unknown, casterUserId: unknown, seed: unknown, speed: unknown)
	if type(ability) ~= "string" or type(style) ~= "string" or typeof(origin) ~= "CFrame" then
		return
	end
	local a = abilities[ability]
	local s = styles[style]
	if not a or not s then
		return
	end
	local caster = if type(casterUserId) == "number" and casterUserId > 0 then Composer.characterOf(casterUserId) else nil
	local handle = Composer.play(a, s, origin :: CFrame, {
		caster = caster,
		seed = if type(seed) == "number" then seed else nil,
		speed = if type(speed) == "number" then math.clamp(speed, 0.05, 1) else 1,
	})
	local hook = VfxClient.onPlay
	if handle and hook then
		hook(ability, handle)
	end
end

local remote: RemoteEvent? = nil

function VfxClient.start(): RemoteEvent
	local r = ReplicatedStorage:WaitForChild("StarVfxEvent") :: RemoteEvent
	remote = r
	r.OnClientEvent:Connect(render)
	return r
end

-- Ask the server to play an ability (it checks cooldowns, range and allow lists).
function VfxClient.request(ability: string, style: string, target: Vector3?)
	local r = remote
	if r then
		r:FireServer(ability, style, target)
	end
end

-- Play locally only (previews, menus); nothing is sent to the server.
function VfxClient.preview(ability: string, style: string, origin: CFrame, speed: number?): Composer.Handle?
	local a = abilities[ability]
	local s = styles[style]
	if not a or not s then
		return nil
	end
	return Composer.play(a, s, origin, { speed = speed })
end

return VfxClient
