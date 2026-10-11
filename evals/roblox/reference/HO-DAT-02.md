`upgrade` works on a deep copy, validates the version, then applies one small step per version. Settings defaults are filled key by key, so a stored `false` is never replaced.

```luau
--!strict
local Migrate = {}

local CURRENT_VERSION = 3
local DEFAULT_SETTINGS = { music = true, sfx = true }

local function deepCopy(value: any): any
	if type(value) ~= "table" then
		return value
	end
	local out = {}
	for k, v in value do
		out[k] = deepCopy(v)
	end
	return out
end

local function toV2(data: { [string]: any })
	data.coins = if type(data.gold) == "number" then data.gold else 0
	data.gold = nil
	local counts: { [string]: number } = {}
	if type(data.items) == "table" then
		for _, name in data.items do
			counts[name] = (counts[name] or 0) + 1
		end
	end
	data.items = counts
	data.version = 2
end

function Migrate.upgrade(data: any): ({ [string]: any }, number)
	if type(data) ~= "table" then
		error("save data must be a table, got " .. type(data))
	end
	local copy = deepCopy(data)
	local version = copy.version
	if version == nil then
		version = 1
	end
	if type(version) ~= "number" or version ~= math.floor(version) or version < 1 or version > CURRENT_VERSION then
		error("unsupported save version " .. tostring(version))
	end
	local steps = 0
	if version == 1 then
		toV2(copy)
		version = 2
		steps += 1
	end
	if version == 2 then
		copy.version = 3
		steps += 1
	end
	local settings = if type(copy.settings) == "table" then copy.settings else {}
	for key, default in DEFAULT_SETTINGS do
		if settings[key] == nil then
			settings[key] = default
		end
	end
	copy.settings = settings
	return copy, steps
end

return Migrate
```
