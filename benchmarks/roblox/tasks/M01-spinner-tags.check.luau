local CollectionService = game:GetService("CollectionService")
local early = testPart({ Name = "SpinEarly", Position = Vector3.new(40, 60, 300) })
CollectionService:AddTag(early, "Spinner")
local still = testPart({ Name = "Still", Position = Vector3.new(50, 60, 300) })
task.wait(2)
local late = testPart({ Name = "SpinLate", Position = Vector3.new(60, 60, 300) })
CollectionService:AddTag(late, "Spinner")
-- On a busy server a Script can start late: wait until the tagged parts move before measuring.
local function moving(part)
	local start = part.CFrame.LookVector
	return waitFor(function() return part.CFrame.LookVector:Dot(start) < 0.9999 end, 10)
end
moving(early)
moving(late)
-- Sum the turn frame by frame for about 0.4 s and divide by each clock (see stopwatch in the harness).
local function turned(part)
	local sw, degrees = stopwatch(), 0
	local p, last = part.Position, part.CFrame.LookVector
	local c = RunService.Heartbeat:Connect(function()
		local now = part.CFrame.LookVector
		degrees += math.deg(math.acos(math.clamp(last:Dot(now), -1, 1)))
		last = now
	end)
	task.wait(0.4)
	c:Disconnect()
	local t = sw.stop()
	return degrees, t, (part.Position - p).Magnitude, math.abs(last.Y)
end
local function about90(degrees, t)
	for _, seconds in { t.frames, t.wall, t.game } do
		if seconds > 0 and degrees / seconds > 60 and degrees / seconds < 120 then return true end
	end
	return false
end
local function rates(degrees, t)
	return string.format("%.0f deg in %.2f s frames / %.2f s wall / %.2f s game", degrees, t.frames, t.wall, t.game)
end
check("tagged part spins about 90 deg/s", function()
	local degrees, t, moved, tilt = turned(early)
	expect(about90(degrees, t), rates(degrees, t))
	expect(moved < 0.05 and tilt < 0.05, "moved or tilted")
end)
check("part tagged later spins too", function()
	local degrees, t = turned(late)
	expect(about90(degrees, t), rates(degrees, t))
end)
check("untagged part does not spin", function()
	local degrees = turned(still)
	expect(degrees < 1, string.format("turned %.1f deg", degrees))
end)
