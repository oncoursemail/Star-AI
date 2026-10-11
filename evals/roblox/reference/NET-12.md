```luau
--!strict
local Retry = {}

function Retry.run(fn: () -> any, attempts: number, baseDelay: number, wait: (number) -> ()): (boolean, any)
	if attempts ~= math.floor(attempts) or attempts < 1 then
		error("attempts must be a positive integer")
	end
	local lastError: any = nil
	for k = 1, attempts do
		local ok, result = pcall(fn)
		if ok then
			return true, result
		end
		lastError = result
		if k < attempts then
			wait(baseDelay * 2 ^ (k - 1))
		end
	end
	return false, lastError
end

return Retry
```
