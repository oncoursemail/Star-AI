"""Regression tests for offline, advisory Roblox feature checklists."""
import pytest

from star.lesson_checklists import Requirement, check_answer, required_features


def test_three_coordinated_features_remain_separate_and_ordered():
    assert [f.key for f in required_features(
        "Can you make a Roblox game with a shop and a timer and a leaderboard?"
    )] == ["shop", "timer", "leaderboard"]


def test_deduplication_order_and_exclusions():
    assert [f.key for f in required_features(
        "Make a leaderboard, checkpoint and leaderboard, but no shop or timer"
    )] == ["leaderboard", "checkpoint"]


@pytest.mark.parametrize(("prompt", "expected"), [
    ("open a door with a ProximityPrompt", "door"),
    ("grab coins when players touch them", "coin"),
    ("add a day/night cycle", "day-night"),
    ("can i have a sprint pad", "speed"),
    ("team spawns for both teams", "teams"),
    ("a moving platform pls", "platform"),
    ("play sound on touch", "sound"),
    ("save player checkpoints", "checkpoint"),
])
def test_recognizes_each_supported_beginner_request(prompt, expected):
    assert [item.key for item in required_features(prompt)] == [expected]


def test_unknown_request_does_not_claim_a_verified_feature():
    assert required_features("make a complicated dragon battle") == ()


def test_prose_is_not_feature_implementation():
    specs = required_features("shop and timer and leaderboard")
    results = check_answer("I built a shop with a timer and leaderboard using OnServerEvent.", specs)
    assert all(not result.present for result in results)


def test_comments_cannot_fake_evidence():
    specs = required_features("shop, timer, leaderboard")
    answer = """```luau
-- shop OnServerEvent
-- timer task.wait(1)
-- leaderboard Instance.new("IntValue")
local empty = {}
return empty
```"""
    assert all(not result.present for result in check_answer(answer, specs))


def test_keyword_alone_or_api_alone_is_not_enough():
    rule = required_features("shop")
    just_keyword = '```luau\nlocal shop = {}\nreturn shop\n```'
    just_api = '```luau\nlocal remote = game.ReplicatedStorage.Buy\nremote.OnServerEvent:Connect(function() end)\n```'
    assert check_answer(just_keyword, rule)[0].keyword_found
    assert not check_answer(just_keyword, rule)[0].present
    assert check_answer(just_api, rule)[0].api_found
    assert not check_answer(just_api, rule)[0].present


def test_realistic_three_feature_script_has_all_hints():
    answer = """```luau
local shopRemote = game.ReplicatedStorage.ShopEvent
shopRemote.OnServerEvent:Connect(function(player) end)
local timer = 30
while timer > 0 do
    task.wait(1)
    timer -= 1
end
local leaderstats = Instance.new("Folder")
local wins = Instance.new("IntValue")
wins.Parent = leaderstats
```"""
    results = check_answer(answer, required_features("shop and timer and leaderboard"))
    assert [result.present for result in results] == [True, True, True]


def test_one_missing_feature_yields_negative_not_blanket_pass():
    answer = """```luau
local shopRemote = game.ReplicatedStorage.ShopRemote
shopRemote.OnServerEvent:Connect(function(player) end)
local timer = 10
task.wait(1)
```"""
    results = check_answer(answer, required_features("shop and timer and leaderboard"))
    assert [result.present for result in results] == [True, True, False]


def test_coincidental_comment_with_api_does_not_satisfy_missing_feature():
    answer = """```luau
-- leaderboard
local amount = Instance.new("IntValue")
```"""
    result = check_answer(answer, required_features("leaderboard"))[0]
    assert result.api_found and not result.keyword_found and not result.present


def test_unknown_unsupported_key_is_not_a_silent_pass():
    with pytest.raises(ValueError, match="unsupported feature"):
        check_answer("local x = 1", (Requirement("telekinesis", "telekinesis"),))


def test_no_runtime_side_effects_and_empty_input():
    assert check_answer("", required_features("")) == ()
    assert not check_answer("", required_features("timer"))[0].present


@pytest.mark.parametrize("bad", [None, 1, []])
def test_invalid_request_or_answer_types_fail(bad):
    with pytest.raises(TypeError):
        required_features(bad)
    with pytest.raises(TypeError):
        check_answer(bad, ())


def test_raw_luau_snippets_supported_without_markdown():
    sample = 'local coin = Instance.new("IntValue")\ncoin.Name = "Coins"\ncoin.Value = 0'
    assert check_answer(sample, required_features("coins"))[0].present


def test_markdown_lessons_are_complete_and_source_linked():
    from pathlib import Path
    import re

    catalog = Path(__file__).resolve().parents[1] / "docs/lessons/logic-and-missing-features.md"
    text = catalog.read_text(encoding="utf-8")
    entries = re.split(r"(?m)^## \d+\. ", text)[1:]
    assert len(entries) == 12
    for entry in entries:
        assert "**Mistake:**" in entry
        assert "**Bad (illustrative):**" in entry
        assert "**Corrected pattern:**" in entry
        assert "**Rule:**" in entry
        assert "[Recorded failure]" in entry
        assert "[official API/scripting reference](https://create.roblox.com/" in entry
