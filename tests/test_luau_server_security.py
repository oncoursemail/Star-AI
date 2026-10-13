"""Regression tests for opt-in Luau server/client trust diagnostics.

These tests call both the standalone scanner and the registered lint entrypoint.
"""
import pytest

from star.luau_lint import lint
from star.luau_server_security import lint_server_trust


CASES = [
    (
        "SEC-CLIENT-AMOUNT",
        """remote.OnServerEvent:Connect(function(player, amount)
    coins.Value += amount
end)""",
        """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount < 1 or amount > 50 then return end
    coins.Value += amount
end)""",
    ),
    (
        "SEC-CLIENT-AMOUNT",
        """remote.OnServerInvoke = function(player, delta)
    if typeof(delta) ~= "number" then return end
    wallet.Value = wallet.Value + delta
end""",
        """remote.OnServerInvoke = function(player, delta)
    if typeof(delta) == "number" and delta >= 1 and delta <= 20 then
        wallet.Value = wallet.Value + delta
    end
end""",
    ),
    (
        "SEC-CLIENT-AMOUNT",
        """remote.OnServerEvent:Connect(function(player, amount)
    if amount >= 0 then cash.Value -= amount end
end)""",
        """remote.OnServerEvent:Connect(function(player, amount)
    if type(amount) ~= "number" then return end
    if amount < 1 or amount > 100 then return end
    cash.Value -= amount
end)""",
    ),
    (
        "SEC-CLIENT-PRICE",
        """remote.OnServerInvoke = function(player, price)
    if typeof(price) ~= "number" then return end
    wallet.Value -= price
end""",
        """remote.OnServerInvoke = function(player, itemId)
    local item = CATALOG[itemId]
    if not item then return end
    local price = item.Price
    wallet.Value -= price
end""",
    ),
    (
        "SEC-CLIENT-PRICE",
        """remote.OnServerEvent:Connect(function(player, requestedCost)
    cash.Value = cash.Value - requestedCost
end)""",
        """remote.OnServerEvent:Connect(function(player, itemId)
    if not PRODUCTS[itemId] then return end
    cash.Value -= PRODUCTS[itemId].Price
end)""",
    ),
    (
        "SEC-INSTANCE-OWNERSHIP",
        """remote.OnServerEvent:Connect(function(player, target)
    target:Destroy()
end)""",
        """remote.OnServerEvent:Connect(function(player, target)
    if typeof(target) ~= "Instance" then return end
    if not target:IsDescendantOf(player.Character) then return end
    target:Destroy()
end)""",
    ),
    (
        "SEC-INSTANCE-OWNERSHIP",
        """remote.OnServerInvoke = function(player, part)
    part.Parent = workspace
end""",
        """remote.OnServerInvoke = function(player, part)
    if part.Parent ~= player.Character then return end
    part.Parent = workspace
end""",
    ),
    (
        "SEC-INSTANCE-OWNERSHIP",
        """remote.OnServerEvent:Connect(function(player, object)
    object:SetAttribute("Taken", true)
end)""",
        """remote.OnServerEvent:Connect(function(player, object)
    if object:IsDescendantOf(player.Character) then
        object:SetAttribute("Taken", true)
    end
end)""",
    ),
    (
        "SEC-DATASTORE-CLIENT-KEY",
        """remote.OnServerEvent:Connect(function(player, key)
    store:GetAsync(key)
end)""",
        """remote.OnServerEvent:Connect(function(player, key)
    store:GetAsync("player_" .. tostring(player.UserId))
end)""",
    ),
    (
        "SEC-DATASTORE-CLIENT-KEY",
        """remote.OnServerInvoke = function(player, suffix)
    local key = "player_" .. suffix
    return store:SetAsync(key, 5)
end""",
        """remote.OnServerInvoke = function(player, suffix)
    if not ALLOWED_KEYS[suffix] then return end
    local key = "player_" .. suffix
    return store:SetAsync(key, 5)
end""",
    ),
    (
        "SEC-REMOTE-ALLOWLIST",
        """remote.OnServerEvent:Connect(function(player, itemId)
    Inventory[itemId] = true
end)""",
        """remote.OnServerEvent:Connect(function(player, itemId)
    if not CATALOG[itemId] then return end
    Inventory[itemId] = true
end)""",
    ),
    (
        "SEC-REMOTE-ALLOWLIST",
        """remote.OnServerInvoke = function(player, slot)
    profile.Data[slot] = true
end""",
        """remote.OnServerInvoke = function(player, slot)
    if not VALID_SLOTS[slot] then return end
    profile.Data[slot] = true
end""",
    ),
    (
        "SEC-CLIENT-AMOUNT",
        """remote.OnServerEvent:Connect(function(player, amount)
    store:IncrementAsync("constant_key", amount)
end)""",
        """remote.OnServerEvent:Connect(function(player, amount)
    if typeof(amount) ~= "number" then return end
    if amount < 1 or amount > 3 then return end
    store:IncrementAsync("constant_key", amount)
end)""",
    ),
]


