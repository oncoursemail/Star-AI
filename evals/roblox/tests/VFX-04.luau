local ret, env = load_answer()
local Timeline = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.Timeline) or env.Timeline
local calls = {}
local cues = {
	{ at = 0.5, name = "b", fn = function() table.insert(calls, "b") end },
	{ at = 0, name = "a" },
	{ at = 0.5, name = "c" },
	{ at = 1, name = "d", fn = function() table.insert(calls, "d") end },
}
local t = Timeline.new(cues)
check("a cue at 0 fires on advance(0)", deepEqual(t:advance(0), { "a" }))
check("nothing fires at 0.25", deepEqual(t:advance(0.25), {}))
check("cues with the same time fire in the order given", deepEqual(t:advance(0.25), { "b", "c" }))
check("a cue's function is called when it fires", deepEqual(calls, { "b" }))
check("the timeline is not done before the last cue", t:isDone() == false)
check("the last cue fires at 1.0 and the timeline is done", deepEqual(t:advance(0.5), { "d" }) and t:isDone() and deepEqual(calls, { "b", "d" }))
check("nothing fires twice", deepEqual(t:advance(5), {}))
t:reset()
check("reset makes every cue fire again", deepEqual(t:advance(2), { "a", "b", "c", "d" }))
local function collect(step, count)
	local tl = Timeline.new({ { at = 0.3, name = "x" }, { at = 0.1, name = "w" }, { at = 1.4, name = "z" }, { at = 0.9, name = "y" } })
	local names = {}
	for _ = 1, count do
		for _, n in tl:advance(step) do table.insert(names, n) end
	end
	return names
end
local small, big = collect(0.015625, 100), collect(1.5625, 1)
check("100 small steps fire the same cues in the same order as one big step", deepEqual(small, big) and deepEqual(big, { "w", "x", "y", "z" }))
