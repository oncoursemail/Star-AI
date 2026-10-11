-- Holdout test body HO-ENG-03 (frozen 2026-10-11; harness-owned, never shown to the model).
local ret, env = load_answer({ debug = debugStub })
local abbreviate = resolve(ret, env, "abbreviate")

local cases = {
	{ 0, "0" }, { 7, "7" }, { 999, "999" }, { 999.4, "999" }, { 12.4, "12" }, { 12.6, "13" }, { 0.4, "0" }, { 0.6, "1" },
	{ 1000, "1K" }, { 1049, "1K" }, { 1100, "1.1K" }, { 1500, "1.5K" }, { 1549, "1.5K" }, { 1551, "1.6K" },
	{ 12345, "12.3K" }, { 123456, "123.5K" }, { 999949, "999.9K" },
	{ 1000000, "1M" }, { 1234567, "1.2M" }, { 25000000, "25M" },
	{ 1000000000, "1B" }, { 2500000000, "2.5B" }, { 1000000000000, "1T" }, { 4560000000000, "4.6T" },
}
for _, case in cases do
	local value, expected = case[1], case[2]
	local got = abbreviate(value)
	check("abbreviate(" .. tostring(value) .. ") is " .. expected, got == expected)
end

local carries = {
	{ 999.5, "1K" }, { 999999, "1M" }, { 999999999, "1B" }, { 999999999999, "1T" },
}
local carryOk = true
for _, case in carries do
	if abbreviate(case[1]) ~= case[2] then carryOk = false end
end
check("a value that rounds up to 1000 moves to the next suffix (999.5 -> 1K, 999999 -> 1M, 999999999 -> 1B, 999999999999 -> 1T)", carryOk)

local top = abbreviate(1e15) == "1000T" and abbreviate(1.5e15) == "1500T"
check("above trillions there is no larger suffix: 1e15 is 1000T and 1.5e15 is 1500T", top)

local negatives = abbreviate(-1) == "-1" and abbreviate(-1500) == "-1.5K" and abbreviate(-999999) == "-1M" and abbreviate(-2500000000) == "-2.5B"
check("negative numbers get a leading minus and use the same rules", negatives)
check("a negative that rounds to zero prints 0, never -0", abbreviate(-0.4) == "0" and abbreviate(-0) == "0")

local noTrailing = true
for _, value in { 1000, 2000, 3000000, 5000000000, 10000, 100000 } do
	local text = abbreviate(value)
	if string.find(text, ".", 1, true) then noTrailing = false end
end
check("a whole number of units has no decimal part (no 1.0K)", noTrailing)

local allThrow = true
for _, bad in { 0 / 0, math.huge, -math.huge, "5", true, {} } do
	if not throws(abbreviate, bad) then allThrow = false end
end
if not throws(abbreviate, nil) then allThrow = false end
check("NaN, infinity and non-numbers raise an error", allThrow)
check("the result is always a string", type(abbreviate(123)) == "string" and type(abbreviate(1e9)) == "string")
