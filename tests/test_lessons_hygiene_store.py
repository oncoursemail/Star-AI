"""Integration with the actual Lesson type, SQLite schema and human review gate."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from star.lessons import Lesson, LessonStore
from star.lessons_hygiene import OverrideObservation, _default_home, build_report, main, read_database

FIXTURE = Path(__file__).parent / "fixtures" / "lessons_hygiene.json"


def test_actual_forty_lesson_dataclasses_and_exports_produce_the_same_report():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    lessons = tuple(Lesson(**row) for row in fixture["lessons"])
    before = tuple(asdict(lesson) for lesson in lessons)
    options = dict(as_of=datetime.fromisoformat(fixture["as_of"]),
                   overrides=[OverrideObservation(**item) for item in fixture["overrides"]])
    result = build_report(lessons, **options)
    assert result == build_report([lesson.public() for lesson in lessons], **options)
    assert result == build_report(fixture["lessons"], **options)
    assert len(lessons) == 40 and tuple(asdict(lesson) for lesson in lessons) == before


def test_hygiene_cli_preserves_the_real_store_and_explicit_review_gate(tmp_path, capsys):
    store = LessonStore(tmp_path)
    try:
        text = "Use camelCase for local variables."
        accepted = store.capture_owner(project="DemoA", kind="preference", text=text, message=text,
                                       source="chat:fixture#1", evidence="Fixture owner statement")
        detailed = "Always use camelCase for local variables in inventory modules."
        candidate = store.capture_inferred(project="DemoA", kind="preference", text=detailed,
                                          source_type="summary", source="chat:fixture#2",
                                          evidence="Fixture candidate explanation")
        assert accepted.status == "accepted" and candidate.status == "candidate"
        recalled = store.recall("DemoA", "inventory variable names")
        store.mark_used("DemoA", recalled)
        before = tuple(store.db.iterdump())
        changes = store.db.total_changes
        lessons = store.list("DemoA")
        clock = datetime.now(timezone.utc)
        result = build_report(lessons, as_of=clock)
        proposal = next(item for item in result.proposals if item.kind == "merge")
        assert proposal.keep_id == candidate.lesson_id and proposal.suggested_text == detailed
        assert {item.source for item in proposal.evidence} == {"chat:fixture#1", "chat:fixture#2"}
        assert main(["report", "--home", str(tmp_path), "--as-of", clock.isoformat()]) == 0
        assert json.loads(capsys.readouterr().out) == json.loads(json.dumps(result.public()))
        assert build_report(read_database(tmp_path / "knowledge" / "knowledge.sqlite3"), as_of=clock) == result
        assert build_report(store.export("DemoA")["lessons"], as_of=clock) == result
        assert tuple(store.db.iterdump()) == before and store.db.total_changes == changes
        assert store.get("DemoA", candidate.lesson_id).status == "candidate"
        assert [lesson.id for lesson in store.recall("DemoA", "inventory variable names")] == [accepted.lesson_id]
        with pytest.raises(PermissionError):
            store.approve("DemoA", candidate.lesson_id)
        with pytest.raises(PermissionError):
            store.edit("DemoA", accepted.lesson_id, text=detailed)
        with pytest.raises(PermissionError):
            store.reject("DemoA", accepted.lesson_id)
        assert tuple(store.db.iterdump()) == before
        # Only a separate, explicit review can change which wording is trusted.
        reviewed = store.approve("DemoA", candidate.lesson_id, human_approved=True)
        assert reviewed.status == "accepted"
        assert store.get("DemoA", accepted.lesson_id).status == "superseded"
    finally:
        store.close()


@pytest.mark.parametrize("configured", [False, True])
def test_default_data_folder_matches_the_actual_desktop_function(tmp_path, monkeypatch, configured):
    from star.desktop_core import app_data

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for variable in ("APPDATA", "XDG_DATA_HOME"):
        if configured:
            monkeypatch.setenv(variable, str(tmp_path / "configured"))
        else:
            monkeypatch.delenv(variable, raising=False)
    assert _default_home() == app_data()
    assert not list(tmp_path.iterdir())