@pytest.mark.parametrize(("rule", "unsafe", "safe"), CASES, ids=[
    "unbounded-coins", "invoke-delta-type-only", "positive-bound-only",
    "client-price-invoke", "client-cost-event", "destroy-instance",
    "parent-mutation", "attribute-mutation", "raw-datastore-key",
    "composed-datastore-key", "inventory-key", "profile-slot",
    "datastore-increment",
])
def test_unsafe_detected_and_guarded_pattern_accepted(rule, unsafe, safe):
    unsafe_findings = lint_server_trust(unsafe)
    assert rule in {finding.rule_id for finding in unsafe_findings}
    assert rule in {finding.rule_id for finding in lint(unsafe, server_security=True)}
    assert rule not in {finding.rule_id for finding in lint_server_trust(safe)}


def test_security_rules_are_off_by_default():
    source = CASES[0][1]
    assert not [finding for finding in lint(source) if finding.rule_id.startswith("SEC-")]
    assert "SEC-CLIENT-AMOUNT" in {
        finding.rule_id for finding in lint(source, server_security=True)}


@pytest.mark.parametrize("source", [
    "",
    "remote.OnServerEvent:Connect(function(player, amount)",
    "-- remote.OnServerEvent:Connect(function(player, amount) coins.Value += amount end)",
    "--[=[ remote.OnServerInvoke = function(player, price) wallet.Value -= price end ]=]",
    "local s = 'remote.OnServerInvoke = function(player, price) wallet.Value -= price end'",
    'local s = [[remote.OnServerEvent:Connect(function(p,x) Inventory[x] = true end)]]',
    "remote.OnServerEvent:Connect(namedHandler)",
    "remote.OnServerInvoke = namedHandler",
    "remote.OnClientEvent:Connect(function(player, amount) coins.Value += amount end)",
    "remote.OnServerEvent:Connect(function(player, text) print(text) end)",
    "remote.OnServerInvoke = function(player, name) return #name end",
    """remote.OnServerEvent:Connect(function(player, key)
       -- key is checked elsewhere; a comment is not a guard
       local row = CATALOG[key]
       if not row then return end
       print(row.Price)
    end)""",
])
def test_no_spurious_security_findings(source):
    assert lint_server_trust(source) == []


def test_type_check_without_range_does_not_hide_amount_warning():
    source = """remote.OnServerEvent:Connect(function(player, amount)
        if typeof(amount) ~= "number" then return end
        if amount > 0 then wallet.Value += amount end
    end)"""
    assert "SEC-CLIENT-AMOUNT" in {f.rule_id for f in lint_server_trust(source)}


def test_instance_type_check_alone_does_not_prove_ownership():
    source = """remote.OnServerEvent:Connect(function(player, target)
        if typeof(target) ~= "Instance" then return end
        target:Destroy()
    end)"""
    assert "SEC-INSTANCE-OWNERSHIP" in {f.rule_id for f in lint_server_trust(source)}


def test_unrelated_character_check_does_not_authorize_an_instance():
    source = """remote.OnServerEvent:Connect(function(player, target)
        if not target:IsDescendantOf(workspace) then return end
        target:Destroy()
    end)"""
    assert "SEC-INSTANCE-OWNERSHIP" in {f.rule_id for f in lint_server_trust(source)}


def test_comments_and_strings_cannot_create_validation_guards():
    source = """remote.OnServerEvent:Connect(function(player, amount)
        -- if typeof(amount) ~= "number" then return end
        local s = "if amount < 1 or amount > 50 then return end"
        coins.Value += amount
    end)"""
    assert "SEC-CLIENT-AMOUNT" in {f.rule_id for f in lint_server_trust(source)}


def test_lines_determinism_and_no_duplicate_findings():
    source = "-- header\n" + CASES[0][1]
    result = lint_server_trust(source)
    assert result == lint_server_trust(source)
    assert result == sorted(set(result), key=lambda f: (f.line, f.rule_id, f.message))
    assert any(f.rule_id == "SEC-CLIENT-AMOUNT" and f.line == 3 for f in result)


def test_non_string_rejected_without_executing_code():
    with pytest.raises(TypeError):
        lint_server_trust(None)
    assert lint_server_trust("loadstring('error()')\nrequire(12345)") == []


def test_separate_handlers_do_not_share_guards():
    source = """first.OnServerEvent:Connect(function(player, amount)
        if typeof(amount) ~= "number" then return end
        if amount < 0 or amount > 20 then return end
        coins.Value += amount
    end)
    second.OnServerEvent:Connect(function(player, amount)
        coins.Value += amount
    end)"""
    assert len([f for f in lint_server_trust(source)
                if f.rule_id == "SEC-CLIENT-AMOUNT"]) == 1
