```luau
local Validate = {}

function Validate.number(x: any, min: number, max: number): number?
	if type(x) ~= "number" or x ~= x or x == math.huge or x == -math.huge then
		return nil
	end
	if x < min or x > max then
		return nil
	end
	return x
end

function Validate.integer(x: any, min: number, max: number): number?
	local n = Validate.number(x, min, max)
	if n == nil or n ~= math.floor(n) then
		return nil
	end
	return n
end

function Validate.string(x: any, maxLength: number): string?
	if type(x) ~= "string" or #x < 1 or #x > maxLength then
		return nil
	end
	for i = 1, #x do
		local b = string.byte(x, i)
		if b < 32 or b == 127 then
			return nil
		end
	end
	return x
end

function Validate.oneOf(x: any, allowed: { [string]: boolean }): string?
	if type(x) ~= "string" or allowed[x] ~= true then
		return nil
	end
	return x
end

return Validate
```
