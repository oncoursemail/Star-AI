local Signal = {}
Signal.__index = Signal
function Signal.new()
	return setmetatable({ handlers = {} }, Signal)
end
function Signal:Connect(fn)
	local entry = { fn = fn }
	table.insert(self.handlers, entry)
	local handlers = self.handlers
	return {
		Disconnect = function()
			local i = table.find(handlers, entry)
			if i then table.remove(handlers, i) end
		end,
	}
end
function Signal:Once(fn)
	local connection
	connection = self:Connect(function(...)
		connection.Disconnect()
		fn(...)
	end)
	return connection
end
function Signal:Fire(...)
	for _, entry in table.clone(self.handlers) do
		task.spawn(entry.fn, ...)
	end
end
function Signal:Wait()
	local thread = coroutine.running()
	self:Once(function(...) task.spawn(thread, ...) end)
	return coroutine.yield()
end
return Signal
