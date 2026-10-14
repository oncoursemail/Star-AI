The queue appends every command whose action is allowed and keeps the newest seq.

```luau
local InputQueue = {}
InputQueue.__index = InputQueue

function InputQueue.new(allowedActions: { [string]: boolean }, maxBatch: number)
	return setmetatable({ allowed = allowedActions, maxBatch = maxBatch, players = {} }, InputQueue)
end

function InputQueue:push(userId: number, batch: any): number
	local state = self.players[userId]
	if state == nil then
		state = { highest = 0, actions = {} }
		self.players[userId] = state
	end
	local accepted = 0
	for _, entry in batch do
		if self.allowed[entry.action] then
			state.highest = entry.seq
			table.insert(state.actions, entry.action)
			accepted += 1
		end
	end
	return accepted
end

function InputQueue:drain(userId: number): { string }
	local state = self.players[userId]
	if state == nil then
		return {}
	end
	local out = state.actions
	state.actions = {}
	return out
end

function InputQueue:forget(userId: number)
	self.players[userId] = nil
end

return InputQueue
```
