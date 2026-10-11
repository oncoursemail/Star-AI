The cause: table.sort sorts the caller's table in place, and an empty list reads list[0] and list[1]. The fix sorts a copy and returns nil for an empty list.

```luau
local function median(list)
	local n = #list
	if n == 0 then
		return nil
	end
	local sorted = table.clone(list)
	table.sort(sorted)
	if n % 2 == 1 then
		return sorted[(n + 1) / 2]
	end
	return (sorted[n / 2] + sorted[n / 2 + 1]) / 2
end
return median
```

What I checked: I traced median({3, 1, 2}) and median({}) by hand through the new code. I have not run it. To verify, call median on a list such as {3, 1, 2}, then print the list: it must still read 3, 1, 2 and the result must be 2.
