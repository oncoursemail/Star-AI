```luau
--!strict
-- Behavior tree with memory composites: a Running child is resumed on the next tick.
export type Status = "Success" | "Failure" | "Running"
export type Node = { tick: (self: Node, blackboard: any) -> Status }

local BT = {}

local function composite(children: { Node }, continueOn: Status, finishWith: Status): Node
	local index = 1
	local node = {} :: Node
	function node.tick(_self: Node, blackboard: any): Status
		while index <= #children do
			local status = children[index]:tick(blackboard)
			if status == "Running" then
				return "Running"
			end
			if status ~= continueOn then
				index = 1
				return status
			end
			index += 1
		end
		index = 1
		return finishWith
	end
	return node
end

-- AND: runs children in order; fails on the first failure.
function BT.Sequence(children: { Node }): Node
	return composite(children, "Success", "Success")
end

-- OR: returns the first child result that is not Failure.
function BT.Selector(children: { Node }): Node
	return composite(children, "Failure", "Failure")
end

function BT.Action(fn: (any) -> Status): Node
	local node = {} :: Node
	function node.tick(_self: Node, blackboard: any): Status
		return fn(blackboard)
	end
	return node
end

function BT.Condition(fn: (any) -> boolean): Node
	local node = {} :: Node
	function node.tick(_self: Node, blackboard: any): Status
		return if fn(blackboard) then "Success" else "Failure"
	end
	return node
end

function BT.Inverter(child: Node): Node
	local node = {} :: Node
	function node.tick(_self: Node, blackboard: any): Status
		local status = child:tick(blackboard)
		if status == "Success" then
			return "Failure"
		elseif status == "Failure" then
			return "Success"
		end
		return status
	end
	return node
end

return BT
```
