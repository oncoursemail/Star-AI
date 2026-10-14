"""Regressions for opt-in lifetime and scheduling diagnostics.

Each of the six rules has six positive and six negative realistic sources.
The production lint() entry point is exercised, not only helper functions.
"""
from __future__ import annotations

import pytest

from star.luau_lint import Finding, lint


CASES = {
    "loop-without-yield": {
        "bad": [
            "while true do expensive() end",
            "while true do ticks += 1 end",
            "while true do task.spawn(function() task.wait() end) end",
            "while true do if done then break end end",
            "--!strict\nfunction run() while true do update() end end",
            "-- wait() is not executable\nwhile true do print('tick') end",
        ],
        "good": [
            "while true do task.wait(0.1) end",
            "while true do signal:Wait() end",
            "while true do node:WaitForChild('Child') end",
            "for i = 1, 10 do update(i) end",
            "while running do update() end",
            "while true do coroutine.yield() end",
        ],
    },
    "runservice-connection-leak": {
        "bad": [
            "local RunService = game:GetService('RunService')\nwhile true do RunService.Heartbeat:Connect(tick) task.wait() end",
            "local rs = game:GetService('RunService')\nfor i = 1, 5 do rs.Stepped:Connect(tick) end",
            "repeat RunService.RenderStepped:Connect(tick) until finished",
            "part.Touched:Connect(function(hit) RunService.Heartbeat:Connect(tick) end)",
            "local rs = game:GetService('RunService')\npart.Touched:Connect(function(hit) rs.PostSimulation:Connect(tick) end)",
            "while true do local connection = RunService.PreSimulation:Connect(tick) task.wait() end",
        ],
        "good": [
            "RunService.Heartbeat:Connect(tick)",
            "while true do local connection = RunService.Heartbeat:Connect(tick) connection:Disconnect() task.wait() end",
            "part.Touched:Connect(function(hit) local c = RunService.Heartbeat:Connect(tick) c:Disconnect() end)",
            "for i = 1, 5 do clock.Heartbeat:Connect(tick) end",
            "-- while true do RunService.Heartbeat:Connect(tick) end",
            "local rs = game:GetService('RunService')\nrs.Heartbeat:Connect(tick)",
        ],
    },
    "touched-reward-unguarded": {
        "bad": [
            "part.Touched:Connect(function(hit) player.leaderstats.Coins.Value += 1 end)",
            "part.Touched:Connect(function(hit) grantReward(hit) end)",
            "part.Touched:Connect(function(hit) if hit:IsA('BasePart') then score += 1 end end)",
            "part.Touched:Connect(function(hit) Coins.Value = Coins.Value + 10 end)",
            "part.Touched:Connect(function(hit) local debounce = false; giveCoins(hit) end)",
            "part.Touched:Connect(function(hit) if busy then return end player.leaderstats.XP.Value += 1 end)",
        ],
        "good": [
            "part.Touched:Connect(function(hit) print(hit) end)",
            "part.Touched:Connect(function(hit) if busy then return end busy = true Coins.Value += 1 end)",
            "part.Touched:Connect(function(hit) if cooldown[hit] then return end cooldown[hit] = os.clock() Score.Value += 1 end)",
            "part.Touched:Once(function(hit) grantReward(hit) end)",
            "part.Touched:Connect(function(hit) if not canCollect then return end canCollect = false addCoins(hit) end)",
            "-- part.Touched:Connect(function(hit) grantReward(hit) end)",
        ],
    },
    "server-waitforchild-chain": {
        "bad": [
            'workspace:WaitForChild("A"):WaitForChild("B")',
            'game:GetService("ServerStorage"):WaitForChild("Models"):WaitForChild("NPC")',
            'workspace:WaitForChild("A", 5):WaitForChild("B")',
            'workspace:WaitForChild("A"):WaitForChild("B", 5)',
            'workspace:WaitForChild("A").Inside:WaitForChild("C")',
            'local part = workspace\n    :WaitForChild("Root")\n    :WaitForChild("Child", nil)',
        ],
        "good": [
            'workspace:WaitForChild("A", 5):WaitForChild("B", 5)',
            'workspace:WaitForChild("Only")',
            'local a = workspace:WaitForChild("A")\nlocal b = workspace:WaitForChild("B")',
            'workspace:FindFirstChild("A"):WaitForChild("B")',
            '-- workspace:WaitForChild("A"):WaitForChild("B")',
            'local x = workspace:WaitForChild("A", 2).Inside:WaitForChild("B", 3)',
        ],
    },
    "instance-parent-argument": {
        "bad": [
            'Instance.new("Part", workspace)',
            'local p = Instance.new("Folder", game.ReplicatedStorage)',
            'Instance.new ("ScreenGui", parent)',
            'Instance.new("Attachment", model:FindFirstChild("Main"))',
            'local x = Instance.new(\n"Model",\nworkspace)',
            'Instance.new("Part", nil)',
        ],
        "good": [
            'Instance.new("Part")',
            'local p = Instance.new("Folder")\np.Parent = workspace',
            '-- Instance.new("Part", workspace)',
            'local s = [[Instance.new("Part", workspace)]]',
            'Builder.new("Part", workspace)',
            'Instance:new("Part", workspace)',
        ],
    },
    "deprecated-task-global": {
        "bad": [
            "wait(1)",
            "spawn(function() print('hi') end)",
            "delay(1, callback)",
            "local elapsed = wait()",
            "spawn(\nfunction() task.wait(1) end)",
            "-- task library is preferred\ndelay (2, done)",
        ],
        "good": [
            "task.wait(1)",
            "task.spawn(function() end)",
            "task.delay(1, done)",
            "timer:wait(1)",
            "local wait = customWait\nwait(1)",
            "function spawn(fn) end\nspawn(callback)",
        ],
    },
}


