"""Structural validation of the separate beginner-development practice pool.

This file is training material, not a golden/holdout suite or evidence of a
model-quality improvement. No Studio or sandbox result is claimed by static hits.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from star.eval_checks import pattern_checks
from star.eval_runner import load_suite
from star.evals import load_catalog


ROOT = Path(__file__).resolve().parents[1]
PRACTICE = ROOT / "evals/roblox/practice-tasks-beginner-v2.json"
SOURCES = (
    ROOT / "evals/roblox/golden-tasks-creation-v1.json",
    ROOT / "evals/roblox/golden-tasks-v1.json",
    ROOT / "evals/roblox/golden-tasks-v2.json",
    ROOT / "evals/roblox/holdout-v1.json",
)
TOPICS = {
    "hazards", "checkpoints", "doors", "coins", "shops",
    "day-night", "speed", "teams", "platforms", "sound",
}
# Independently reviewed names from Roblox Creator Hub classes, events and
# the Luau task library. Avoid accepting arbitrary invented dotted names.
KNOWN_SYMBOLS = {
    "BasePart.Touched", "BasePart.Position", "BasePart.Transparency",
    "BasePart.CanTouch", "BasePart.CFrame", "Humanoid.Health",
    "Humanoid.TakeDamage", "Humanoid.WalkSpeed", "Players.GetPlayers",
    "Players.GetPlayerFromCharacter", "Players.PlayerAdded",
    "Player.RespawnLocation", "Player.CharacterAdded",
    "Player.SetAttribute", "Player.Team", "Instance.GetAttribute",
    "Instance.Destroy", "PVInstance.PivotTo", "IntValue.Value", "Folder",
    "IntValue", "ProximityPrompt.Triggered", "TweenService.Create",
    "Tween.Play", "Tween.Completed", "TweenInfo.new", "task.delay",
    "RemoteEvent.OnServerEvent", "RemoteEvent.OnClientEvent",
    "RemoteEvent.FireServer", "GuiButton.Activated", "TextLabel.Text",
    "RunService.Heartbeat", "Lighting.ClockTime",
    "Lighting.OutdoorAmbient", "Color3.Lerp", "BindableEvent.Event",
    "SpawnLocation.Neutral", "SpawnLocation.TeamColor", "Teams",
    "Sound.Play", "Sound.IsPlaying", "Sound.Ended", "Enum.PlaybackState",
}


def _tasks(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text):
    return re.findall(r"[a-z0-9]+", text.casefold())


def _near_copy(first, second):
    a, b = _tokens(first), _tokens(second)
    if not a or not b:
        return False
    if len(set(a) & set(b)) / len(set(a) | set(b)) >= 0.82:
        return True
    if len(a) < 12 or len(b) < 12:
        return False
    windows = {tuple(a[i:i + 12]) for i in range(len(a) - 11)}
    return any(tuple(b[i:i + 12]) in windows for i in range(len(b) - 11))


def test_pool_loads_through_existing_catalog_and_runner():
    cases = load_catalog(PRACTICE)
    suite = load_suite(PRACTICE)
    assert len(cases) == len(suite.tasks) == len(suite.runnable()) == 30
    assert all(case.run_mode == "automated" for case in cases)


def test_unique_ids_topics_goals_and_no_protected_overlap():
    tasks = _tasks(PRACTICE)
    ids = [t["id"] for t in tasks]
    assert ids == [f"BEG-{i:02d}" for i in range(1, 31)]
    assert len(ids) == len(set(ids))
    assert len({t["goal"].casefold() for t in tasks}) == 30
    assert Counter(t["topic"] for t in tasks) == {topic: 3 for topic in TOPICS}
    protected = [task for path in SOURCES for task in _tasks(path)]
    protected_ids = {t["id"] for t in protected}
    assert not protected_ids.intersection(ids)
    for task in tasks:
        assert not any(_near_copy(task["prompt"], other["prompt"]) for other in protected)
    for i, task in enumerate(tasks):
        assert not any(_near_copy(task["prompt"], other["prompt"]) for other in tasks[:i])


def test_every_task_is_checkable_and_uses_known_api_names():
    for task in _tasks(PRACTICE):
        assert task["run_mode"] == "automated"
        assert task["fixture_status"] == "not_needed" and task["fixtures"] == []
        assert task["split"] == "development"
        assert len(task["prompt"].strip()) >= 80
        assert task["teaches"].strip() and task["edge_case"].strip()
        assert len(task["expected_behavior"]) >= 2
        assert task["scoring_scope"].startswith("static regex")
        assert task["source_urls"] and all(
            url.startswith("https://create.roblox.com/docs/") for url in task["source_urls"]
        )
        assert task["engine_symbols"] and set(task["engine_symbols"]) <= KNOWN_SYMBOLS
        checks = task["auto"]
        assert checks["compile"] is True
        assert len(checks["require"]) >= 2 and len(checks["forbid"]) >= 1
        all_checks = checks["require"] + checks["forbid"]
        assert len({c["id"] for c in all_checks}) == len(all_checks)
        for check in all_checks:
            assert check["scope"] in {"code", "code_nostr"}
            assert check["why"] and check["re"]
            pattern = re.compile(check["re"])
            assert pattern.search("") is None, (task["id"], check["id"])
        # Execute STAR's actual pattern checker, verifying missing required
        # evidence does fail, rather than merely validating JSON structure.
        results = pattern_checks(checks, ["local unrelated = 1"], "")
        assert len(results) == len(all_checks)
        assert all(not check.ok for check in results[:len(checks["require"])])
        assert all(check.ok for check in results[len(checks["require"]):])


SAMPLES = {
    "BEG-01": """local brick = script.Parent
brick.Touched:Connect(function(hit)
    local humanoid = hit.Parent:FindFirstChildOfClass("Humanoid")
    if humanoid then humanoid.Health = 0 end
end)""",
    "BEG-14": """local Prices = {sword = 50}
BuyItem.OnServerEvent:Connect(function(player, itemId)
    local price = Prices[itemId]
    local Coins = player.leaderstats.Coins
    if price and Coins.Value >= price then
        Coins.Value -= price
    end
end)""",
    "BEG-28": """local sound = script.Parent.Sound
local busy = false
script.Parent.Touched:Connect(function(hit)
    if busy then return end
    sound:Play()
end)""",
}


def test_existing_checker_accepts_realistic_positive_api_hints():
    tasks = {task["id"]: task for task in _tasks(PRACTICE)}
    for task_id, sample in SAMPLES.items():
        checks = pattern_checks(tasks[task_id]["auto"], [sample], "")
        assert checks and all(c.ok for c in checks), (task_id, [c.id for c in checks if not c.ok])


def test_existing_checker_rejects_a_task_specific_unsafe_variant():
    task = next(task for task in _tasks(PRACTICE) if task["id"] == "BEG-14")
    bad = SAMPLES["BEG-14"].replace("Coins.Value -= price", "Coins.Value -= clientPrice")
    checks = pattern_checks(task["auto"], [bad], "")
    assert any(c.id == "forbid:no_clientprice" and not c.ok for c in checks)
