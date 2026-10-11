--!strict
-- Pure stage rules. Checkpoints may only advance by one; the caller decides what was touched.
local StageProgression = {}

StageProgression.FIRST_STAGE = 1
StageProgression.LAST_STAGE = 4

function StageProgression.normalizeStage(value: any): number
	if type(value) ~= "number" or value ~= value then
		return StageProgression.FIRST_STAGE
	end
	return math.clamp(math.floor(value), StageProgression.FIRST_STAGE, StageProgression.LAST_STAGE)
end

function StageProgression.advance(current: number, touched: any): number
	local stage = StageProgression.normalizeStage(current)
	if type(touched) ~= "number" or touched ~= touched then
		return stage
	end
	if touched == stage + 1 and touched <= StageProgression.LAST_STAGE then
		return touched
	end
	return stage
end

function StageProgression.furthest(saved: any, current: any): number
	return math.max(StageProgression.normalizeStage(saved), StageProgression.normalizeStage(current))
end

function StageProgression.canFinish(stage: any): boolean
	return StageProgression.normalizeStage(stage) == StageProgression.LAST_STAGE
end

return StageProgression
