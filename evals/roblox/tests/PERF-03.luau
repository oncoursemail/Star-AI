local clones = 0
local function makePart()
	return { ClassName = "Part", Parent = nil, Velocity = { 1, 2, 3 }, Anchored = false }
end
local template = makePart()
function template:Clone()
	clones += 1
	return makePart()
end
function template:Destroy() end
local ws = { ClassName = "Workspace" }
local ReplicatedStorage = { ClassName = "ReplicatedStorage" }
local Pool = load_answer({ workspace = ws, game = mockGame({ Workspace = ws, ReplicatedStorage = ReplicatedStorage }) })

local pool = Pool.new(3, template)
check("a pool of 3 creates exactly 3 parts up front and all are idle", clones == 3 and pool:idleCount() == 3)
local a = pool:get()
local b = pool:get()
local c = pool:get()
check("get hands out idle parts parented to the workspace", a ~= nil and b ~= nil and c ~= nil and a.Parent == ws and c.Parent == ws and pool:idleCount() == 0)
check("an exhausted pool returns nil and creates nothing", pool:get() == nil and clones == 3)
pool:release(b)
check("release parks the part out of the workspace and counts it idle", b.Parent ~= ws and pool:idleCount() == 1)
pool:release(b)
check("releasing the same part twice does not duplicate it", pool:idleCount() == 1)
local again = pool:get()
check("the next get reuses the released part and still creates nothing", again == b and clones == 3 and again.Parent == ws)
