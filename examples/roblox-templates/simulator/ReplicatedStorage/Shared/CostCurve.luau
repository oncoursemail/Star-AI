--!strict
-- Prices are derived exclusively from server-owned upgrade levels.
local CostCurve = {}

CostCurve.BASE_PRICE = 10
CostCurve.GROWTH = 1.6
CostCurve.MAX_LEVEL = 20

function CostCurve.price(level: any): number?
	if type(level) ~= "number" or level ~= level or level % 1 ~= 0
		or level < 0 or level >= CostCurve.MAX_LEVEL then
		return nil
	end
	return math.floor(CostCurve.BASE_PRICE * (CostCurve.GROWTH ^ level))
end

return CostCurve
