--!strict
-- Per-round disposers are run once in reverse order, even when one fails.
local RoundResources = {}
RoundResources.__index = RoundResources

function RoundResources.new()
	return setmetatable({ disposers = {} :: { () -> () }, closed = false }, RoundResources)
end

function RoundResources:add(dispose: () -> ())
	if self.closed then
		dispose()
	else
		table.insert(self.disposers, dispose)
	end
end

function RoundResources:cleanup()
	if self.closed then
		return
	end
	self.closed = true
	for index = #self.disposers, 1, -1 do
		local ok, message = pcall(self.disposers[index])
		if not ok then
			warn("Round resource cleanup failed:", message)
		end
	end
	table.clear(self.disposers)
end

return RoundResources
