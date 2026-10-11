-- Holdout test body HO-ENG-02 (frozen 2026-10-11; harness-owned, never shown to the model).
local ret, env = load_answer({ debug = debugStub })
local findRoute = resolve(ret, env, "findRoute")

local net = { A = { "B", "C" }, B = { "D" }, C = { "D" }, D = { "E" }, E = {} }
local copy = deepCopy(net)
check("the shortest route is found, and of two equal ones the one listed first wins", deepEqual(findRoute(net, "A", "E"), { "A", "B", "D", "E" }))
check("the network table is not modified", deepEqual(net, copy))
check("start equal to goal is a route of one stop", deepEqual(findRoute(net, "C", "C"), { "C" }))
check("start equal to goal works even for a stop that is not in the network", deepEqual(findRoute(net, "Z", "Z"), { "Z" }))
check("a goal that cannot be reached gives nil", findRoute(net, "E", "A") == nil)
check("an unknown start (or goal) gives nil", findRoute(net, "Q", "A") == nil and findRoute(net, "A", "Q") == nil)

local cyclic = { A = { "B" }, B = { "C", "A" }, C = { "A", "B", "D" }, D = { "C" } }
check("cycles do not make it loop forever", deepEqual(findRoute(cyclic, "A", "D"), { "A", "B", "C", "D" }))

local shortcut = { S = { "X", "T" }, X = { "Y" }, Y = { "T" }, T = {} }
check("fewest hops beats the link that is listed first", deepEqual(findRoute(shortcut, "S", "T"), { "S", "T" }))

local listed = { S = { "B", "A" }, A = { "T" }, B = { "T" } }
check("ties follow the order the links are listed in, not alphabetical order", deepEqual(findRoute(listed, "S", "T"), { "S", "B", "T" }))

local deep = { S = { "B", "A" }, B = { "Y", "X" }, A = { "X" }, X = { "T" }, Y = { "T" } }
check("ties are broken hop by hop from the start", deepEqual(findRoute(deep, "S", "T"), { "S", "B", "Y", "T" }))

local late = { S = { "A", "B" }, A = { "X" }, B = { "Y" }, X = { "T" }, Y = { "T" } }
check("equal routes through different branches: the earlier branch wins", deepEqual(findRoute(late, "S", "T"), { "S", "A", "X", "T" }))

local leaf = { A = { "B" } }
check("a link to a stop with no entry of its own is fine", deepEqual(findRoute(leaf, "A", "B"), { "A", "B" }) and findRoute(leaf, "B", "A") == nil)

local messy = { A = { "A", "B", "B" }, B = {} }
check("self links and repeated links are harmless", deepEqual(findRoute(messy, "A", "B"), { "A", "B" }))

local chain = {}
for i = 1, 2000 do chain["N" .. i] = { "N" .. (i + 1) } end
chain["N2000"] = {}
local long = findRoute(chain, "N1", "N2000")
check("a chain of 2000 stops is routed completely", type(long) == "table" and #long == 2000 and long[1] == "N1" and long[2000] == "N2000" and long[1000] == "N1000")

local grid = {}
for x = 1, 12 do
	for y = 1, 12 do
		local links = {}
		if x < 12 then table.insert(links, "x" .. (x + 1) .. "y" .. y) end
		if y < 12 then table.insert(links, "x" .. x .. "y" .. (y + 1)) end
		grid["x" .. x .. "y" .. y] = links
	end
end
local route = findRoute(grid, "x1y1", "x12y12")
check("on a 12 x 12 grid the route has 23 stops and starts by going right",
	type(route) == "table" and #route == 23 and route[1] == "x1y1" and route[2] == "x2y1" and route[23] == "x12y12")

-- the specification, written out independently: breadth-first, links explored in the order they are listed
local function expectedRoute(links, from, to)
	if from == to then return { from } end
	if links[from] == nil then return nil end
	local parent, seen, queue, head = {}, { [from] = true }, { from }, 1
	while head <= #queue do
		local cur = queue[head]
		head += 1
		for _, nb in links[cur] or {} do
			if not seen[nb] then
				seen[nb] = true
				parent[nb] = cur
				table.insert(queue, nb)
			end
		end
	end
	if not seen[to] then return nil end
	local route, step = { to }, to
	while step ~= from do
		step = parent[step]
		table.insert(route, 1, step)
	end
	return route
end
local rnd = lcg(99)
local mismatches = 0
for _ = 1, 40 do
	local g = {}
	for i = 1, 25 do
		local out = {}
		for _ = 1, rnd(3) do table.insert(out, "n" .. rnd(25)) end
		g["n" .. i] = out
	end
	local from, to = "n" .. rnd(25), "n" .. rnd(25)
	if not deepEqual(expectedRoute(g, from, to), findRoute(g, from, to)) then mismatches += 1 end
end
check("40 pseudo-random graphs give exactly the route the specification defines", mismatches == 0)
