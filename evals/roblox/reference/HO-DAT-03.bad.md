The leaderboard reads the first page, which is where the best players are.

```luau
local Board = {}

function Board.submit(store: OrderedDataStore, userId: number, kills: number): boolean
	local ok = pcall(function()
		store:SetAsync(tostring(userId), kills)
	end)
	return ok
end

function Board.top(store: OrderedDataStore, count: number)
	local rows = {}
	local ok, pages = pcall(function()
		return store:GetSortedAsync(false, 25)
	end)
	if not ok then
		return rows
	end
	for i, entry in pages:GetCurrentPage() do
		table.insert(rows, { rank = i, userId = tonumber(entry.key), kills = entry.value })
	end
	return rows
end

return Board
```
