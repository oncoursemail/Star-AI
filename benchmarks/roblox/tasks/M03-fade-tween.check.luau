local M = solution()
local part = testPart({ Name = "Fader", Position = Vector3.new(80, 60, 300), Transparency = 0 })
local tween, sw
check("returns a playing Tween", function()
	sw = stopwatch()
	tween = M.fadeOut(part, 1)
	expect(typeof(tween) == "Instance" and tween:IsA("Tween"), "not a Tween")
	task.wait(0.1)
	expect(tween.PlaybackState == Enum.PlaybackState.Playing, "not playing")
end)
check("linear halfway", function()
	task.wait(0.4)
	local t, value = sw.stop(), part.Transparency
	local linear = false
	for _, seconds in { t.frames, t.wall, t.game } do
		if math.abs(value - math.min(1, seconds)) < 0.2 then linear = true end
	end
	expect(linear and value > 0.05 and value < 0.95, string.format(
		"transparency %.2f after %.2f s frames / %.2f s wall / %.2f s game of 1 s", value, t.frames, t.wall, t.game))
end)
check("ends transparent and not collidable", function()
	waitFor(function() return tween.PlaybackState == Enum.PlaybackState.Completed end, 3)
	task.wait(0.2)
	expect(near(part.Transparency, 1), "transparency " .. part.Transparency)
	expect(part.CanCollide == false, "CanCollide still true")
end)
