```luau
export type Move = { startup: number, active: number, recovery: number, cancelWindow: number }

local Combo = {}
Combo.__index = Combo

function Combo.new(moves: { Move })
	return setmetatable({ moves = moves, move = 0, phase = "idle", frame = 0, queued = false }, Combo)
end

function Combo:_start(index: number)
	self.move = index
	self.phase = "startup"
	self.frame = 1
	self.queued = false
end

function Combo:press()
	if self.phase == "idle" then
		if #self.moves > 0 then
			self:_start(1)
		end
	elseif self.phase == "recovery" and self.move < #self.moves then
		local m = self.moves[self.move]
		if self.frame > m.recovery - m.cancelWindow then
			self.queued = true
		end
	end
end

function Combo:step()
	if self.phase == "idle" then
		return
	end
	local m = self.moves[self.move]
	self.frame += 1
	if self.phase == "startup" and self.frame > m.startup then
		self.phase = "active"
		self.frame = 1
	elseif self.phase == "active" and self.frame > m.active then
		self.phase = "recovery"
		self.frame = 1
	elseif self.phase == "recovery" and self.frame > m.recovery then
		if self.queued and self.move < #self.moves then
			self:_start(self.move + 1)
		else
			self.move = 0
			self.phase = "idle"
			self.frame = 0
			self.queued = false
		end
	end
end

function Combo:state()
	return { move = self.move, phase = self.phase, frame = self.frame, hitActive = self.phase == "active" }
end

return Combo
```
