"""Metamorphic real-entrypoint checks for opt-in Roblox Luau security and lifetime rules.

Inputs are not executed: the witnesses measure static scanner stability and scope,
not Roblox Studio safety or semantic equivalence for arbitrary Lua syntax.
"""
from __future__ import annotations

import pytest

from star.luau_lint import lint
from star.luau_safety import inspect_safety
from star.luau_server_security import lint_server_trust
from tests.test_luau_safety import CASES as LIFETIME_CASES
from tests.test_luau_server_security import CASES as TRUST_CASES


# Fixed, deterministic transforms that change neither the executable guard nor sink.
TRANSFORMS = (
    "crlf",
    "indent",
    "line-comment",
    "long-comment",
    "long-string",
    "unrelated-local",
    "spacing",
)


def _transform(source: str, transformation: str) -> tuple[str, int]:
    if transformation == "crlf":
        return source.replace("\n", "\r\n"), 0
    if transformation == "indent":
        return "\n".join("    " + line for line in source.split("\n")), 0
    if transformation == "line-comment":
        return '-- if typeof(amount) ~= "number" then return end\n' + source, 1
    if transformation == "long-comment":
        return "--[=[remote.OnServerEvent:Connect(function(p, amount) coins.Value += amount end)]=]\n" + source, 1
    if transformation == "long-string":
        return 'local unusedMessage = [==[if amount < 1 or amount > 50 then return end]==]\n' + source, 1
    if transformation == "unrelated-local":
        return "local unrelatedCounter = 123\n" + source, 1
    if transformation == "spacing":
        return source.replace("OnServerEvent:Connect", "OnServerEvent  :  Connect").replace(
            "OnServerInvoke =", "OnServerInvoke     ="), 0
    raise AssertionError(f"Unknown transformation: {transformation}")


def _evidence(findings, line_offset=0, *, only_security=False):
    return sorted(
        (f.rule_id, f.line - line_offset, f.message, f.severity)
        for f in findings if not only_security or f.rule_id.startswith("SEC-")
    )


@pytest.mark.parametrize(
    ("rule", "unsafe", "safe", "transformation"),
    [
        pytest.param(rule, unsafe, safe, transformation, id=f"trust-{index}-{transformation}")
        for index, (rule, unsafe, safe) in enumerate(TRUST_CASES, 1)
        for transformation in TRANSFORMS
    ],
)
def test_metamorphic_server_trust_verdicts_through_scanner_and_lint(
    rule, unsafe, safe, transformation,
):
    for source, expected in ((unsafe, True), (safe, False)):
        original = lint_server_trust(source)
        assert (rule in {f.rule_id for f in original}) is expected
        changed, offset = _transform(source, transformation)
        assert _evidence(lint_server_trust(changed), offset) == _evidence(original)
        assert _evidence(lint(changed, external=False, server_security=True), offset,
                         only_security=True) == _evidence(
                             lint(source, external=False, server_security=True),
                             only_security=True,
                         )


@pytest.mark.parametrize(
    ("rule", "source", "expected", "transformation"),
    [
        pytest.param(rule, source, expected, transformation, id=f"safety-{rule}-{kind}-{transformation}")
        for rule, samples in LIFETIME_CASES.items()
        for kind, expected in (("bad", True), ("good", False))
        for source in samples[kind][:1]
        for transformation in TRANSFORMS
    ],
)
def test_metamorphic_lifetime_inspector_and_lint_agree(
    rule, source, expected, transformation,
):
    script_class = "Script" if rule == "server-waitforchild-chain" else None
    original = inspect_safety(source, script_class=script_class)
    assert (rule in {f.rule_id for f in original}) is expected
    changed, offset = _transform(source, transformation)
    assert _evidence(inspect_safety(changed, script_class=script_class), offset) == _evidence(original)
    def selected(source):
        return [f for f in lint(source, external=False, safety_checks=True,
                                script_class=script_class) if f.rule_id == rule]
    assert _evidence(selected(changed), offset) == _evidence(selected(source))