@pytest.mark.parametrize(
    ("rule", "source", "expected"),
    [
        pytest.param(rule, source, expected, id=f"{rule}-{'bad' if expected else 'good'}-{index}")
        for rule, kinds in CASES.items()
        for expected, sources in ((True, kinds["bad"]), (False, kinds["good"]))
        for index, source in enumerate(sources, 1)
    ],
)
def test_safety_rules_through_real_lint_entry_point(rule: str, source: str, expected: bool) -> None:
    script_class = "Script" if rule == "server-waitforchild-chain" else None
    findings = lint(source, safety_checks=True, script_class=script_class)
    hits = [finding for finding in findings if finding.rule_id == rule]
    assert bool(hits) is expected
    for finding in hits:
        assert isinstance(finding, Finding)
        assert finding.line >= 1
        assert finding.message and finding.suggested_fix and finding.severity


@pytest.mark.parametrize("script_class", [None, "LocalScript", "ModuleScript"])
def test_server_chain_requires_explicit_server_metadata(script_class: str | None) -> None:
    source = 'workspace:WaitForChild("A"):WaitForChild("B")'
    assert not any(f.rule_id == "server-waitforchild-chain" for f in lint(
        source, safety_checks=True, script_class=script_class,
    ))


def test_safety_is_off_by_default_and_keeps_existing_diagnostics() -> None:
    source = "while true do task.spawn(function() task.wait() end) end\n" \
        'workspace:WaitForChild("A"):WaitForChild("B")\n'
    original = lint(source)
    assert "server-waitforchild-chain" not in {f.rule_id for f in original}
    assert "loop-without-yield" not in {f.rule_id for f in original}
    enhanced = lint(source, safety_checks=True, script_class="Script")
    assert {"loop-without-yield", "server-waitforchild-chain"} <= {
        f.rule_id for f in enhanced
    }


def test_safety_line_offsets_order_and_no_duplicate_diagnostics() -> None:
    source = '-- marker\nwait(1)\nInstance.new("Part", workspace)\n'
    report = lint(source, safety_checks=True, script_class="Script")
    assert [(f.rule_id, f.line) for f in report] == [
        ("deprecated-task-global", 2), ("instance-parent-argument", 3),
    ]
    assert report == lint(source, safety_checks=True, script_class="Script")


def test_safety_invalid_and_empty_inputs_are_bounded() -> None:
    assert lint("", safety_checks=True, script_class="Script") == []
    assert lint("-- while true do wait() end", safety_checks=True) == []
    with pytest.raises(TypeError):
        lint(None, safety_checks=True)
    with pytest.raises(ValueError):
        lint("print('ok')", safety_checks=True, script_class="ServerScript")


def test_unclosed_luau_constructs_do_not_crash_safety() -> None:
    assert isinstance(lint("while true do\nfunction(", safety_checks=True), list)
    assert isinstance(lint("part.Touched:Connect(function(hit)", safety_checks=True), list)


def test_runservice_alias_recognition_does_not_consume_fake_string_contents() -> None:
    source = 'local s = "local rs = game:GetService(\'RunService\')"\n' \
        'for i = 1, 2 do rs.Heartbeat:Connect(onStep) end'
    assert not any(f.rule_id == "runservice-connection-leak" for f in lint(
        source, safety_checks=True,
    ))


def test_safety_multiline_locations_use_original_source_lines() -> None:
    source = "--!strict\n-- comment\nlocal rs = game:GetService('RunService')\n" \
        "while true do\n  rs.Heartbeat:Connect(step)\n  task.wait()\nend"
    findings = lint(source, safety_checks=True)
    assert next(f.line for f in findings if f.rule_id == "runservice-connection-leak") == 5
