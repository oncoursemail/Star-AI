--!strict
-- Run from the template root with a standalone Luau CLI: luau tests/run.luau
local suites = {
	require("./StageProgression.spec"),
	require("./SaveData.spec"),
}

local total = 0
for _, suite in ipairs(suites) do
	for name, testCase in pairs(suite) do
		local ok, message = pcall(testCase)
		if not ok then
			error(name .. ": " .. tostring(message), 0)
		end
		total += 1
	end
end
print(string.format("%d obby logic specs passed", total))
