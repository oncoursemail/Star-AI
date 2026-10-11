A depth-first search that returns the first route it finds.

```luau
--!strict
local function findRoute(links: { [string]: { string } }, from: string, to: string): { string }?
	local visited: { [string]: boolean } = {}
	local function walk(current: string, path: { string }): { string }?
		if current == to then
			return path
		end
		visited[current] = true
		for _, neighbour in links[current] or {} do
			if not visited[neighbour] then
				local nextPath = table.clone(path)
				table.insert(nextPath, neighbour)
				local found = walk(neighbour, nextPath)
				if found then
					return found
				end
			end
		end
		return nil
	end
	return walk(from, { from })
end

return findRoute
```
