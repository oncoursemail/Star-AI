"""Real loader/validator regressions for unreviewed Luau record type candidates."""
from dataclasses import replace
from types import SimpleNamespace
from pathlib import Path

import pytest

from star import luau_record_type_lessons as lessons
from star import skill_packs


def test_twelve_unique_officially_sourced_candidate_cases_and_rejected_wrong_witnesses():
    cases = lessons.load_cases()
    assert [case.id for case in cases] == [f"RT-{n:02d}" for n in range(1, 13)]
    assert len({case.id for case in cases}) == 12
    assert {case.verification for case in cases} == {
        "pure-luau-illustrative", "multi-file-illustrative"
    }
    assert sum(case.verification == "multi-file-illustrative" for case in cases) == 4
    assert len({case.witness for case in cases}) == 12
    for case in cases:
        assert all([case.title, case.context, case.failure, case.correction, case.source_url])
        assert case.source_url in lessons.OFFICIAL_SOURCES
        assert case.incorrect != case.corrected
        assert not lessons.witness_matches(case, case.incorrect), case.id
        assert lessons.witness_matches(case, case.corrected), case.id
        # The witness is intentionally a discriminating substring, not a
        # typechecking oracle: remove the fix and the structural check fails.
        assert not lessons.witness_matches(case, case.corrected.replace(case.witness, "", 1))
        assert not lessons.witness_matches(
            replace(case, witness="not-a-real-type-correction"), case.corrected
        )


@pytest.mark.parametrize("old,new", [
    ("Status: unreviewed candidate reference", "Status: promoted"),
    ("### RT-02:", "### RT-01:"),
    ("**Source:** https://luau.org/syntax/", "**Source:** https://other.invalid/types"),
    ("**Verification:** pure-luau-illustrative", "**Verification:** studio-typechecked"),
    ("**Correction:** Declare a file-local type", "**NotCorrection:** Declare a file-local type"),
    ("type PlatformMotion = {active: boolean, speed: number}",
     "type OtherMotion = {active: boolean, speed: number}"),
    ("**Context:** Moving-platform movement state", "**NoContext:** Moving-platform movement state"),
    ("### RT-12:", "### RT-13:"),
])
def test_loader_rejects_malformed_duplicates_sources_and_claims(tmp_path: Path, old: str, new: str):
    content = lessons.LESSONS_FILE.read_text(encoding="utf-8")
    assert old in content
    target = tmp_path / "bad-record-types.md"
    target.write_text(content.replace(old, new, 1), encoding="utf-8")
    if old == "### RT-12:":
        # The loader accepts valid unique subsets, but the published 12-case
        # collection is pinned by test_twelve_unique_officially_sourced...
        assert lessons.load_cases(target)[-1].id == "RT-13"
    else:
        with pytest.raises(ValueError):
            lessons.load_cases(target)


def test_loader_rejects_missing_pairs_empty_sections_and_oversize(tmp_path: Path):
    original = lessons.LESSONS_FILE.read_text(encoding="utf-8")
    for malformed in (
        original.replace("\x60\x60\x60luau", "\x60\x60\x60text", 1),
        original.replace("Status: unreviewed candidate reference", "", 1),
        original + " " * lessons.MAX_BYTES,
    ):
        target = tmp_path / "bad.md"
        target.write_text(malformed, encoding="utf-8")
        with pytest.raises(ValueError):
            lessons.load_cases(target)


def test_read_only_candidates_are_not_selected_as_skill_packs():
    assert "luau-record-type-lessons" not in skill_packs.DEFAULT_ENABLED
    assert skill_packs.select("What color is the sky?", enabled=set()) == []
    assert lessons.load_cases()  # No lesson store or model execution.

def test_quality_smoke_checks_all_eight_real_pure_candidate_pairs(monkeypatch):
    from scripts import luau_quality_smoke as smoke

    pure = [case for case in lessons.load_cases()
            if case.verification == "pure-luau-illustrative"]
    broken = {case.incorrect for case in pure}
    seen = []

    def fake_analyze(source):
        seen.append(source)
        return ([SimpleNamespace(rule_id="luau-analyze-typeerror")]
                if source in broken else [])

    monkeypatch.setattr(smoke, "analyze", fake_analyze)
    assert smoke.verify_pure_record_candidates() == 8
    assert len(seen) == 16
    assert set(seen) == broken | {case.corrected for case in pure}


def test_quality_smoke_refuses_silent_analyzer_and_bad_repairs(monkeypatch):
    from scripts import luau_quality_smoke as smoke

    monkeypatch.setattr(smoke, "analyze", lambda _source: [])
    with pytest.raises(AssertionError, match="did not detect broken typing"):
        smoke.verify_pure_record_candidates()
    monkeypatch.setattr(
        smoke, "analyze", lambda _source: [SimpleNamespace(rule_id="luau-analyze-typeerror")])
    with pytest.raises(AssertionError, match="rejected corrected Luau"):
        smoke.verify_pure_record_candidates()
