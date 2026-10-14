"""Exercise the real read-only candidate loader; no Studio execution is claimed."""
from pathlib import Path

import pytest

from star import character_lifecycle_lessons as lessons
from star import skill_packs


def test_twelve_distinct_officially_cited_character_cases():
    found = lessons.load_cases()
    assert len(found) == 12
    assert [case.id for case in found] == [f"CL-{i:02d}" for i in range(1, 13)]
    assert len({case.source_url for case in found}) == 12
    for case in found:
        assert case.title and case.failure and case.correction
        assert case.incorrect != case.corrected
        assert case.source_url.startswith("https://create.roblox.com/docs/reference/engine/classes/")
        assert case.verification == "illustrative-engine-only"


@pytest.mark.parametrize("index,expected", [
    (1, "GetPlayers"), (2, "if player.Character"), (3, "WaitForChild"),
    (4, "player.Character ~= character"), (5, "CharacterAdded"), (6, "CharacterRemoving"),
    (7, "PlayerRemoving"), (8, "TakeDamage"), (9, "HumanoidRigType.R15"),
    (10, "animator:LoadAnimation"), (11, "LoadCharacterAsync"), (12, "markerConnection:Disconnect"),
])
def test_corrected_illustration_contains_a_required_fix_missing_from_wrong_case(index, expected):
    case = lessons.load_cases()[index - 1]
    assert expected in case.corrected
    assert expected not in case.incorrect


@pytest.mark.parametrize("replacement", [
    ("Status: unreviewed candidate reference", "Status: promoted lesson"),
    ("https://create.roblox.com", "https://untrusted.invalid"),
    ("**Correction:**", "**Fix:**"),
    ("### CL-02:", "### CL-01:"),
    ("**Verification:** illustrative-engine-only", "**Verification:** ran-in-Studio"),
])
def test_reject_malformed_untrusted_and_prematurely_promoted_lessons(tmp_path, replacement):
    original = lessons.LESSONS_FILE.read_text(encoding="utf-8")
    file = tmp_path / "broken.md"
    file.write_text(original.replace(*replacement, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        lessons.load_cases(file)


def test_only_candidates_and_no_default_pack_changes():
    assert "roblox-animation-tools" not in skill_packs.DEFAULT_ENABLED
    assert "roblox-character-lifecycle" not in skill_packs.DEFAULT_ENABLED
    assert skill_packs.select("How many moons does Mars have?", enabled=set()) == []
    assert lessons.load_cases()
