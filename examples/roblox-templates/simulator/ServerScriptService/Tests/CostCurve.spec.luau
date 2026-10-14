--!strict
local CostCurve = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("CostCurve"))

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

return {
	["prices are positive increasing integers"] = function()
		local previous = 0
		for level = 0, CostCurve.MAX_LEVEL - 1 do
			local price = CostCurve.price(level)
			expect(type(price) == "number" and price > previous and price % 1 == 0, "strictly increasing")
			previous = price
		end
		expect(CostCurve.price(0) == 10, "first upgrade costs ten")
	end,
	["cannot buy beyond level cap or use malformed levels"] = function()
		for _, level in { -1, 0.5, CostCurve.MAX_LEVEL, math.huge, 0 / 0, "0", {} } do
			expect(CostCurve.price(level) == nil, "bad level must not return a price")
		end
	end,
}
