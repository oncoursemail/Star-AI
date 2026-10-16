-- STAR Roblox benchmark: check harness (server Script). The runner puts a task's check body after this text.
-- It runs only in a playtest; it prints one marked JSON line when it starts and one with every check's result.
local RunService = game:GetService("RunService")
if not RunService:IsRunning() or not RunService:IsServer() then
	return
end
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local RUN = script:GetAttribute("StarBenchRun")
local ROOT = script.Parent
local MARK = "STAR_BENCH "
local results = {}

local function say(kind, data)
	data.kind = kind
	data.run = RUN
	print(MARK .. HttpService:JSONEncode(data))
end

-- One named check: passes when fn returns without an error. Each result is printed at once (a later check that
-- hangs keeps the earlier results). Quotes and backslashes in error text become ' : the Studio console does not
-- keep JSON escapes intact.
local function check(name, fn)
	local ok, err = pcall(fn)
	local why = ok and "" or string.sub(string.gsub(tostring(err), '[%c"\\]', "'"), 1, 300)
	local result = { name = name, ok = ok, why = why }
	table.insert(results, result)
	say("check", { name = name, ok = ok, why = why })
end

local function expect(condition, message)
	if not condition then
		error(message or "expectation failed", 2)
	end
end

local function near(a, b, eps)
	return math.abs(a - b) <= (eps or 1e-3)
end

-- Polls fn every 0.1 s until it returns a truthy value or the time is up (then nil).
local function waitFor(fn, seconds)
	local deadline = os.clock() + (seconds or 5)
	repeat
		local value = fn()
		if value then
			return value
		end
		task.wait(0.1)
	until os.clock() > deadline
	return nil
end

-- The task's ModuleScript (module tasks).
local function solution()
	local module = ROOT:WaitForChild("Solution", 10)
	expect(module and module:IsA("ModuleScript"), "no ModuleScript named Solution")
	return require(module)
end

-- The playtest's player, its character and HumanoidRootPart.
local function testPlayer()
	local player = waitFor(function()
		return Players:GetPlayers()[1]
	end, 20)
	expect(player, "no player joined the playtest")
	local character = player.Character or waitFor(function()
		return player.Character
	end, 20)
	expect(character, "the player has no character")
	local root = character:WaitForChild("HumanoidRootPart", 10)
	expect(root, "the character has no HumanoidRootPart")
	return player, character, root
end

-- A fresh anchored test part inside this task's folder.
local function testPart(props)
	local part = Instance.new("Part")
	part.Anchored = true
	for key, value in pairs(props or {}) do
		part[key] = value
	end
	part.Parent = ROOT
	return part
end

-- Elapsed time in three clocks. On a busy Studio server they disagree (measured: 0.6 s wall clock = 0.34 s
-- time() = 0.38 s of Heartbeat dt), so timing checks accept an answer that is right in any of them.
local function stopwatch()
	local sw = { frames = 0, wall0 = os.clock(), game0 = time() }
	sw.connection = RunService.Heartbeat:Connect(function(dt)
		sw.frames += dt
	end)
	function sw.read()
		return { frames = sw.frames, wall = os.clock() - sw.wall0, game = time() - sw.game0 }
	end
	function sw.stop()
		sw.connection:Disconnect()
		return sw.read()
	end
	return sw
end

say("start", {})
-- ===== task check body =====
