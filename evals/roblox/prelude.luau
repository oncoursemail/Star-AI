-- STAR eval harness prelude (owned by the harness; the model never sees or edits it).
-- Runs in the standalone Luau VM on the server, as user `star`, under prlimit and timeout.
-- The answer under test arrives as the string __SRC and is only loaded with loadstring() into a
-- whitelisted environment, so it has no `require`, no `loadstring`, no file or network access.
-- Result lines start with "@@" so they can be told from anything the answer prints (its print is silenced).
local __print = print
local __loadstring = loadstring
local __setfenv = setfenv
local __clock = 0

local function check(name, cond)
	__print("@@T\t" .. (cond and "pass" or "fail") .. "\t" .. tostring(name))
end

local function deepEqual(a, b)
	if a == b then return true end
	if type(a) ~= "table" or type(b) ~= "table" then return false end
	for k, v in a do
		if not deepEqual(v, b[k]) then return false end
	end
	for k in b do
		if a[k] == nil then return false end
	end
	return true
end

local function deepCopy(t)
	if type(t) ~= "table" then return t end
	local out = {}
	for k, v in t do out[k] = deepCopy(v) end
	return out
end

local function countKeys(t)
	local n = 0
	for _ in t do n += 1 end
	return n
end

-- A deterministic generator (the harness never uses math.random, so runs are repeatable).
local function lcg(seed)
	local state = seed
	return function(n)
		state = (state * 1103515245 + 12345) % 2147483648
		return (state % n) + 1
	end
end

local Signal = {}
Signal.__index = Signal
function Signal.new()
	return setmetatable({ _fns = {} }, Signal)
end
function Signal:Connect(fn)
	local entry = { fn = fn, connected = true }
	table.insert(self._fns, entry)
	return { Connected = true, Disconnect = function() entry.connected = false end }
end
function Signal:Fire(...)
	for _, entry in ipairs(self._fns) do
		if entry.connected then entry.fn(...) end
	end
end

-- A mock `game`: GetService returns what the test registered, anything else is an error.
local function mockGame(services)
	local g = { __closers = {} }
	function g:GetService(name)
		local s = services[name]
		if s == nil then error("service not mocked: " .. tostring(name)) end
		return s
	end
	function g:BindToClose(fn) table.insert(g.__closers, fn) end
	g.PlaceId = 1
	g.JobId = "test-job"
	for name, service in services do g[name] = service end   -- game.Players as well as game:GetService("Players")
	return g
end

local SAFE = {
	assert = assert, error = error, ipairs = ipairs, pairs = pairs, next = next, pcall = pcall, xpcall = xpcall,
	select = select, tonumber = tonumber, tostring = tostring, type = type, typeof = typeof, unpack = unpack,
	rawequal = rawequal, rawget = rawget, rawset = rawset, rawlen = rawlen, setmetatable = setmetatable,
	getmetatable = getmetatable, math = math, string = string, table = table, utf8 = utf8, bit32 = bit32,
	coroutine = coroutine, buffer = buffer,
	os = { time = os.time, clock = os.clock, date = os.date },
	print = function() end, warn = function() end,
	time = function() return os.clock() end, tick = function() return os.time() end,
}
SAFE.task = {
	wait = function(t) local d = t or 0.03; __clock += d; return d end,
	spawn = function(f, ...) local co = coroutine.create(f); coroutine.resume(co, ...); return co end,
	defer = function(f, ...) local co = coroutine.create(f); coroutine.resume(co, ...); return co end,
	delay = function() end, cancel = function() end,
}
SAFE.wait = SAFE.task.wait

local function newEnv(extra)
	local env = {}
	for k, v in SAFE do env[k] = v end
	if extra then
		for k, v in extra do env[k] = v end
	end
	return env
end

-- Load the answer; returns what its chunk returns (the ModuleScript's value) and the chunk's globals table.
-- `extra` adds or replaces globals such as game, Instance, os or Players.
local function load_answer(extra)
	local f, err = __loadstring(__SRC, "=answer")
	if not f then
		__print("@@LOADERR\t" .. string.sub(tostring(err), 1, 300))
		error("answer did not load")
	end
	local env = newEnv(extra)
	__setfenv(f, env)
	return f(), env
end

-- The thing named `name` that the answer provides: its returned function or table member, else a global.
local function resolve(ret, env, name)
	if type(ret) == "function" then return ret end
	if type(ret) == "table" and ret[name] ~= nil then return ret[name] end
	return env[name]
end

-- A folder-like node: t:FindFirstChild(name) and t:WaitForChild(name) read the table's own fields.
local function node(t)
	function t:FindFirstChild(name) return rawget(self, name) end
	function t:WaitForChild(name) return rawget(self, name) end
	function t:FindFirstChildOfClass(className)
		for _, child in self do
			if type(child) == "table" and child.ClassName == className then return child end
		end
		return nil
	end
	t.FindFirstChildWhichIsA = t.FindFirstChildOfClass
	return t
end

-- A mock Humanoid inside a character node.
local function mockCharacter(health)
	local hum = { ClassName = "Humanoid", WalkSpeed = 16, Health = health or 100, MaxHealth = 100 }
	function hum:IsA(c) return c == "Humanoid" end
	function hum:TakeDamage(n) self.Health = math.max(0, self.Health - n) end
	return node({ Humanoid = hum, ClassName = "Model" }), hum
end

-- A mock player with leaderstats.Coins, attributes and the lookups scripts usually make.
local function mockPlayer(name, userId, coins)
	local attrs = {}
	local p = node({ Name = name, UserId = userId, leaderstats = node({ Coins = { Value = coins or 0 } }) })
	function p:GetAttribute(k) return attrs[k] end
	function p:SetAttribute(k, v) attrs[k] = v end
	function p:IsA(c) return c == "Player" end
	return p
end

-- Run `fn` and report whether it threw (a thrown error is a legitimate, checked outcome).
local function throws(fn, ...)
	local ok = pcall(fn, ...)
	return not ok
end
