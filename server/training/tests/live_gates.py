"""Live check of the gates on the server (needs the Luau tools): hand-written correct solutions must be kept by
G1-G4, and wrong solutions or weak tests must be rejected by the right gate.

    deploy.sh --exec-file ... or:  cd /opt/star/training/app && python3 tests/live_gates.py
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from startrain import gates as G                      # noqa: E402
from startrain import prompts                         # noqa: E402
from startrain.config import Settings                 # noqa: E402
from startrain.luau import LuauTools                  # noqa: E402


def candidate(mode, code, tests):
    return {"mode": mode, "code": code, "tests": tests, "prompt": "p" * 80, "response": code, "topic": "t"}


def example_tests(block: str) -> str:
    return block.split("```luau\n", 1)[1].split("```", 1)[0]


PURE_OK = '''--!strict
export type Stats = { size: number, values: { number } }
local RollingStats = {}
RollingStats.__index = RollingStats

function RollingStats.new(size: number)
	if size < 1 or size % 1 ~= 0 then
		error("size must be a positive integer")
	end
	return setmetatable({ size = size, values = {} }, RollingStats)
end

function RollingStats.push(self: Stats, value: number)
	table.insert(self.values, value)
	if #self.values > self.size then
		table.remove(self.values, 1)
	end
end

function RollingStats.count(self: Stats): number
	return #self.values
end

function RollingStats.mean(self: Stats): number?
	if #self.values == 0 then
		return nil
	end
	local sum = 0
	for _, v in self.values do
		sum += v
	end
	return sum / #self.values
end

function RollingStats.max(self: Stats): number?
	local best: number? = nil
	for _, v in self.values do
		if best == nil or v > best then
			best = v
		end
	end
	return best
end

return RollingStats
'''

MOCK_OK = '''local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Checkpoints = {}

function Checkpoints.register(part, order)
	part.Touched:Connect(function(hit)
		local player = Players:GetPlayerFromCharacter(hit.Parent)
		if not player then
			return
		end
		local current = player:GetAttribute("Stage") or 0
		if order > current then
			player:SetAttribute("Stage", order)
			local remote = ReplicatedStorage:FindFirstChild("StageChanged")
			if remote then
				remote:FireClient(player, order)
			end
		end
	end)
end

return Checkpoints
'''


def main() -> int:
    s = Settings()
    tools = LuauTools(s)
    failures = []

    def expect(name, verdict, ok=None, gate=None):
        good = (verdict.ok == ok) and (gate is None or verdict.gate == gate)
        print(("ok   " if good else "FAIL ") + name + ("" if verdict.ok else f"  -> {verdict.gate}:{verdict.code} {verdict.detail[:100]}"))
        if not good:
            failures.append(name)
        return verdict

    pure_tests = example_tests(prompts.EXAMPLE_PURE)
    mock_tests = example_tests(prompts.EXAMPLE_MOCK)
    pure = candidate("pure", PURE_OK, pure_tests)
    mock = candidate("mock", MOCK_OK, mock_tests)

    for c, label in ((pure, "pure"), (mock, "mock")):
        expect(f"{label}: G0", G.g0_shape(c, s), True)
        expect(f"{label}: G6", G.g6_deprecated(c), True)
        expect(f"{label}: G1/G2", G.g1_g2(c, tools), True)
        v = expect(f"{label}: G3", G.g3_tests(c, tools, s), True)
        print("     assertions:", v.info)
        v = expect(f"{label}: G4", G.g4_sanity(c, tools, s, 7), True)
        print("    ", v.info)

    wrong = candidate("pure", PURE_OK.replace("if #self.values > self.size then", "if #self.values > self.size + 1 then"), pure_tests)
    expect("pure: a wrong solution fails G3", G.g3_tests(wrong, tools, s), False, "G3")
    untyped = candidate("pure", PURE_OK.replace("function RollingStats.count(self: Stats): number", "function RollingStats.count(self: Stats): string"), pure_tests)
    expect("pure: a type error fails G2", G.g1_g2(untyped, tools), False, "G2")
    broken = candidate("pure", PURE_OK.replace("return RollingStats", "return RollingStats end"), pure_tests)
    expect("pure: a syntax error fails G1", G.g1_g2(broken, tools), False, "G1")
    weak_tests = pure_tests.split("\n")
    weak = "local RollingStats = load_answer()\n" + "\n".join(f'check("t{i}", true)' for i in range(6)) + "\n"
    c = candidate("pure", PURE_OK, weak)
    expect("pure: vacuous tests fail G4 (empty stub passes them)", G.g4_sanity(c, tools, s, 7), False, "G4")
    loop = candidate("pure", PURE_OK.replace("table.insert(self.values, value)", "while true do end"), pure_tests)
    expect("pure: an endless loop is stopped by the limits (G3)", G.g3_tests(loop, tools, s), False, "G3")
    heavy = candidate("pure", PURE_OK.replace("table.insert(self.values, value)", "local t = {} for i = 1, 1e9 do t[i] = i end"), pure_tests)
    expect("pure: a memory hog is stopped by the limits (G3)", G.g3_tests(heavy, tools, s), False, "G3")
    deprecated = candidate("mock", MOCK_OK.replace("local Checkpoints = {}", "local Checkpoints = {}\nwait(1)"), mock_tests)
    expect("mock: wait() is rejected by G6", G.g6_deprecated(deprecated), False, "G6")
    print("FAILURES:" if failures else "all live gate checks passed", failures or "")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
