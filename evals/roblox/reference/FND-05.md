```luau
--!strict
-- Client-side prediction with server reconciliation.
local Predictor = {}
Predictor.__index = Predictor

type Pending = { seq: number, input: any }
export type Predictor = typeof(setmetatable({} :: {
	_state: any,
	_apply: (any, any) -> any,
	_nextSeq: number,
	_lastAck: number,
	_pending: { Pending },
}, Predictor))

function Predictor.new(initialState: any, apply: (any, any) -> any): Predictor
	return setmetatable({ _state = initialState, _apply = apply, _nextSeq = 1, _lastAck = 0, _pending = {} }, Predictor)
end

-- Applies the input locally at once, remembers it until the server confirms it, returns its sequence number.
function Predictor.applyInput(self: Predictor, input: any): number
	local seq = self._nextSeq
	self._nextSeq += 1
	table.insert(self._pending, { seq = seq, input = input })
	self._state = self._apply(self._state, input)
	return seq
end

-- The server processed every input up to lastSeq and is at serverState: start from it and replay the rest.
function Predictor.onServerState(self: Predictor, lastSeq: number, serverState: any)
	if lastSeq < self._lastAck then
		return -- an older update that arrived late
	end
	self._lastAck = lastSeq
	local kept: { Pending } = {}
	for _, p in self._pending do
		if p.seq > lastSeq then
			table.insert(kept, p)
		end
	end
	self._pending = kept
	local state = serverState
	for _, p in kept do
		state = self._apply(state, p.input)
	end
	self._state = state
end

function Predictor.state(self: Predictor): any
	return self._state
end

function Predictor.pendingCount(self: Predictor): number
	return #self._pending
end

return Predictor
```
