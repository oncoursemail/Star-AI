Numeric keys are turned into strings on the way in and back into numbers on the way out.

```luau
local Codec = {}

function Codec.encode(value: any): any
	if type(value) ~= "table" then
		return value
	end
	local out = {}
	for k, v in value do
		out[tostring(k)] = Codec.encode(v)
	end
	return out
end

function Codec.decode(value: any): any
	if type(value) ~= "table" then
		return value
	end
	local out = {}
	for k, v in value do
		out[tonumber(k) or k] = Codec.decode(v)
	end
	return out
end

return Codec
```
