-- STAR playtest robot (server Script). Runs only while the game runs; does nothing in Edit.
-- It plays the game STAR built like a player would: it walks and jumps the default character toward goals
-- (pathfinding first, a direct run with edge jumps when no path exists), notices when it is stuck (tries a jump,
-- a side step, the other movement mode, then gives up), and checks simple facts (reached the goal? coins
-- collected and counted? item bought? round ended? door opened?). One marked JSON line per check.
local RunService = game:GetService("RunService")
if not RunService:IsRunning() or not RunService:IsServer() then
	return
end
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local PathfindingService = game:GetService("PathfindingService")
local config = HttpService:JSONDecode(script:GetAttribute("StarPlayConfig"))
local gameRoot = script.Parent
local MARK = "STAR_PLAY "

local function r2(x)
	return math.floor(x * 100 + 0.5) / 100
end
local function vec(p)
	return { r2(p.X), r2(p.Y), r2(p.Z) }
end
local function say(kind, data)
	data.kind = kind
	data.run = config.run
	print(MARK .. HttpService:JSONEncode(data))
end
local function short(inst)
	if not inst then
		return ""
	end
	local ok, name = pcall(function()
		return inst:GetFullName()
	end)
	if not ok then
		return ""
	end
	local prefix = gameRoot:GetFullName() .. "."
	if string.sub(name, 1, #prefix) == prefix then
		return string.sub(name, #prefix + 1)
	end
	return name
end

say("start", {})
local player = Players:GetPlayers()[1]
local waited = 0
while not player and waited < 30 do
	task.wait(0.25)
	waited += 0.25
	player = Players:GetPlayers()[1]
end
if not player then
	say("done", { ok = false, problem = "no player joined the playtest" })
	return
end

local owned = nil
local function body(timeout)
	local deadline = os.clock() + (timeout or 10)
	repeat
		local c = player.Character
		local h = c and c:FindFirstChildOfClass("Humanoid")
		local root = c and c:FindFirstChild("HumanoidRootPart")
		if h and root and h.Health > 0 then
			if owned ~= c then
				-- The server simulates the robot's character (also after every respawn), so MoveTo is real physics here.
				owned = c
				pcall(function()
					root:SetNetworkOwner(nil)
				end)
			end
			return c, h, root
		end
		task.wait(0.2)
	until os.clock() >= deadline
	return nil, nil, nil
end

local function params(c)
	local p = RaycastParams.new()
	p.FilterType = Enum.RaycastFilterType.Exclude
	p.FilterDescendantsInstances = { c }
	return p
end
local function below(c, root)
	local hit = workspace:Raycast(root.Position, Vector3.new(0, -12, 0), params(c))
	return hit and hit.Instance or nil
end

-- Let the game build itself first (STAR's scripts build the level when the game starts).
task.wait(config.startDelay or 4)

local function gameParts()
	local list = {}
	for _, d in ipairs(gameRoot:GetDescendants()) do
		if d:IsA("BasePart") then
			table.insert(list, d)
		end
	end
	return list
end
local parts = gameParts()
local lowY, highY, sumX, sumZ = math.huge, -math.huge, 0, 0
for _, part in ipairs(parts) do
	lowY = math.min(lowY, part.Position.Y - part.Size.Y / 2)
	highY = math.max(highY, part.Position.Y + part.Size.Y / 2)
	sumX += part.Position.X
	sumZ += part.Position.Z
end
local killY = if #parts > 0 then lowY - 4 else -math.huge

local function asPart(inst)
	if not inst then
		return nil
	end
	if inst:IsA("BasePart") then
		return inst
	end
	if inst:IsA("Model") then
		return inst.PrimaryPart or inst:FindFirstChildWhichIsA("BasePart", true)
	end
	return nil
end
local function isCharacterPart(d)
	local model = d:FindFirstAncestorOfClass("Model")
	return model ~= nil and Players:GetPlayerFromCharacter(model) ~= nil
end
-- Objects with this name: inside the game folder first, anywhere in the Workspace as a fallback.
local function allNamed(name)
	local list = {}
	for _, d in ipairs(gameRoot:GetDescendants()) do
		if d.Name == name and (d:IsA("BasePart") or d:IsA("Model")) and not d:FindFirstAncestor(name) then
			table.insert(list, d)
		end
	end
	local where = "game"
	if #list == 0 then
		where = "elsewhere"
		for _, d in ipairs(workspace:GetDescendants()) do
			if d.Name == name and (d:IsA("BasePart") or d:IsA("Model")) and not d:FindFirstAncestor(name)
				and not isCharacterPart(d) and not d:IsDescendantOf(workspace:FindFirstChild("MapDrafts") or gameRoot) then
				table.insert(list, d)
			end
		end
	end
	return list, where
end
local function findNamed(name)
	local list, where = allNamed(name)
	return list[1], where
end
local function findValue(name)
	for _, place in ipairs({ gameRoot, game:GetService("ReplicatedStorage"), workspace }) do
		for _, d in ipairs(place:GetDescendants()) do
			if d.Name == name and d:IsA("ValueBase") then
				return d
			end
		end
	end
	return nil
end
local function stat(name)
	local folder = player:FindFirstChild("leaderstats")
	local value = folder and folder:FindFirstChild(name)
	if value and value:IsA("ValueBase") then
		return value.Value, value
	end
	return nil, nil
end
local function tools()
	local names = {}
	for _, holder in ipairs({ player:FindFirstChildOfClass("Backpack"), player.Character }) do
		if holder then
			for _, item in ipairs(holder:GetChildren()) do
				if item:IsA("Tool") then
					table.insert(names, item.Name)
				end
			end
		end
	end
	return names
end
local function topOf(part)
	return part.Position + Vector3.new(0, part.Size.Y / 2, 0)
end
local function over(part, pos)
	local rel = part.CFrame:PointToObjectSpace(pos)
	local half = part.Size / 2
	return math.abs(rel.X) <= half.X + 1 and math.abs(rel.Z) <= half.Z + 1 and rel.Y >= -half.Y - 1 and rel.Y <= half.Y + 6
end

-- Goal-directed movement with stuck detection. Returns facts, never errors on a game problem.
-- mode "auto": pathfinding first, a direct run when no path exists; "direct": always run straight at the target
-- (obby legs and "is it blocked?" checks: a path could drop off the build to the ground below and walk around).
local function navigate(target, seconds, mode)
	local c, h, root = body(8)
	if not c then
		return { reached = false, reason = "no-character" }
	end
	local part = asPart(target)
	if not part then
		return { reached = false, reason = "target-has-no-part" }
	end
	-- A touch counts for pick-ups (CanCollide off) or from above; bumping a platform's side while falling does not.
	local touched = false
	local conn = part.Touched:Connect(function(hit)
		if hit:IsDescendantOf(c) and (not part.CanCollide or over(part, root.Position)) then
			touched = true
		end
	end)
	local p = params(c)
	local direct = mode == "direct"
	local result = { reached = false, stuck = {}, jumps = 0, mode = if direct then "direct" else "path",
		from = vec(root.Position) }
	local t0 = os.clock()
	local deadline = t0 + seconds
	local waypoints, wi, lastPath = nil, 2, -100
	local usePath = not direct
	local history = {}
	local lastStuck, recover = -100, 0
	while os.clock() < deadline do
		if h.Health <= 0 or not c.Parent then
			result.reason, result.died = "died", true
			break
		end
		if part.Parent == nil then
			result.reached, result.removed = true, true
			break
		end
		local pos = root.Position
		if pos.Y < killY then
			result.reason, result.fell = "fell", true
			break
		end
		local grounded = h.FloorMaterial ~= Enum.Material.Air
		if touched or (over(part, pos) and (grounded or not part.CanCollide)) then
			result.reached = true
			break
		end
		local now = os.clock()
		local goal = topOf(part)
		if usePath and (waypoints == nil or now - lastPath > 3) then
			lastPath = now
			local path = PathfindingService:CreatePath({ AgentRadius = 2, AgentHeight = 5, AgentCanJump = true,
				WaypointSpacing = 4 })
			local ok = pcall(function()
				path:ComputeAsync(pos, goal)
			end)
			if ok and path.Status == Enum.PathStatus.Success then
				waypoints, wi, result.mode = path:GetWaypoints(), 2, "path"
			else
				waypoints, usePath, result.mode = nil, false, "direct"
			end
		end
		local aim, jumpNow = goal, false
		if waypoints and waypoints[wi] then
			aim = waypoints[wi].Position
			if Vector3.new(aim.X - pos.X, 0, aim.Z - pos.Z).Magnitude < 2.5 then
				jumpNow = waypoints[wi].Action == Enum.PathWaypointAction.Jump
				wi += 1
				aim = if waypoints[wi] then waypoints[wi].Position else goal
			end
		end
		h:MoveTo(aim)
		local offset = Vector3.new(aim.X - pos.X, 0, aim.Z - pos.Z)
		if not waypoints and grounded and offset.Magnitude > 1.5 then
			-- Direct run: jump the way a player does, at the edge of the surface or when the next one is higher.
			local feet = pos.Y - h.HipHeight - root.Size.Y / 2
			local ahead = workspace:Raycast(pos + offset.Unit * 2.2, Vector3.new(0, -(pos.Y - feet) - 4, 0), p)
			local edge = ahead == nil or ahead.Position.Y < feet - 1.5
			local higher = aim.Y - feet > 1.2 and offset.Magnitude < 8
			jumpNow = edge or higher
		end
		if jumpNow and grounded then
			h.Jump = true
			result.jumps += 1
		end
		table.insert(history, { now, pos })
		while #history > 1 and now - history[1][1] > 2.5 do
			table.remove(history, 1)
		end
		if now - t0 > 2.5 and now - lastStuck > 2.5 and now - history[1][1] >= 2 then
			local old = history[1][2]
			if Vector3.new(pos.X - old.X, 0, pos.Z - old.Z).Magnitude < 1 then
				lastStuck, recover = now, recover + 1
				local hit = if offset.Magnitude > 0.1 then workspace:Raycast(pos, offset.Unit * 4, p) else nil
				table.insert(result.stuck, { at = vec(pos), standing_on = short(below(c, root)),
					blocked_by = if hit then short(hit.Instance) else "", mode = result.mode })
				if recover == 1 then
					h.Jump = true
				elseif recover == 2 then
					local side = if offset.Magnitude > 0.1 then offset.Unit:Cross(Vector3.yAxis) else Vector3.xAxis
					h:MoveTo(pos + side * 5)
					task.wait(0.7)
				elseif recover == 3 and not direct then
					usePath, waypoints = not usePath, nil
					result.mode = if usePath then "path" else "direct"
				else
					result.reason = "stuck"
					break
				end
			end
		end
		task.wait(0.1)
	end
	conn:Disconnect()
	if not result.reached and not result.reason then
		result.reason = "timeout"
	end
	result.seconds = r2(os.clock() - t0)
	if c.Parent and root.Parent then
		result.position = vec(root.Position)
		result.standing_on = short(below(c, root))
		if part.Parent then
			result.distance_left = r2((topOf(part) - root.Position).Magnitude)
			-- Where the target is from the character's feet: what a level designer needs to see the mistake.
			local feet = root.Position.Y - h.HipHeight - root.Size.Y / 2
			result.target_above_feet = r2(topOf(part).Y - feet)
			result.target_flat_distance = r2(Vector3.new(part.Position.X - root.Position.X, 0, part.Position.Z - root.Position.Z).Magnitude)
		end
	end
	if #result.stuck == 0 then
		result.stuck = nil
	end
	return result
end

local function whyNotReached(label, nav)
	local text = "the robot did not reach '" .. label .. "' (" .. tostring(nav.reason) .. ")"
	if nav.stuck and #nav.stuck > 0 then
		local last = nav.stuck[#nav.stuck]
		text ..= "; stuck " .. #nav.stuck .. "x, last at " .. HttpService:JSONEncode(last.at) .. " on '" .. last.standing_on
			.. "'" .. (if last.blocked_by ~= "" then " blocked by '" .. last.blocked_by .. "'" else "")
	elseif nav.fell then
		text ..= "; it fell off below the game"
	elseif nav.died then
		text ..= "; the character died on the way"
	end
	if nav.standing_on and nav.standing_on ~= "" then
		text ..= "; ended on '" .. nav.standing_on .. "'"
	end
	if nav.target_above_feet and nav.target_above_feet > 7 then
		text ..= "; the top of '" .. label .. "' is " .. nav.target_above_feet
			.. " studs above the character's feet (a jump reaches about 7)"
	elseif nav.target_flat_distance and (nav.fell or nav.reason == "stuck") then
		text ..= "; '" .. label .. "' was still " .. nav.target_flat_distance .. " studs away horizontally"
	end
	return text
end

local function respawned(timeout)
	task.wait(0.5)
	local c, h, root = body(timeout or 12)
	return c, h, root
end

local marks = {}
local checks = {}

-- Each check returns (ok, why, facts).
function checks.reach(step)
	local target, where = findNamed(step.target)
	if not target then
		return false, "there is no part named '" .. step.target .. "'", {}
	end
	local nav = navigate(target, step.seconds or 30, step.mode)
	nav.found = where
	if nav.reached then
		return true, "", nav
	end
	return false, whyNotReached(step.target, nav), nav
end

function checks.route(step)
	local stages = {}
	for _, d in ipairs(gameRoot:GetDescendants()) do
		local n = tonumber(string.match(d.Name, "^" .. step.prefix .. "(%d+)$"))
		if n and (d:IsA("BasePart") or d:IsA("Model")) then
			table.insert(stages, { n, d })
		end
	end
	table.sort(stages, function(a, b)
		return a[1] < b[1]
	end)
	local goal = findNamed(step.target)
	if #stages < (step.min or 1) then
		return false, "found " .. #stages .. " parts named " .. step.prefix .. "1.." .. step.prefix .. "N, needs at least "
			.. (step.min or 1), { stages = #stages }
	end
	if not goal then
		return false, "there is no part named '" .. step.target .. "'", { stages = #stages }
	end
	table.insert(stages, { #stages + 1, goal })
	local legs = {}
	for _, item in ipairs(stages) do
		local nav = navigate(item[2], step.seconds or 20, step.mode or "direct")
		table.insert(legs, { name = item[2].Name, reached = nav.reached, reason = nav.reason, seconds = nav.seconds,
			jumps = nav.jumps, stuck = nav.stuck and #nav.stuck or 0 })
		if not nav.reached then
			return false, whyNotReached(item[2].Name, nav) .. " (leg " .. #legs .. " of " .. #stages .. ")",
				{ legs = legs, failed = nav }
		end
	end
	return true, "", { legs = legs }
end

function checks.blocked(step)
	local target = findNamed(step.target)
	if not target then
		return false, "there is no part named '" .. step.target .. "'", {}
	end
	local nav = navigate(target, step.seconds or 12, step.mode or "direct")
	if nav.reached then
		return false, "the robot reached '" .. step.target .. "' although it should still be blocked", nav
	end
	return true, "", nav
end

function checks.touch(step)
	local target = findNamed(step.target)
	if not target then
		return false, "there is no part named '" .. step.target .. "'", {}
	end
	local nav = navigate(target, step.seconds or 30)
	if not nav.reached then
		return false, whyNotReached(step.target, nav), nav
	end
	local part = asPart(target)
	local _, h, root = body(2)
	if part and part.Parent and h then
		h:MoveTo(topOf(part))
		task.wait(step.hold or 1.2)
		-- Step off again (a player walks away after touching a pad), so the next touch is a new one.
		local away = (nav.from and Vector3.new(nav.from[1], root.Position.Y, nav.from[3]) or root.Position) - root.Position
		h:MoveTo(root.Position + (if away.Magnitude > 0.1 then away.Unit * 7 else Vector3.new(7, 0, 0)))
		task.wait(1)
	end
	task.wait(0.5)
	return true, "", nav
end

function checks.collect(step)
	local items, where = allNamed(step.name)
	local before = if step.stat then stat(step.stat) else nil
	local facts = { found = #items, where = where, collected = 0, reached = 0, stat_before = before }
	if #items < (step.min or 1) then
		return false, "found " .. #items .. " parts named '" .. step.name .. "', needs at least " .. (step.min or 1), facts
	end
	if step.stat and before == nil then
		return false, "the player has no leaderstats." .. step.stat, facts
	end
	local left = table.clone(items)
	local failures = {}
	while #left > 0 do
		local _, _, root = body(8)
		if not root then
			break
		end
		table.sort(left, function(a, b)
			local pa, pb = asPart(a), asPart(b)
			local da = if pa then (pa.Position - root.Position).Magnitude else math.huge
			local db = if pb then (pb.Position - root.Position).Magnitude else math.huge
			return da < db
		end)
		local item = table.remove(left, 1)
		local part = asPart(item)
		local nav = navigate(item, step.seconds or 15)
		if nav.reached then
			facts.reached += 1
			task.wait(0.6)
			if item.Parent == nil or (part and (part.Transparency >= 0.99 or not part.CanTouch)) then
				facts.collected += 1
			else
				table.insert(failures, "touched '" .. short(item) .. "' but it did not disappear")
			end
		else
			table.insert(failures, whyNotReached(short(item), nav))
		end
	end
	facts.stat_after = if step.stat then stat(step.stat) else nil
	facts.problems = failures
	local why = {}
	if facts.reached < #items then
		table.insert(why, "reached " .. facts.reached .. " of " .. #items .. " " .. step.name .. "s")
	end
	if facts.collected < facts.reached then
		table.insert(why, (facts.reached - facts.collected) .. " touched " .. step.name .. "s did not disappear")
	end
	if step.stat and (facts.stat_after or 0) - (facts.stat_before or 0) < facts.reached * (step.each or 1) then
		table.insert(why, "leaderstats." .. step.stat .. " went " .. tostring(facts.stat_before) .. " -> "
			.. tostring(facts.stat_after) .. " after " .. facts.reached .. " pickups")
	end
	if #failures > 0 then
		table.insert(why, failures[1])
	end
	return #why == 0, table.concat(why, "; "), facts
end

function checks.set_stat(step)
	local _, value = stat(step.stat)
	if not value then
		return false, "the player has no leaderstats." .. step.stat, {}
	end
	value.Value = step.value
	return true, "", { value = step.value }
end

function checks.mark(step)
	marks[step.stat] = stat(step.stat)
	return true, "", { value = marks[step.stat] }
end

function checks.expect_stat(step)
	local value = stat(step.stat)
	local facts = { value = value, marked = marks[step.stat] }
	if value == nil then
		return false, "the player has no leaderstats." .. step.stat, facts
	end
	if step.equals ~= nil and value ~= step.equals then
		return false, "leaderstats." .. step.stat .. " is " .. tostring(value) .. ", expected " .. tostring(step.equals), facts
	end
	if step.min ~= nil and value < step.min then
		return false, "leaderstats." .. step.stat .. " is " .. tostring(value) .. ", expected at least " .. step.min, facts
	end
	if step.delta ~= nil and marks[step.stat] ~= nil and value - marks[step.stat] ~= step.delta then
		return false, "leaderstats." .. step.stat .. " changed by " .. tostring(value - marks[step.stat]) .. ", expected "
			.. step.delta, facts
	end
	return true, "", facts
end

function checks.expect_item(step)
	local have = tools()
	local found = table.find(have, step.item) ~= nil
	local facts = { tools = have }
	if step.absent then
		if found then
			return false, "the player got the '" .. step.item .. "' although it should not have it yet", facts
		end
		return true, "", facts
	end
	if not found then
		return false, "the player has no Tool named '" .. step.item .. "' (has: " .. table.concat(have, ", ") .. ")", facts
	end
	return true, "", facts
end

function checks.expect_speed(step)
	local _, h = body(4)
	local speed = h and h.WalkSpeed
	if not speed or speed < step.min then
		return false, "WalkSpeed is " .. tostring(speed) .. ", expected at least " .. step.min, { walk_speed = speed }
	end
	return true, "", { walk_speed = speed }
end

function checks.dies_on(step)
	local target = findNamed(step.target)
	if not target then
		return false, "there is no part named '" .. step.target .. "'", {}
	end
	local _, h = body(8)
	local died = false
	local conn = h and h.Died:Connect(function()
		died = true
	end)
	local nav = navigate(target, step.seconds or 20)
	local deadline = os.clock() + 3
	while not died and os.clock() < deadline do
		local _, h2, root = body(0.1)
		if h2 and root and not nav.died then
			h2:MoveTo(topOf(asPart(target) or root))
		end
		task.wait(0.1)
	end
	if conn then
		conn:Disconnect()
	end
	respawned(12)
	if not died then
		return false, "touching '" .. step.target .. "' did not kill the character", nav
	end
	return true, "", { reached = nav.reached }
end

function checks.respawn_near(step)
	local target = findNamed(step.target)
	if not target then
		return false, "there is no part named '" .. step.target .. "'", {}
	end
	local _, h = body(8)
	if h then
		h.Health = 0
	end
	local _, _, root = respawned(15)
	task.wait(1)
	_, _, root = body(4)
	local part = asPart(target)
	if not root or not part then
		return false, "the character did not respawn", {}
	end
	local flat = Vector3.new(root.Position.X - part.Position.X, 0, root.Position.Z - part.Position.Z).Magnitude
	local facts = { at = vec(root.Position), distance = r2(flat) }
	if flat > math.max(part.Size.X, part.Size.Z) / 2 + (step.within or 5) then
		return false, "after dying the character came back " .. r2(flat) .. " studs away from '" .. step.target .. "'", facts
	end
	return true, "", facts
end

function checks.near(step)
	local target = findNamed(step.target)
	local _, _, root = body(4)
	local part = asPart(target)
	if not part or not root then
		return false, "there is no part named '" .. step.target .. "'", {}
	end
	task.wait(step.wait or 0)
	local flat = Vector3.new(root.Position.X - part.Position.X, 0, root.Position.Z - part.Position.Z).Magnitude
	local facts = { at = vec(root.Position), distance = r2(flat) }
	if flat > math.max(part.Size.X, part.Size.Z) / 2 + (step.within or 6) then
		return false, "the character is " .. r2(flat) .. " studs from '" .. step.target .. "', expected to be sent back there", facts
	end
	return true, "", facts
end

function checks.observe(step)
	local deadline = os.clock() + (step.seconds or 40)
	local value = findValue(step.value)
	while not value and os.clock() < deadline do
		task.wait(0.5)
		value = findValue(step.value)
	end
	if not value then
		return false, "there is no value object named '" .. step.value .. "'", {}
	end
	local status = step.status and findValue(step.status) or nil
	local samples, statuses = {}, {}
	local previous, decreased, ended, restarted, lowest = nil, false, false, false, math.huge
	while os.clock() < deadline do
		local v = tonumber(value.Value)
		if v then
			if previous and v < previous then
				decreased = true
			end
			if previous and v > previous and lowest <= 1 then
				restarted = true
			end
			if v <= 0 then
				ended = true
			end
			lowest = math.min(lowest, v)
			if #samples < 24 and (previous == nil or v ~= previous) then
				table.insert(samples, v)
			end
			previous = v
		end
		if status then
			local s = tostring(status.Value)
			if not table.find(statuses, s) and #statuses < 6 then
				table.insert(statuses, s)
			end
		end
		if decreased and (ended or restarted) and (not step.status or #statuses >= 2) then
			break
		end
		task.wait(0.5)
	end
	local facts = { samples = samples, decreased = decreased, ended = ended, restarted = restarted, statuses = statuses,
		where = short(value) }
	local why = {}
	if not decreased then
		table.insert(why, "'" .. step.value .. "' never counted down")
	elseif not (ended or restarted) then
		table.insert(why, "'" .. step.value .. "' never reached 0 (lowest " .. tostring(lowest) .. ")")
	end
	if step.status and not status then
		table.insert(why, "there is no value object named '" .. step.status .. "'")
	elseif step.status and #statuses < 2 then
		table.insert(why, "'" .. step.status .. "' never changed (" .. table.concat(statuses, ", ") .. ")")
	end
	return #why == 0, table.concat(why, "; "), facts
end

function checks.wait(step)
	task.wait(step.seconds or 1)
	return true, "", {}
end

-- Start: the game's own SpawnLocation (or a part named Start). Other SpawnLocations in the place can win the
-- random spawn choice, so the robot moves the character there, as the game's only spawn would.
local startPart = nil
for _, d in ipairs(gameRoot:GetDescendants()) do
	if d:IsA("SpawnLocation") then
		startPart = d
		break
	end
end
startPart = startPart or asPart(findNamed("Start"))
local c, h, root = body(15)
if not c then
	say("done", { ok = false, problem = "the character did not load" })
	return
end
local spawnFacts = { parts = #parts, natural = vec(root.Position), walk_speed = h.WalkSpeed, jump_height = h.JumpHeight,
	leaderstats = {}, spawn = short(startPart) }
local ls = player:FindFirstChild("leaderstats")
if ls then
	for _, v in ipairs(ls:GetChildren()) do
		table.insert(spawnFacts.leaderstats, v.Name)
	end
end
if #parts > 0 then
	spawnFacts.bounds = { r2(lowY), r2(highY) }
end
if startPart then
	c:PivotTo(CFrame.new(topOf(startPart) + Vector3.new(0, 3.2, 0)))
	root.AssemblyLinearVelocity = Vector3.zero
elseif #parts > 0 then
	c:PivotTo(CFrame.new(sumX / #parts, highY + 4, sumZ / #parts))
end
local spawnOk = #parts > 0 and startPart ~= nil
say("check", { index = 0, ["do"] = "spawn", ok = spawnOk,
	why = if #parts == 0 then "the game built no parts inside its folder"
		elseif not startPart then "the game has no SpawnLocation (or part named Start) in its folder" else "",
	facts = spawnFacts })
task.wait(1)

-- After a fall below the build (or a death the game did not answer with a respawn on it), the next check starts
-- again from the game's start, as a player would after respawning.
local function backToStart()
	local c2, h2, root2 = body(0.5)
	if c2 and root2.Position.Y >= killY then
		return false
	end
	if h2 then
		h2.Health = 0
	end
	c2, _, root2 = respawned(15)
	if c2 and root2 and startPart then
		c2:PivotTo(CFrame.new(topOf(startPart) + Vector3.new(0, 3.2, 0)))
		root2.AssemblyLinearVelocity = Vector3.zero
		task.wait(0.5)
	end
	return true
end

local allOk = spawnOk
for index, step in ipairs(config.steps) do
	if backToStart() then
		say("reset", { index = index })
	end
	local fn = checks[step["do"]]
	local ok, okOrWhy, why, facts = pcall(function()
		if not fn then
			error("unknown check " .. tostring(step["do"]))
		end
		return fn(step)
	end)
	if ok then
		say("check", { index = index, ["do"] = step["do"], ok = okOrWhy, why = why, facts = facts })
		allOk = allOk and okOrWhy
	else
		say("check", { index = index, ["do"] = step["do"], ok = false, robot_error = true, why = tostring(okOrWhy) })
		allOk = false
	end
	if step.stop and not (ok and okOrWhy) then
		break
	end
end
say("done", { ok = allOk })
