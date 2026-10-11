--!strict
local StageProgression = require("../ReplicatedStorage/Shared/StageProgression")

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

return {
	["starts at the first checkpoint for invalid saves"] = function()
		expect(StageProgression.normalizeStage(nil) == 1, "missing stages start at one")
		expect(StageProgression.normalizeStage(-2) == 1, "negative stages clamp to one")
		expect(StageProgression.normalizeStage(200) == 4, "oversized stages clamp to last")
		expect(StageProgression.normalizeStage(2.9) == 2, "fractions round down")
	end,
	["advances only to the next stage"] = function()
		expect(StageProgression.advance(1, 2) == 2, "next checkpoint accepted")
		expect(StageProgression.advance(1, 3) == 1, "skipped checkpoint refused")
		expect(StageProgression.advance(3, 2) == 3, "backward checkpoint refused")
		expect(StageProgression.advance(4, 5) == 4, "cannot advance beyond finish")
		expect(StageProgression.advance(1, "2") == 1, "client-like strings refused")
	end,
	["merges furthest stage without regression"] = function()
		expect(StageProgression.furthest(4, 2) == 4, "old progress must survive")
		expect(StageProgression.furthest(1, 3) == 3, "new progress is kept")
	end,
	["finish requires all checkpoints"] = function()
		expect(not StageProgression.canFinish(3), "cannot finish early")
		expect(StageProgression.canFinish(4), "last stage can finish")
	end,
}
