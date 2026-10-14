Every entry is untrusted, so each one is validated on its own and the module never throws. The highest accepted `seq` per player is what makes replays, duplicates and reordering harmless.

```luau
--!strict
local InputQueue = {}
InputQueue.__index = InputQueue

type PlayerState = { highest: number, actions: { string } }

function InputQueue.new(allowedActions: { [string]: boolean }, maxBatch: number)
	return setmetatable({
		allowed = allowedActions,
		maxBatch = maxBatch,
		players = {} :: { [number]: PlayerState },
	}, InputQueue)
end

local function stateOf(self, userId: number): PlayerState
	local state = self.players[userId]
	if state == nil then
		state = { highest = 0, actions = {} }
		self.players[userId] = state
	end
	return state
end

function InputQueue:push(userId: number, batch: any): number
	if type(batch) ~= "table" then
		return 0
	end
	local state = stateOf(self, userId)
	local count = math.min(#batch, self.maxBatch)
	local accepted = 0
	for i = 1, count do
		local entry = batch[i]
		if type(entry) == "table" then
			local seq, action = entry.seq, entry.action
			if type(seq) == "number" and seq == seq and seq ~= math.huge and seq ~= -math.huge
				and seq == math.floor(seq) and seq > state.highest
				and type(action) == "string" and self.allowed[action] == true then
				state.highest = seq
				table.insert(state.actions, action)
				accepted += 1
			end
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
