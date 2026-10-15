"""The learning bundle format (star/learned_week.py): well-formed passes, malformed is refused with a clear error,
and an invalid bundle is rejected before any write."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from star import learned_week as lw
from star.lessons import LessonRefused

EVIDENCE = ("paired gate PROMOTE: 9 wins / 2 losses over 24 tasks x k=2, sign test p=0.0327")
EXAMPLE = {
    "id": "night-school-P-07", "group_id": "P-07", "task_category": "luau-modules",
    "instruction": "Write a Luau module that clamps stamina.",
    "response": "```luau\nreturn math.clamp(1, 0, 100)\n```", "source": "night-school-verified",
    "reviewed": False, "rights_confirmed": False,
    "evidence": ["night-school automated checks: luau_block"], "lessons_in_context": ["L3"],
}


def sample() -> dict:
    return {
        "format": lw.FORMAT, "created": datetime.now(timezone.utc).isoformat(), "project": "MyGame",
        "source": "night-school", "scoreboard": "ok",
        "lessons": [{"id": "L3", "kind": "rule", "text": "Clamp a stamina value with math.clamp before saving it.",
                     "evidence": EVIDENCE, "gate": lw.gate_of(EVIDENCE)}],
        "examples": [copy.deepcopy(EXAMPLE)],
    }


def kind() -> str:
    return sorted(lw.LESSON_KINDS)[0]


def good() -> dict:
    data = sample()
    data["lessons"][0]["kind"] = kind()
    return data


def test_well_formed_bundle_passes():
    data = good()
    assert lw.bundle_error(data) is None
    assert lw.parse_bundle(data)["project"] == "MyGame"


def mutate_missing_evidence(d):
    del d["lessons"][0]["evidence"]


def mutate_empty_evidence(d):
    d["lessons"][0]["evidence"] = ""          # gate no longer matches the (now absent) verdict


def mutate_bad_expiry(d):
    d["created"] = "not-a-date"


def mutate_no_zone(d):
    d["created"] = "2026-10-14T07:00:00"


def mutate_unknown_kind(d):
    d["lessons"][0]["kind"] = "superpower"


def mutate_oversized_text(d):
    d["lessons"][0]["text"] = "x " * 5000


def mutate_oversized_evidence(d):
    d["lessons"][0]["evidence"] = EVIDENCE + " " + "y" * 1300


def mutate_extra_field(d):
    d["lessons"][0]["expires"] = "never"


def mutate_example_missing_evidence(d):
    d["examples"][0]["evidence"] = []


def mutate_wrong_format(d):
    d["format"] = "star-learning-bundle-v0"


def mutate_repeated_id(d):
    d["lessons"].append(copy.deepcopy(d["lessons"][0]))


@pytest.mark.parametrize("mutate", [
    mutate_missing_evidence, mutate_empty_evidence, mutate_bad_expiry, mutate_no_zone, mutate_unknown_kind,
    mutate_oversized_text, mutate_oversized_evidence, mutate_extra_field, mutate_example_missing_evidence,
    mutate_wrong_format, mutate_repeated_id])
def test_malformed_bundles_are_refused_with_a_message(mutate):
    data = good()
    mutate(data)
    message = lw.bundle_error(data)
    assert message and len(message) > 5
    with pytest.raises((ValueError, LessonRefused)):
        lw.parse_bundle(data)


@pytest.mark.parametrize("junk", [None, [], "bundle", 5])
def test_non_object_is_refused(junk):
    assert lw.bundle_error(junk)


def test_invalid_bundle_file_writes_nothing(tmp_path):
    data = good()
    data["lessons"].append({**data["lessons"][0], "id": "L4", "kind": "superpower"})
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    home = tmp_path / "home"
    with pytest.raises(ValueError):
        lw.import_bundled(home, "1.0.0", bundle=path)
    registry = lw.Registry(home)
    try:
        assert registry.db.execute("SELECT COUNT(*) FROM learned_items").fetchone()[0] == 0
        assert registry.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
    finally:
        registry.close()
    assert not (home / "worked_examples.sqlite3").exists()
    with pytest.raises(ValueError):
        lw.read_bundle(path)


def test_apply_rejects_invalid_bundle_before_writing(tmp_path):
    data = good()
    data["examples"][0]["evidence"] = []
    registry = lw.Registry(tmp_path / "home")
    try:
        with pytest.raises(ValueError):
            registry.apply(data)
        assert registry.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
    finally:
        registry.close()
    assert not (tmp_path / "home" / "worked_examples.sqlite3").exists()


def test_import_version_is_not_recorded_for_a_bad_bundle(tmp_path):
    path = tmp_path / "bundle.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        lw.import_bundled(tmp_path / "home", "1.0.0", bundle=path)
    registry = lw.Registry(tmp_path / "home")
    try:
        registry.db.execute("CREATE TABLE IF NOT EXISTS learning_bundle_imports (version TEXT PRIMARY KEY, "
                            "imported_at TEXT NOT NULL)")
        assert registry.db.execute("SELECT COUNT(*) FROM learning_bundle_imports").fetchone()[0] == 0
    finally:
        registry.close()
