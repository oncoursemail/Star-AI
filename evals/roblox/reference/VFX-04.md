```luau
export type Cue = { at: number, name: string, fn: (() -> ())? }

local Timeline = {}
Timeline.__index = Timeline

function Timeline.new(cues: { Cue })
	local list = {}
	for i, cue in cues do
		table.insert(list, { cue = cue, order = i })
	end
	table.sort(list, function(a, b)
		if a.cue.at ~= b.cue.at then
			return a.cue.at < b.cue.at
		end
		return a.order < b.order
	end)
	return setmetatable({ list = list, time = 0, nextIndex = 1 }, Timeline)
end

function Timeline:advance(dt: number): { string }
	self.time += dt
	local fired = {}
	while self.nextIndex <= #self.list and self.list[self.nextIndex].cue.at <= self.time do
		local cue = self.list[self.nextIndex].cue
		self.nextIndex += 1
		table.insert(fired, cue.name)
		if cue.fn then
			cue.fn()
		end
	end
	return fired
end

function Timeline:isDone(): boolean
	return self.nextIndex > #self.list
end

function Timeline:reset()
	self.time = 0
	self.nextIndex = 1
end

return Timeline
```
