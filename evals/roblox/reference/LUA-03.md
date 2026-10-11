```luau
--!strict
local ListUtil = {}

function ListUtil.map<T, U>(list: { T }, fn: (T) -> U): { U }
	local out: { U } = {}
	for i, v in ipairs(list) do
		out[i] = fn(v)
	end
	return out
end

function ListUtil.filter<T>(list: { T }, pred: (T) -> boolean): { T }
	local out: { T } = {}
	for _, v in ipairs(list) do
		if pred(v) then
			table.insert(out, v)
		end
	end
	return out
end

function ListUtil.find<T>(list: { T }, pred: (T) -> boolean): T?
	for _, v in ipairs(list) do
		if pred(v) then
			return v
		end
	end
	return nil
end

return ListUtil
```
