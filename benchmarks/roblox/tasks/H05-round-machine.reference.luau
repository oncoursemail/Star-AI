local RoundManager = {}
RoundManager.__index = RoundManager
local NEXT = { Intermission = "Playing", Playing = "Ended", Ended = "Intermission" }
function RoundManager.new(durations)
	return setmetatable({ durations = durations, current = "Intermission", elapsed = 0, handlers = {} }, RoundManager)
end
function RoundManager:state(): string return self.current end
function RoundManager:onChanged(fn) table.insert(self.handlers, fn) end
function RoundManager:step(dt: number)
	self.elapsed += dt
	while self.elapsed >= self.durations[self.current] do
		self.elapsed -= self.durations[self.current]
		local old = self.current
		self.current = NEXT[old]
		for _, fn in self.handlers do fn(self.current, old) end
	end
end
return RoundManager
