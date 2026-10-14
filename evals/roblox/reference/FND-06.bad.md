```luau
--!strict
-- Restarts every composite from its first child on each tick, so earlier actions run again while one is Running.
local BT = {}

function BT.Sequence(children: { any })
	return { tick = function(_self: any, bb: any): string
		for _, child in children do
			local s = child:tick(bb)
			if s ~= "Success" then return s end
		end
		return "Success"
	end }
end

function BT.Selector(children: { any })
	return { tick = function(_self: any, bb: any): string
		for _, child in children do
			local s = child:tick(bb)
			if s ~= "Failure" then return s end
		end
		return "Failure"
	end }
end

function BT.Action(fn: (any) -> string)
	return { tick = function(_self: any, bb: any): string return fn(bb) end }
end

function BT.Condition(fn: (any) -> boolean)
	return { tick = function(_self: any, bb: any): string return if fn(bb) then "Success" else "Failure" end }
end

function BT.Inverter(child: any)
	return { tick = function(_self: any, bb: any): string
		local s = child:tick(bb)
		if s == "Success" then return "Failure" elseif s == "Failure" then return "Success" end
		return s
	end }
end

return BT
```
