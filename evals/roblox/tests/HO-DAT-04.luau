-- Holdout test body HO-DAT-04 (frozen 2026-10-11; harness-owned, never shown to the model).
local Mod = load_answer({ debug = debugStub })

local function finite(x) return type(x) == "number" and x == x and x ~= math.huge and x ~= -math.huge end
-- JSON-safe the way DataStores need it: scalars, or tables that are a continuous array or a string-keyed dictionary.
local function jsonSafe(v, depth)
	if depth > 60 then return false end
	local t = type(v)
	if t == "boolean" or t == "string" then return true end
	if t == "number" then return finite(v) end
	if t ~= "table" then return false end
	local count, allStrings = 0, true
	for k in v do
		count += 1
		if type(k) ~= "string" then allStrings = false end
	end
	if not allStrings then
		for k in v do
			if type(k) ~= "number" or k ~= math.floor(k) or k < 1 or k > count then return false end
		end
	end
	for _, child in v do
		if not jsonSafe(child, depth + 1) then return false end
	end
	return true
end

local shared = { 1, 2, 3 }
local big = {}
for i = 1, 200 do big[i] = i * 2 end
local samples = {
	{ "an empty table", {} },
	{ "a plain array", { 1, 2, 3 } },
	{ "a string-keyed dictionary", { name = "Ada", level = 5, vip = false } },
	{ "sparse numeric keys", { [101] = true, [205] = true } },
	{ "an array with a hole", { [1] = "a", [2] = "b", [4] = "d" } },
	{ "array and string keys mixed", { 10, 20, label = "mixed" } },
	{ "negative, zero and fractional keys", { [-1] = "neg", [0] = "zero", [0.5] = "half" } },
	{ "a string key \"1\" next to the number key 1", { ["1"] = "string one", [1] = "number one", ["2"] = "string two" } },
	{ "a huge index", { [1000000] = "far" } },
	{ "nested save data", { unlocked = { [101] = true, [205] = true }, queue = { "a", "b" }, stats = { hp = 10, [7] = { deep = { 1, 2 } } } } },
	{ "the same table used twice (not a cycle)", { a = shared, b = shared } },
	{ "a long array", big },
	{ "odd strings", { ["new\nline"] = "tab\there", ["é"] = "ü", [""] = "empty key" } },
}
for _, sample in samples do
	local name, value = sample[1], sample[2]
	local before = deepCopy(value)
	local okEnc, encoded = pcall(Mod.encode, value)
	local safe = okEnc and jsonSafe(encoded, 0)
	local okDec, decoded = false, nil
	if okEnc then okDec, decoded = pcall(Mod.decode, encoded) end
	check(name .. ": encode output is JSON-safe", okEnc == true and safe == true)
	check(name .. ": decode(encode(x)) equals x and x was not modified", okDec == true and deepEqual(decoded, value) and deepEqual(value, before))
end

local scalarsOk = true
for _, scalar in { 5, "text", true, false, 0.25, -3 } do
	local okEnc, encoded = pcall(Mod.encode, scalar)
	local okDec, decoded = false, nil
	if okEnc then okDec, decoded = pcall(Mod.decode, encoded) end
	if not (okEnc and okDec and decoded == scalar) then scalarsOk = false end
end
check("scalars round-trip", scalarsOk)

local cycle = { name = "loop" }
cycle.self = cycle
local a, b = { tag = "a" }, { tag = "b" }
a.other, b.other = b, a
local bad = {
	{ "NaN", { hp = 0 / 0 } },
	{ "infinity", { hp = math.huge } },
	{ "negative infinity", { list = { 1, -math.huge } } },
	{ "a function", { callback = function() end } },
	{ "a coroutine", { thread = coroutine.create(function() end) } },
	{ "a table containing itself", cycle },
	{ "two tables containing each other", { root = a } },
	{ "a top-level NaN", 0 / 0 },
	{ "an infinite key", { [math.huge] = 1 } },
}
for _, case in bad do
	local okCall = pcall(Mod.encode, case[2])
	check("encode raises an error for " .. case[1], okCall == false)
end
