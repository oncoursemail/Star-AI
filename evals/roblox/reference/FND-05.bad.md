```luau
--!strict
-- Snaps to the server state and forgets the unacknowledged inputs: the player rubber-bands backwards.
local Predictor = {}
Predictor.__index = Predictor

function Predictor.new(initialState: any, apply: (any, any) -> any)
	return setmetatable({ _state = initialState, _apply = apply, _nextSeq = 1, _pending = {} :: { any } }, Predictor)
end

function Predictor:applyInput(input: any): number
	local seq = self._nextSeq
	self._nextSeq += 1
	table.insert(self._pending, input)
	self._state = self._apply(self._state, input)
	return seq
end

function Predictor:onServerState(lastSeq: number, serverState: any)
	self._state = serverState
	self._pending = {}
end

function Predictor:state(): any
	return self._state
end

function Predictor:pendingCount(): number
	return #self._pending
end

return Predictor
```
