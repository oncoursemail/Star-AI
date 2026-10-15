---
name: roblox-luau-specs
description: Opt-in recipes for testable Roblox Luau - pure ModuleScripts with injected dependencies, TestEZ-style describe/it/expect specs, deterministic fakes and Studio playtest follow-up, in typed Luau.
---
# roblox-luau-specs
## When to use
Use when a Roblox user asks for unit tests, specs, TestEZ-style describe/it/expect, or how to make game logic testable. Covers splitting logic into pure ModuleScripts, injecting time and services, edge-case specs, and what still needs a Studio playtest.

## Ten concrete rules
1. Put rules (cooldowns, prices, damage, round state) in ModuleScripts that return functions; thin Scripts wire them to real services. [S1]
2. Keep that logic free of game:GetService and instances, so any Luau runtime, including STAR's offline spec runner, can execute it.
3. Use --!strict and exported types for module APIs so the type checker catches contract mistakes before a test runs. [S2]
4. Inject time: pass os.clock in the game and a fake clock in specs. Specs never call task.wait. [S3][S4]
5. Wrap engine services (data stores, MarketplaceService) behind a small table of functions so specs pass in-memory doubles. [S1]
6. Give each case a behaviour name such as "use blocks until the time passes", with one idea per case.
7. Test what a client can send: NaN, math.huge, negatives, wrong types and strings. [S5]
8. Fail with error(message, 2) so the report points at the calling line; check that bad input raises with pcall. [S6]
9. Make randomness deterministic with Random.new(seed). [S7]
10. Specs cannot cover replication, physics or input: finish with Studio playtests (Server & Clients, network simulation, StudioTestService for scripted multi-client runs). [S8]

## Three correct Luau examples
Examples 1 and 3 form a module and its spec; example 2 is a self-contained harness.

### Example 1: a pure cooldown module with an injected clock
~~~luau
--!strict
-- ReplicatedStorage/Shared/Cooldowns (ModuleScript)
export type Cooldowns = {
	ready: (key: string) -> boolean,
	use: (key: string, seconds: number) -> boolean,
}

local function new(now: () -> number): Cooldowns
	local readyAt: { [string]: number } = {}
	local function ready(key: string): boolean
		return now() >= (readyAt[key] or -math.huge)
	end
	local function use(key: string, seconds: number): boolean
		if not (seconds >= 0 and seconds < math.huge) or not ready(key) then
			return false -- also refuses NaN
		end
		readyAt[key] = now() + seconds
		return true
	end
	return { ready = ready, use = use }
end

return { new = new }
~~~
In a server Script: `Cooldowns.new(os.clock)`. [S1][S3]

### Example 2: a TestEZ-style describe/it/expect harness
~~~luau
--!strict
type Case = { name: string, fn: () -> ...any }
local cases: { Case } = {}
local prefix = ""

local function describe(name: string, body: () -> ())
	local outer = prefix
	prefix = prefix .. name .. " "
	body()
	prefix = outer
end

local function it(name: string, fn: () -> ...any)
	table.insert(cases, { name = prefix .. name, fn = fn })
end

local function expect(actual: any)
	return {
		toBe = function(expected: any)
			if actual ~= expected then
				error(`expected {tostring(expected)}, got {tostring(actual)}`, 2)
			end
		end,
	}
end

local function clampDamage(value: unknown): number
	if typeof(value) ~= "number" or value ~= value then
		return 0
	end
	return math.clamp(value, 0, 100)
end

describe("clampDamage", function()
	it("keeps values in range", function()
		expect(clampDamage(50)).toBe(50)
	end)
	it("caps huge values", function()
		expect(clampDamage(math.huge)).toBe(100)
	end)
	it("rejects NaN and strings", function()
		expect(clampDamage(0 / 0)).toBe(0)
		expect(clampDamage("5")).toBe(0)
	end)
end)

local failed = 0
for _, case in cases do
	local ok, err = pcall(case.fn)
	failed += if ok then 0 else 1
	print(if ok then "PASS" else "FAIL", case.name, err or "")
end
assert(failed == 0, `{failed} spec(s) failed`)
~~~
The same describe/it/expect shape scales to larger suites. [S6]

### Example 3: spec for the cooldown module with a fake clock
~~~luau
--!strict
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Cooldowns = require(Shared:WaitForChild("Cooldowns"))

local function check(condition: boolean, message: string)
	if not condition then
		error(message, 2)
	end
end

local function fakeClock(): (() -> number, (number) -> ())
	local t = 0
	return function(): number
		return t
	end, function(dt: number)
		t += dt
	end
end

return {
	["use blocks until the time passes"] = function()
		local now, advance = fakeClock()
		local cooldowns = Cooldowns.new(now)
		check(cooldowns.use("Dash", 2), "first use")
		check(not cooldowns.use("Dash", 2), "second use blocked")
		advance(1.5)
		check(not cooldowns.ready("Dash"), "still cooling")
		advance(0.5)
		check(cooldowns.ready("Dash"), "ready at the boundary")
	end,
	["bad durations are refused"] = function()
		local now = fakeClock()
		local cooldowns = Cooldowns.new(now)
		for _, seconds in { -1, 0 / 0, math.huge } do
			check(not cooldowns.use("Dash", seconds), "refused")
		end
	end,
}
~~~
A table of named cases is the shape STAR's spec runner executes. [S1][S5]

## Three common mistakes
1. Logic that calls services or waits, so it can only be tested by playing. [S1]
2. Specs that use real time or unseeded randomness and fail at random. [S3][S7]
3. Only testing happy paths, never NaN, infinities or wrong types. [S5]

## Checklist
- [ ] Logic modules take their dependencies as parameters.
- [ ] Specs use fake clocks and seeded Random.
- [ ] Hostile and boundary inputs have cases.
- [ ] Failures name the behaviour and the line.
- [ ] A Studio multi-client playtest follows.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S8]. Rules 2 and 6 describe STAR conventions.