UNSAFE_MUTATIONS = [
    (
        "guard-in-uncalled-function", "SEC-CLIENT-AMOUNT", "coins.Value",
        """remote.OnServerEvent:Connect(function(player, amount)
    local function validate()
        if typeof(amount) ~= "number" then return end
        if amount < 1 or amount > 50 then return end
    end
    coins.Value += amount
end)""",
    ),
    (
        "guard-in-conditional-scope", "SEC-CLIENT-AMOUNT", "coins.Value",
        """remote.OnServerEvent:Connect(function(player, amount)
    if false then
        if typeof(amount) ~= "number" then return end
        if amount < 1 or amount > 50 then return end
    end
    coins.Value += amount
end)""",
    ),
    (
        "return-only-in-nested-branch", "SEC-CLIENT-AMOUNT", "coins.Value",
        """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount < 1 or amount > 50 then
        if false then return end
    end
    coins.Value += amount
end)""",
    ),
    (
        "wrong-guard-operand", "SEC-CLIENT-AMOUNT", "coins.Value",
        """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if other < 1 or other > 50 then return end
    coins.Value += amount
end)""",
    ),
    (
        "range-guard-rejects-good-values", "SEC-CLIENT-AMOUNT", "coins.Value",
        """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount >= 1 and amount <= 50 then return end
    coins.Value += amount
end)""",
    ),
    (
        "comparisons-without-rejection", "SEC-CLIENT-AMOUNT", "coins.Value",
        """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount < 1 then print("low") end
    if amount > 50 then print("high") end
    coins.Value += amount
end)""",
    ),
    (
        "ownership-guard-unrelated-not", "SEC-INSTANCE-OWNERSHIP", "target:Destroy",
        """remote.OnServerEvent:Connect(function(player, target)
    if not disabled and target:IsDescendantOf(player.Character) then return end
    target:Destroy()
end)""",
    ),
    (
        "ownership-guard-conditional-rejection", "SEC-INSTANCE-OWNERSHIP", "target:Destroy",
        """remote.OnServerEvent:Connect(function(player, target)
    if not target:IsDescendantOf(player.Character) and disabled then return end
    target:Destroy()
end)""",
    ),
    (
        "ownership-checks-wrong-object", "SEC-INSTANCE-OWNERSHIP", "target:Destroy",
        """remote.OnServerEvent:Connect(function(player, target, other)
    if not other:IsDescendantOf(player.Character) then return end
    target:Destroy()
end)""",
    ),
    (
        "allowlist-in-uncalled-helper", "SEC-REMOTE-ALLOWLIST", "Inventory[itemId]",
        """remote.OnServerEvent:Connect(function(player, itemId)
    local function check()
        if not CATALOG[itemId] then return end
    end
    Inventory[itemId] = true
end)""",
    ),
    (
        "client-key-guard-in-uncalled-helper", "SEC-DATASTORE-CLIENT-KEY", "store:GetAsync",
        """remote.OnServerEvent:Connect(function(player, key)
    local function check()
        if not VALID_KEYS[key] then return end
    end
    store:GetAsync(key)
end)""",
    ),
    (
        "guard-in-another-remote-handler", "SEC-CLIENT-AMOUNT", "coins.Value",
        """first.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount < 1 or amount > 50 then return end
end)
second.OnServerEvent:Connect(function(player, amount)
    coins.Value += amount
end)""",
    ),
]


@pytest.mark.parametrize(("name", "rule", "sink", "source"), UNSAFE_MUTATIONS,
                         ids=[item[0] for item in UNSAFE_MUTATIONS])
def test_unsafe_mutations_have_expected_security_rule_and_original_source_line(name, rule, sink, source):
    sink_line = next(index for index, line in enumerate(source.splitlines(), 1) if sink in line)
    for findings in (lint_server_trust(source), lint(source, external=False, server_security=True)):
        assert (rule, sink_line) in {(f.rule_id, f.line) for f in findings}, name
        assert findings == sorted(set(findings), key=lambda f: (
            f.line, f.rule_id, f.message,
        ))


@pytest.mark.parametrize(("rule", "source"), [
    ("SEC-CLIENT-AMOUNT", """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount < 1 or amount > 50 then return end
    if enabled then coins.Value += amount end
end)"""),
    ("SEC-CLIENT-AMOUNT", """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) == "number" and amount >= 1 and amount <= 50 then
        coins.Value += amount
    end
end)"""),
    ("SEC-INSTANCE-OWNERSHIP", """remote.OnServerEvent:Connect(function(player, target)
    if target:IsDescendantOf(player.Character) then target:Destroy() end
end)"""),
    ("SEC-REMOTE-ALLOWLIST", """remote.OnServerEvent:Connect(function(player, itemId)
    if CATALOG[itemId] then Inventory[itemId] = true end
end)"""),
])
def test_real_same_handler_guards_still_protect_sinks(rule, source):
    assert rule not in {finding.rule_id for finding in lint_server_trust(source)}
    assert rule not in {finding.rule_id for finding in lint(
        source, external=False, server_security=True,
    )}


def test_security_extensions_remain_default_off_and_do_not_run_external_analyzer():
    code = UNSAFE_MUTATIONS[0][-1]
    assert all(not finding.rule_id.startswith("SEC-") for finding in lint(code, external=False))
    assert "SEC-CLIENT-AMOUNT" in {
        finding.rule_id for finding in lint(code, external=False, server_security=True)
    }
    source = "while true do expensive() end"
    assert not any(f.rule_id == "loop-without-yield" for f in lint(source, external=False))
    assert "loop-without-yield" in {f.rule_id for f in lint(
        source, external=False, safety_checks=True,
    )}
