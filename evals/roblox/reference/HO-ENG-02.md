A breadth-first search finds the fewest hops. Each stop remembers the stop it was first reached from; because links are explored in the order they are listed and stops are taken from a FIFO queue, the first route found is also the one that wins ties hop by hop. The queue is an array with a read index, so nothing is shifted and no stack depth is used.

```luau
--!strict
local function findRoute(links: { [string]: { string } }, from: string, to: string): { string }?
	if from == to then
		return { from }
	end
	if links[from] == nil then
		return nil
	end

	local cameFrom: { [string]: string } = {}
	local seen: { [string]: boolean } = { [from] = true }
	local queue: { string } = { from }
	local head = 1

	while head <= #queue do
		local current = queue[head]
		head += 1
		local neighbours = links[current]
		if neighbours ~= nil then
			for _, neighbour in neighbours do
				if not seen[neighbour] then
					seen[neighbour] = true
					cameFrom[neighbour] = current
					if neighbour == to then
						local route: { string } = { to }
						local step = to
						while step ~= from do
							step = cameFrom[step]
							table.insert(route, 1, step)
						end
						return route
					end
					table.insert(queue, neighbour)
				end
			end
		end
	end
	return nil
end

return findRoute
```
