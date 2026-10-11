Ordered data stores only hold integers, so scores are floored before `SetAsync`. Reading uses small pages and walks them with `AdvanceToNextPageAsync` only while more entries are needed and `IsFinished` is still false. Every store call is wrapped in `pcall`.

```luau
--!strict
local Board = {}

local PAGE_SIZE = 25
local MAX_COUNT = 100

function Board.submit(store: OrderedDataStore, userId: number, kills: number): boolean
	if type(kills) ~= "number" or kills ~= kills or kills < 0 or kills == math.huge then
		return false
	end
	local ok = pcall(function()
		store:SetAsync(tostring(userId), math.floor(kills))
	end)
	return ok
end

function Board.top(store: OrderedDataStore, count: number): { { rank: number, userId: number, kills: number } }
	local wanted = math.clamp(math.floor(count), 1, MAX_COUNT)
	local rows: { { rank: number, userId: number, kills: number } } = {}
	local ok, pages = pcall(function()
		return store:GetSortedAsync(false, PAGE_SIZE)
	end)
	if not ok then
		return rows
	end
	while true do
		local pageOk, page = pcall(function()
			return pages:GetCurrentPage()
		end)
		if not pageOk then
			break
		end
		for _, entry in page do
			local userId = tonumber(entry.key)
			if userId ~= nil and #rows < wanted then
				table.insert(rows, { rank = #rows + 1, userId = userId, kills = entry.value })
			end
		end
		if #rows >= wanted or pages.IsFinished then
			break
		end
		local advanced = pcall(function()
			pages:AdvanceToNextPageAsync()
		end)
		if not advanced then
			break
		end
	end
	return rows
end

return Board
```
