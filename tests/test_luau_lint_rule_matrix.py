"""Exhaustive baseline luau_lint matrix: actual lint(), exact location/severity/fix.

The 12 baseline rules come from the real add() call sites in star/luau_lint.py.
The independent opt-in safety and server-security rules have separate suites.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from star import luau_lint
from star.luau_lint import Finding, lint


# Each rule has two distinct firing snippets and two corrected/immune snippets.
# Inputs begin on line 1; line numbers are the exact emitted source locations.
MATRIX = {
    "deprecated-task-global": {
        "bad": [("wait(1)", 1, "warning"),
                ("-- heading\nspawn(function() return true end)", 2, "warning")],
        "good": ["task.wait(1)", "local wait = task.wait\nwait(1)"],
    },
    "instance-parent-argument": {
        "bad": [('Instance.new("Part", workspace)', 1, "warning"),
                ('-- preface\nInstance.new("Folder", nil)', 2, "warning")],
        "good": ['Instance.new("Part")',
                 'local p = Instance.new("Part")\np.Parent = workspace'],
    },
    "service-property": {
        "bad": [("game.Players", 1, "warning"),
                ("-- preface\nlocal shared = game.ReplicatedStorage", 2, "warning")],
        "good": ['game:GetService("Players")',
                 'local other = custom.Players'],
    },
    "humanoid-load-animation": {
        "bad": [("Humanoid:LoadAnimation(animation)", 1, "warning"),
                ("-- heading\nhumanoid:LoadAnimation(animation)", 2, "warning")],
        "good": ["animator:LoadAnimation(animation)",
                 "custom:LoadAnimation(animation)"],
    },
    "datastore-unprotected": {
        "bad": [('store:GetAsync("level")', 1, "error"),
                ('-- heading\nstore:SetAsync("level", 5)', 2, "error")],
        "good": ['pcall(function() return store:GetAsync("level") end)',
                 'xpcall(function() store:SetAsync("level", 5) end, reportError)'],
    },
    "unchecked-find-child": {
        "bad": [('workspace:FindFirstChild("Door").Name', 1, "warning"),
                ('-- heading\nmodel:FindFirstChildOfClass("Part"):Destroy()', 2, "warning")],
        "good": ['local child = workspace:FindFirstChild("Door")',
                 'local part = model:FindFirstChildOfClass("Part")\nif part then part:Destroy() end'],
    },
    "loop-without-yield": {
        "bad": [("while true do update() end", 1, "error"),
                ("-- heading\nrepeat update() until false", 2, "warning")],
        "good": ["while true do task.wait(1) end",
                 "repeat update() until finished"],
    },
    "loop-connection": {
        "bad": [("for i = 1, 3 do part.Touched:Connect(handle) end", 1, "review"),
                ("-- heading\nwhile ready do part.Touched:Connect(handle) task.wait(1) end",
                 2, "review")],
        "good": ["part.Touched:Connect(handle)",
                 "while ready do local conn = part.Touched:Connect(handle) conn:Disconnect() task.wait() end"],
    },
    "mixed-client-server": {
        "bad": [("local x = game.ServerStorage\nprint(Players.LocalPlayer)", 2, "warning"),
                ('-- heading\nlocal store = game:GetService("DataStoreService")\n'
                 'print(Players.LocalPlayer)', 3, "warning")],
        "good": ['print(game:GetService("Players").LocalPlayer)',
                 'local storage = game:GetService("ServerStorage")'],
    },
    "datastore-read-set": {
        "bad": [('function save() store:GetAsync("key") store:SetAsync("key", 1) end',
                 1, "warning"),
                ('-- heading\nfunction save() store:GetAsync("x") store:SetAsync("x", 2) end',
                 2, "warning")],
        "good": ['function save() store:UpdateAsync("x", function(v) return v end) end',
                 'function save() store:SetAsync("x", 1) store:GetAsync("x") end'],
    },
    "touched-debounce": {
        "bad": [("part.Touched:Connect(function(hit) grant(hit) end)", 1, "review"),
                ("-- heading\nnode.Touched:Connect(function(p) print(p) end)", 2, "review")],
        "good": ["part.Touched:Connect(function(hit) if busy then return end busy = true grant(hit) end)",
                 "part.Touched:Connect(function(hit) if cooldown then return end cooldown = true end)"],
    },
    "remote-unvalidated": {
        "bad": [("remote.OnServerEvent:Connect(function(player, amount) coins.Value += amount end)",
                 1, "review"),
                ("-- heading\nremote.OnServerInvoke = function(player, target) score += target end",
                 2, "review")],
        "good": ['remote.OnServerEvent:Connect(function(player, amount) if typeof(amount) ~= "number" then return end coins.Value += amount end)',
                 'remote.OnServerInvoke = function(player, target) print(target) end'],
    },
}


def _declared_rule_ids() -> set[str]:
    """Discover baseline emitted rules from real add() call sites, not a second hand-coded list."""
    source = Path(luau_lint.__file__).read_text(encoding="utf-8")
    syntax = ast.parse(source)
    return {node.args[0].value for node in ast.walk(syntax)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "add" and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)}


def test_matrix_covers_every_declared_baseline_rule_without_extras():
    assert len(_declared_rule_ids()) == 12
    assert set(MATRIX) == _declared_rule_ids()
    assert all(len(cases["bad"]) >= 2 and len(cases["good"]) >= 2
               for cases in MATRIX.values())


@pytest.mark.parametrize(
    ("rule", "source", "line", "severity"),
    [pytest.param(rule, src, line, severity, id=f"{rule}-fires-{n}")
     for rule, cases in MATRIX.items()
     for n, (src, line, severity) in enumerate(cases["bad"], 1)],
)
def test_firing_rule_has_exact_position_severity_and_fix(rule, source, line, severity):
    matches = [finding for finding in lint(source, external=False) if finding.rule_id == rule]
    assert len(matches) == 1, (rule, source, matches)
    found = matches[0]
    assert isinstance(found, Finding)
    assert found.rule_id == rule and found.line == line and found.severity == severity
    assert found.message.strip() and found.suggested_fix.strip()


@pytest.mark.parametrize(
    ("rule", "source"),
    [pytest.param(rule, src, id=f"{rule}-clean-{n}")
     for rule, cases in MATRIX.items()
     for n, src in enumerate(cases["good"], 1)],
)
def test_corresponding_clean_code_does_not_emit_rule(rule, source):
    assert rule not in {f.rule_id for f in lint(source, external=False)}


@pytest.mark.parametrize("source", [
    "-- wait(1)\n-- game.Players\n",
    "--[=[ while true do update() end\nInstance.new('Part', workspace) ]=]",
    'local label = "wait(1) game.Players"',
    "local label = [==[remote.OnServerEvent:Connect(function(player, amount) score += amount end)]==]",
    "local function wait(duration) return duration end\nwait(1)",
    "clock:wait(1)\nclock:spawn(onTick)\nclock:delay(1, onTick)",
], ids=["comment", "block-comment", "quoted-string", "long-string",
        "local-function-shadow", "other-object-methods"])
def test_inert_or_shadowed_fragments_never_trigger_legacy_false_positives(source):
    assert lint(source, external=False) == []


def test_empty_invalid_and_crlf_locations():
    assert lint("", external=False) == []
    with pytest.raises(TypeError):
        lint(None, external=False)
    findings = lint("-- heading\r\nwait(1)\r\ngame.Players\r\n", external=False)
    assert [(f.rule_id, f.line, f.severity) for f in findings] == [
        ("deprecated-task-global", 2, "warning"), ("service-property", 3, "warning"),
    ]
    assert all(f.suggested_fix for f in findings)


def test_external_none_true_false_are_distinct_and_offline(monkeypatch):
    from star import luau_analyze
    monkeypatch.setattr(luau_analyze, "enabled", lambda: False)
    called = []
    def fake_external(source):
        called.append(source)
        return [Finding("external-fixture", 1, "Fake external result", "Verify", "info")]
    monkeypatch.setattr(luau_analyze, "analyze", fake_external)
    assert lint("wait(1)", external=False) == lint("wait(1)", external=None)
    assert not called
    assert "external-fixture" in {f.rule_id for f in lint("wait(1)", external=True)}
    assert called == ["wait(1)"]
    monkeypatch.setattr(luau_analyze, "enabled", lambda: True)
    assert "external-fixture" in {f.rule_id for f in lint("wait(1)", external=None)}
    assert called == ["wait(1)", "wait(1)"]


def test_safety_script_class_and_server_security_modes_are_separate():
    chain = 'workspace:WaitForChild("First"):WaitForChild("Second")'
    default = lint(chain, external=False)
    assert not any(f.rule_id == "server-waitforchild-chain" for f in default)
    assert not any(f.rule_id == "server-waitforchild-chain" for f in lint(
        chain, safety_checks=True, script_class="LocalScript", external=False))
    with_safety = lint(chain, safety_checks=True, script_class="Script", external=False)
    assert any(f.rule_id == "server-waitforchild-chain" and f.line == 1
               and f.suggested_fix for f in with_safety)

    remote = "remote.OnServerEvent:Connect(function(player, amount) Coins.Value += amount end)"
    basic = lint(remote, external=False)
    assert not any(f.rule_id.startswith("SEC-") for f in basic)
    secured = lint(remote, external=False, server_security=True, script_class="Script")
    assert any(f.rule_id == "SEC-CLIENT-AMOUNT" and f.suggested_fix for f in secured)


def test_fifty_thousand_char_line_is_processed_with_bounded_token_matches(monkeypatch):
    actual_word = luau_lint._WORD
    calls = []
    def counted_match(source, start):
        calls.append(start)
        return actual_word.match(source, start)
    monkeypatch.setattr(luau_lint, "_WORD", SimpleNamespace(match=counted_match))
    assert lint("value = " + "a" * 50_000, external=False) == []
    assert len(calls) <= 8, "One long identifier should tokenize in constant many match calls"


def test_target_mutation_needs_validation_but_a_plain_read_is_not_a_remote_risk():
    unsafe = "remote.OnServerEvent:Connect(function(player, target) target:Destroy() end)"
    safe = "remote.OnServerEvent:Connect(function(player, target) print(target) end)"
    assert any(f.rule_id == "remote-unvalidated" and f.severity == "review"
               for f in lint(unsafe, external=False))
    assert not any(f.rule_id == "remote-unvalidated"
                   for f in lint(safe, external=False))
