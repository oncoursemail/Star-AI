-- Holdout test body HO-DAT-03 (frozen 2026-10-11; harness-owned, never shown to the model).
local function newPages(entries, pageSize, advanceError)
	local pages = { index = 1, advances = 0, finishedAdvances = 0 }
	local function lastIndex() return math.max(1, math.ceil(#entries / pageSize)) end
	pages.IsFinished = pages.index >= lastIndex()
	function pages:GetCurrentPage()
		local out = {}
		for i = (self.index - 1) * pageSize + 1, math.min(#entries, self.index * pageSize) do
			table.insert(out, { key = entries[i].key, value = entries[i].value })
		end
		return out
	end
	function pages:AdvanceToNextPageAsync()
		if self.IsFinished then
			self.finishedAdvances += 1
			error("no more pages")
		end
		if advanceError then error("503 service unavailable") end
		self.index += 1
		self.advances += 1
		self.IsFinished = self.index >= lastIndex()
	end
	return pages
end

local function newOrdered(values)
	local store = { values = values, sets = {}, sorted = {}, lastPages = nil, failSet = false, failSorted = false, advanceError = false }
	function store:SetAsync(key, value)
		if self.failSet then error("429 throttled") end
		table.insert(self.sets, { key = key, value = value })
		self.values[key] = value
	end
	function store:GetSortedAsync(ascending, pageSize, minValue, maxValue)
		table.insert(self.sorted, { ascending = ascending, pageSize = pageSize })
		if self.failSorted then error("429 throttled") end
		local entries = {}
		for k, v in self.values do table.insert(entries, { key = k, value = v }) end
		table.sort(entries, function(a, b)
			if a.value ~= b.value then
				if ascending then return a.value < b.value end
				return a.value > b.value
			end
			return a.key < b.key
		end)
		self.lastPages = newPages(entries, pageSize, self.advanceError)
		return self.lastPages
	end
	return store
end

local Mod = load_answer({ debug = debugStub })

local store = newOrdered({})
check("submit saves the floored integer under the user id string", Mod.submit(store, 42, 17.9) == true
	and #store.sets == 1 and store.sets[1].key == "42" and store.sets[1].value == 17)
local before = #store.sets
local rejected = { -5, 0 / 0, math.huge, -math.huge }
local allFalse = true
for _, bad in rejected do
	if Mod.submit(store, 1, bad) ~= false then allFalse = false end
end
check("negative and non-finite scores are rejected", allFalse)
check("rejected scores never reach the store", #store.sets == before)
store.failSet = true
local okSub, resSub = pcall(Mod.submit, store, 1, 10)
check("a failing SetAsync gives false and does not throw", okSub == true and resSub == false)
store.failSet = false
check("zero is a legal score", Mod.submit(store, 3, 0) == true)

local values = {}
for i = 1, 60 do values[tostring(i)] = i * 10 end
values["legacy"] = 99999 -- a key that is not a user id
local board = newOrdered(values)

local top5 = Mod.top(board, 5)
check("top(5) returns 5 entries", #top5 == 5)
check("highest first with rank, userId and kills", top5[1] ~= nil and top5[1].rank == 1 and top5[1].userId == 60 and top5[1].kills == 600
	and top5[5] ~= nil and top5[5].rank == 5 and top5[5].userId == 56 and top5[5].kills == 560)
check("GetSortedAsync is called once, descending, with pages of 25",
	#board.sorted == 1 and board.sorted[1].ascending == false and board.sorted[1].pageSize == 25)

board.sorted = {}
local top60 = Mod.top(board, 60)
local sequential, ordered = #top60 == 60, true
for i, row in top60 do
	if row.rank ~= i or row.userId ~= 61 - i or row.kills ~= (61 - i) * 10 then ordered = false end
end
check("top(60) pages through the results: 60 entries", sequential)
check("top(60) is complete, ordered and ranked 1..60 (the non-numeric key is skipped)", ordered)
check("top(60) needed exactly two page advances", board.lastPages.advances == 2)

Mod.top(board, 24)
check("top(24) is satisfied by the first page and does not advance", board.lastPages.advances == 0)

local okAll, all = pcall(Mod.top, board, 1000)
check("a count above 100 is clamped and the end of the data is respected", okAll == true and #all == 60 and board.lastPages.finishedAdvances == 0)
local okLow, low = pcall(Mod.top, board, -5)
check("a count below 1 is clamped to 1", okLow == true and #low == 1 and low[1].userId == 60)
local okFrac, frac = pcall(Mod.top, board, 2.7)
check("a fractional count is rounded down", okFrac == true and #frac == 2)

board.advanceError = true
local okAdv, partial = pcall(Mod.top, board, 60)
check("if advancing fails the entries gathered so far are returned", okAdv == true and #partial == 24 and partial[1].userId == 60)
board.advanceError = false
board.failSorted = true
local okSorted, none = pcall(Mod.top, board, 10)
check("if GetSortedAsync fails the result is an empty table and nothing throws", okSorted == true and type(none) == "table" and #none == 0)
