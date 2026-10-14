Tables are classified one at a time: a string-keyed dictionary and a continuous array are already storable and stay as they are; every other table (sparse, mixed, negative or fractional keys, or a dictionary that happens to use the marker key) is stored as a list of `{ key, value }` pairs behind a marker. Cycles are detected on the current path only, so a table that is merely shared in two places is fine.

```luau
--!strict
local Codec = {}

local MARKER = "__pairs"

local function isFinite(n: number): boolean
	return n == n and n ~= math.huge and n ~= -math.huge
end

local function classify(t: { [any]: any }): string
	local count, strings, numbers = 0, 0, 0
	for k in t do
		count += 1
		if type(k) == "string" then
			strings += 1
		elseif type(k) == "number" then
			numbers += 1
		else
			error("unsupported key type " .. type(k))
		end
	end
	if count == 0 then
		return "array"
	end
	if strings == count then
		return if t[MARKER] ~= nil then "pairs" else "dict"
	end
	if numbers == count then
		for i = 1, count do
			if t[i] == nil then
				return "pairs"
			end
		end
		return "array"
	end
	return "pairs"
end

local function encodeValue(value: any, path: { [any]: boolean }): any
	local kind = type(value)
	if kind == "boolean" or kind == "string" then
		return value
	elseif kind == "number" then
		if not isFinite(value) then
			error("cannot store a non-finite number")
		end
		return value
	elseif kind ~= "table" then
		error("cannot store a " .. kind)
	end
	if path[value] then
		error("cannot store a table that contains itself")
	end
	path[value] = true
	local shape = classify(value)
	local out: { [any]: any } = {}
	if shape == "array" then
		for i = 1, #value do
			out[i] = encodeValue(value[i], path)
		end
	elseif shape == "dict" then
		for k, v in value do
			out[k] = encodeValue(v, path)
		end
	else
		local pairsList = {}
		for k, v in value do
			if type(k) == "number" and not isFinite(k) then
				error("cannot store a non-finite key")
			end
			table.insert(pairsList, { k, encodeValue(v, path) })
		end
		out[MARKER] = pairsList
	end
	path[value] = nil
	return out
end

function Codec.encode(value: any): any
	return encodeValue(value, {})
end

function Codec.decode(value: any): any
	if type(value) ~= "table" then
		return value
	end
	local out: { [any]: any } = {}
	local list = value[MARKER]
	if type(list) == "table" then
		for _, pair in list do
			out[pair[1]] = Codec.decode(pair[2])
		end
		return out
	end
	for k, v in value do
		out[k] = Codec.decode(v)
	end
	return out
end

return Codec
```
