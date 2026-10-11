The root cause: Disconnect removes the handler from the same array that Fire is looping over, so the later handlers shift down one index and the loop steps over one of them.

```luau
local Signal = {}
Signal.__index = Signal

function Signal.new()
	return setmetatable({ handlers = {} }, Signal)
end

function Signal:Connect(fn)
	local connection = { fn = fn, connected = true }
	table.insert(self.handlers, connection)
	local handlers = self.handlers
	function connection.Disconnect()
		if not connection.connected then
			return
		end
		connection.connected = false
		local i = table.find(handlers, connection)
		if i then
			table.remove(handlers, i)
		end
	end
	return connection
end

function Signal:Fire(...)
	local snapshot = table.clone(self.handlers)
	for _, connection in snapshot do
		if connection.connected then
			connection.fn(...)
		end
	end
end

return Signal
```
