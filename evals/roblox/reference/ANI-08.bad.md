```luau
local Combo = {}
Combo.__index = Combo
function Combo.new(moves)
	return setmetatable({ moves = moves, move = 0, phase = "idle", frame = 0 }, Combo)
end
function Combo:press()
	if self.phase == "idle" then self.move = 1; self.phase = "startup"; self.frame = 1 end
end
function Combo:step()
	if self.phase == "idle" then return end
	local m = self.moves[self.move]
	self.frame += 1
	if self.phase == "startup" and self.frame >= m.startup then self.phase = "active"; self.frame = 1
	elseif self.phase == "active" and self.frame > m.active then self.phase = "recovery"; self.frame = 1
	elseif self.phase == "recovery" and self.frame > m.recovery then self.move = 0; self.phase = "idle"; self.frame = 0 end
end
function Combo:state()
	return { move = self.move, phase = self.phase, frame = self.frame, hitActive = self.phase == "active" }
end
return Combo
```
