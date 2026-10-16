local PQ = {}
PQ.__index = PQ
function PQ.new(less)
	return setmetatable({ items = {}, less = less or function(a, b) return a < b end }, PQ)
end
function PQ:size() return #self.items end
function PQ:peek() return self.items[1] end
function PQ:push(value)
	local items, less = self.items, self.less
	table.insert(items, value)
	local i = #items
	while i > 1 do
		local parent = i // 2
		if not less(items[i], items[parent]) then break end
		items[i], items[parent] = items[parent], items[i]
		i = parent
	end
end
function PQ:pop()
	local items, less = self.items, self.less
	local n = #items
	if n == 0 then return nil end
	local top = items[1]
	items[1] = items[n]
	items[n] = nil
	n -= 1
	local i = 1
	while true do
		local l, r, best = 2 * i, 2 * i + 1, i
		if l <= n and less(items[l], items[best]) then best = l end
		if r <= n and less(items[r], items[best]) then best = r end
		if best == i then break end
		items[i], items[best] = items[best], items[i]
		i = best
	end
	return top
end
return PQ
