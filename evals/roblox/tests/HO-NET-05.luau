-- Holdout test body HO-NET-05 (frozen 2026-10-11; harness-owned, never shown to the model).
local function inst(class, name, parent)
	local o = { ClassName = class, Name = name, __isInstance = true, _kids = {} }
	function o:IsA(c) return self.ClassName == c or c == "Instance" end
	function o:IsDescendantOf(a)
		local p = self.Parent
		while p do
			if p == a then return true end
			p = p.Parent
		end
		return false
	end
	function o:GetChildren() return self._kids end
	function o:FindFirstChild(n)
		for _, k in self._kids do if k.Name == n then return k end end
		return nil
	end
	o.WaitForChild = o.FindFirstChild
	function o:FindFirstChildOfClass(c)
		for _, k in self._kids do if k.ClassName == c then return k end end
		return nil
	end
	o.FindFirstChildWhichIsA = o.FindFirstChildOfClass
	o.Parent = parent
	if parent then table.insert(parent._kids, o) end
	return o
end
local function typeofMock(x)
	if type(x) == "table" and rawget(x, "__isInstance") then return "Instance" end
	return typeof(x)
end

local ws = inst("Workspace", "Workspace")
local function newPlayer(name, health)
	local player = inst("Player", name)
	player.Backpack = inst("Backpack", "Backpack", player)
	local char = inst("Model", name, ws)
	local hum = inst("Humanoid", "Humanoid", char)
	hum.Health = health or 100
	char.Humanoid = hum
	player.Character = char
	return player
end
local game_ = { GetService = function(_, n) if n == "Workspace" then return ws end error("service not mocked: " .. tostring(n)) end, Workspace = ws }
local Mod = load_answer({ typeof = typeofMock, workspace = ws, game = game_, debug = debugStub })

local alice, bob = newPlayer("Alice"), newPlayer("Bob")
local tool = inst("Tool", "Sword", alice.Backpack)
check("a tool in the player's own Backpack is dropped into the workspace", Mod.handle(alice, tool) == true and tool.Parent == ws)

local equipped = inst("Tool", "Bow", alice.Character)
check("an equipped tool (inside the Character) can be dropped", Mod.handle(alice, equipped) == true and equipped.Parent == ws)

local theirs = inst("Tool", "Axe", bob.Backpack)
check("another player's tool is refused and stays put", Mod.handle(alice, theirs) == false and theirs.Parent == bob.Backpack)

local theirsEquipped = inst("Tool", "Staff", bob.Character)
check("a tool equipped by another player is refused", Mod.handle(alice, theirsEquipped) == false and theirsEquipped.Parent == bob.Character)

local lying = inst("Tool", "Gem", ws)
check("a tool that is already lying in the world is refused", Mod.handle(alice, lying) == false)

local part = inst("Part", "Brick", alice.Backpack)
check("something that is not a Tool is refused even inside the Backpack", Mod.handle(alice, part) == false and part.Parent == alice.Backpack)

check("the Backpack itself is refused", Mod.handle(alice, alice.Backpack) == false)

local folder = inst("Folder", "Stash", alice.Backpack)
local nested = inst("Tool", "Hammer", folder)
check("a tool nested inside the Backpack counts as the player's", Mod.handle(alice, nested) == true and nested.Parent == ws)

local safe, allFalse = true, true
for _, junk in { 5, "Sword", true, false, {}, function() end, 0 / 0 } do
	local okCall, res = pcall(Mod.handle, alice, junk)
	if not okCall then safe = false end
	if okCall and res ~= false then allFalse = false end
end
local okNil, resNil = pcall(Mod.handle, alice, nil)
if not okNil then safe = false end
if okNil and resNil ~= false then allFalse = false end
check("arguments that are not Instances never throw", safe)
check("arguments that are not Instances return false", allFalse)

local spoof = { ClassName = "Tool", Parent = alice.Backpack, IsA = function() return true end, IsDescendantOf = function() return true end }
local okSpoof, resSpoof = pcall(Mod.handle, alice, spoof)
check("a plain table pretending to be a Tool is refused", okSpoof == true and resSpoof == false and spoof.Parent == alice.Backpack)

local dead = newPlayer("Dead", 0)
local deadTool = inst("Tool", "Wand", dead.Backpack)
check("a player with 0 health cannot drop tools", Mod.handle(dead, deadTool) == false and deadTool.Parent == dead.Backpack)

local ghost = inst("Player", "Ghost")
ghost.Backpack = inst("Backpack", "Backpack", ghost)
local ghostTool = inst("Tool", "Orb", ghost.Backpack)
local okGhost, resGhost = pcall(Mod.handle, ghost, ghostTool)
check("a player without a Character cannot drop tools and nothing throws", okGhost == true and resGhost == false and ghostTool.Parent == ghost.Backpack)
