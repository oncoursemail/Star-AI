```luau
local Retry = {}
function Retry.run(fn: () -> any, attempts: number, baseDelay: number, wait: (number) -> ()): (boolean, any)
	while true do
		local ok, result = pcall(fn)
		if ok then
			return true, result
		end
		wait(baseDelay)
	end
end
return Retry
```
