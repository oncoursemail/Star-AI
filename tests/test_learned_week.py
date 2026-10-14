"""W7: night school's reviewed bundle reaches the app as "What STAR learned this week" (star/learned_week.py).

The bundle is built from night school's REAL outbox writer (server/night_school/nightschool/real.export_outbox), so the
evidence strings are the ones the server writes. Every test uses a throwaway data folder; nothing touches %APPDATA%.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from star import learned_week as lw
from star.lessons import LessonStore
from star.worked_examples import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "night_school"))
from nightschool.real import export_outbox  # noqa: E402

PROMOTED = "Clamp a stamina value with math.clamp before writing it to an attribute."
LEGACY = "Check that a RemoteEvent argument is a number before using it on the server."
GATE = {"decision": "PROMOTE", "wins": 9, "losses": 2, "tasks": 24, "k": 2, "p_better": 0.0327, "p_worse": 0.99,
        "mde_tasks": 5}


def iso(days: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def outbox(tmp_path: Path) -> Path:
    data = tmp_path / "ns-data"
    data.mkdir()
    (data / "examples.jsonl").write_text(json.dumps({
        "task": "P-07", "category": "luau-modules", "prompt": "Write a Luau module that clamps stamina for a sprint bar.",
        "answer": "```luau\nlocal M = {}\nfunction M.clampStamina(v) return math.clamp(v, 0, 100) end\nreturn M\n```",
        "checks": ["luau_block", "require:clamp"], "lessons": ["L3"]}) + "\n", encoding="utf-8")
    state = {"lessons": {
        "L3": {"id": "L3", "text": PROMOTED, "status": "active",
               "promotion": {"fixed_tasks": ["P-01", "P-02"], "validation_before": "10/24", "validation_with": "15/24",
                             "gate": GATE}},
        "L1": {"id": "L1", "text": LEGACY, "status": "active",
               "promotion": {"fixed_tasks": ["P-03", "P-04"], "validation_before": "6/12", "validation_with": "6/12"}},
    }}
    settings = SimpleNamespace(outbox=tmp_path / "outbox", data=data)
    assert export_outbox(settings, state) == {"lessons": 2, "examples": 1}
    return settings.outbox


@pytest.fixture()
def bundle(tmp_path):
    return lw.build_bundle(outbox(tmp_path), project="MyGame", created=iso())


def note(home: Path, note_id: int) -> tuple:
    with sqlite3.connect(home / "knowledge" / "knowledge.sqlite3") as db:
        return db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()


def find_db(home: Path) -> Path:
    found = list((home / "knowledge").glob("*.sqlite3"))
    assert found
    return found[0]


def recalled(home: Path, project: str, prompt: str) -> list[str]:
    store = LessonStore(home)
    try:
        return [l.text for l in store.recall(project, prompt)]
    finally:
        store.close()


def test_bundle_carries_the_gate_verdict_from_the_real_outbox_evidence(bundle):
    by_id = {l["id"]: l for l in bundle["lessons"]}
    assert by_id["L3"]["gate"]["decision"] == "PROMOTE" and by_id["L3"]["gate"]["wins"] == 9
    assert by_id["L1"]["gate"]["decision"] == "LEGACY"
    assert len(bundle["examples"]) == 1 and bundle["examples"][0]["id"] == "night-school-P-07"
    lw.parse_bundle(bundle)


def test_a_tampered_verdict_or_secret_is_refused(bundle):
    forged = json.loads(json.dumps(bundle))
    forged["lessons"][1]["gate"] = {"decision": "PROMOTE"}           # claims a win its evidence does not show
    with pytest.raises(ValueError, match="gate verdict"):
        lw.parse_bundle(forged)
    leaky = json.loads(json.dumps(bundle))
    leaky["lessons"][0]["text"] = "Use the key " + "sk" + "-" + "abcdefghij" * 3 + " for the server."
    with pytest.raises(ValueError):
        lw.parse_bundle(leaky)
    with pytest.raises(ValueError, match="Unsupported"):
        lw.parse_bundle({**bundle, "format": "star-lessons-v1"})


def test_promoted_text_lesson_goes_live_visibly_and_is_recalled(tmp_path, bundle, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata-must-stay-empty"))
    home = tmp_path / "home"
    registry = lw.Registry(home)
    try:
        receipt = registry.apply(bundle, project="MyGame")
        assert receipt["live"] == 1 and receipt["candidates"] == 1 and receipt["examples"] == 1
        week = registry.week("MyGame")
    finally:
        registry.close()
    assert [i["kind"] for i in week["items"]] == ["lesson", "example"] or [i["kind"] for i in week["items"]] == ["example", "lesson"]
    lesson = next(i for i in week["items"] if i["kind"] == "lesson")
    assert lesson["title"] == PROMOTED and lesson["state"] == "live" and lesson["days_left"] == 14
    assert "paired gate PROMOTE: 9 wins / 2 losses" in lesson["evidence"] and lesson["gate"]["decision"] == "PROMOTE"
    assert PROMOTED in recalled(home, "MyGame", "make a sprint stamina bar with math.clamp")
    assert LEGACY not in recalled(home, "MyGame", "check a RemoteEvent argument number on the server")
    store = LessonStore(home)
    try:
        assert [l.text for l in store.list("MyGame", "candidate")] == [LEGACY]      # waits for the owner
    finally:
        store.close()
    text, used = select(home, "MyGame", "clamp stamina sprint bar module")
    assert used and used[0].id == "night-school-P-07"
    assert not (tmp_path / "appdata-must-stay-empty").exists()


def test_reapplying_the_same_bundle_changes_nothing(tmp_path, bundle):
    registry = lw.Registry(tmp_path)
    try:
        registry.apply(bundle)
        again = registry.apply(bundle)
    finally:
        registry.close()
    assert again["live"] == again["candidates"] == again["examples"] == 0 and again["skipped"] == 3


def test_owner_can_turn_automatic_use_off(tmp_path, bundle):
    registry = lw.Registry(tmp_path)
    try:
        receipt = registry.apply(bundle, auto_live=False)
        assert receipt["live"] == 0 and receipt["candidates"] == 2
    finally:
        registry.close()
    assert recalled(tmp_path, "MyGame", "sprint stamina math.clamp") == []


def test_expiry_after_14_days_stops_recall_even_before_the_sweep(tmp_path, bundle):
    registry = lw.Registry(tmp_path, clock=lambda: iso(-15))         # went live 15 days ago
    try:
        registry.apply(bundle)
    finally:
        registry.close()
    assert recalled(tmp_path, "MyGame", "sprint stamina math.clamp") == []          # no sweep has run yet
    assert select(tmp_path, "MyGame", "clamp stamina sprint bar module")[1] == []    # expired example unused
    registry = lw.Registry(tmp_path)
    try:
        week = registry.week("MyGame")                                               # sweeps
    finally:
        registry.close()
    assert {i["state"] for i in week["items"]} == {"expired"} and week["counts"]["expired"] == 2
    store = LessonStore(tmp_path)
    try:
        assert {l.text for l in store.list("MyGame", "rejected")} == {PROMOTED}
    finally:
        store.close()


def test_undo_then_restore_gives_back_the_byte_identical_row(tmp_path, bundle):
    registry = lw.Registry(tmp_path)
    try:
        registry.apply(bundle)
        item = next(i for i in registry.week("MyGame")["items"] if i["kind"] == "lesson")
        note_id = int(registry.db.execute("SELECT ref FROM learned_items WHERE id=?", (item["id"],)).fetchone()[0])
        before = tuple(registry.db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone())
        with pytest.raises(PermissionError):
            registry.undo("MyGame", item["id"])                                   # not an owner click
        registry.undo("MyGame", item["id"], human_approved=True)
        assert recalled(tmp_path, "MyGame", "sprint stamina math.clamp") == []
        registry.restore("MyGame", item["id"], human_approved=True)
        after = tuple(registry.db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone())
    finally:
        registry.close()
    assert after == before
    assert PROMOTED in recalled(tmp_path, "MyGame", "sprint stamina math.clamp")


def test_undo_and_restore_a_worked_example(tmp_path, bundle):
    registry = lw.Registry(tmp_path)
    try:
        registry.apply(bundle)
        item = next(i for i in registry.week("MyGame")["items"] if i["kind"] == "example")
        registry.undo("MyGame", item["id"], human_approved=True)
        assert select(tmp_path, "MyGame", "clamp stamina sprint bar module")[1] == []
        registry.restore("MyGame", item["id"], human_approved=True)
        assert select(tmp_path, "MyGame", "clamp stamina sprint bar module")[1]
    finally:
        registry.close()


def test_keep_makes_a_lesson_permanent_and_owner_approved(tmp_path, bundle):
    registry = lw.Registry(tmp_path)
    try:
        registry.apply(bundle)
        item = next(i for i in registry.week("MyGame")["items"] if i["kind"] == "lesson")
        week = registry.keep("MyGame", item["id"], human_approved=True)
    finally:
        registry.close()
    kept = next(i for i in week["items"] if i["id"] == item["id"])
    assert kept["state"] == "kept" and kept["expires_at"] == "" and kept["days_left"] is None
    later = lw.Registry(tmp_path, clock=lambda: iso(30))
    try:
        assert later.sweep("MyGame") == 1                       # only the example expires
    finally:
        later.close()
    store = LessonStore(tmp_path)
    try:
        lesson = next(l for l in store.list("MyGame", "accepted") if l.text == PROMOTED)
    finally:
        store.close()
    with sqlite3.connect(find_db(tmp_path)) as db:
        assert db.execute("SELECT revision FROM notes WHERE id=?", (lesson.id,)).fetchone()[0] == "owner-approved"


def test_restore_after_expiry_is_refused_but_keep_still_works(tmp_path, bundle):
    registry = lw.Registry(tmp_path, clock=lambda: iso(-20))
    try:
        registry.apply(bundle)
        item = next(i for i in registry.week("MyGame")["items"] if i["kind"] == "lesson")
        registry.undo("MyGame", item["id"], human_approved=True)
    finally:
        registry.close()
    registry = lw.Registry(tmp_path)
    try:
        with pytest.raises(ValueError, match="Keep"):
            registry.restore("MyGame", item["id"], human_approved=True)
        registry.keep("MyGame", item["id"], human_approved=True)
    finally:
        registry.close()
    assert PROMOTED in recalled(tmp_path, "MyGame", "sprint stamina math.clamp")


def test_an_owner_approval_on_the_review_page_is_never_undone_by_expiry(tmp_path, bundle):
    registry = lw.Registry(tmp_path, clock=lambda: iso(-20))
    try:
        registry.apply(bundle)
        note_id = int(registry.db.execute("SELECT ref FROM learned_items WHERE kind='lesson'").fetchone()[0])
    finally:
        registry.close()
    store = LessonStore(tmp_path)
    try:
        store.approve("MyGame", note_id, human_approved=True, text=PROMOTED + " Always.")   # owner's own wording
    finally:
        store.close()
    registry = lw.Registry(tmp_path)
    try:
        assert registry.sweep("MyGame") == 1                      # the example expires, the approved lesson does not
        states = {r["kind"]: r["state"] for r in registry.db.execute("SELECT kind,state FROM learned_items")}
    finally:
        registry.close()
    assert states == {"lesson": "kept", "example": "expired"}
    assert PROMOTED + " Always." in recalled(tmp_path, "MyGame", "sprint stamina math.clamp")


def test_bridge_actions_need_the_owner_click(tmp_path, bundle):
    registry = lw.Registry(tmp_path)
    try:
        registry.apply(bundle)
    finally:
        registry.close()
    listing = lw.handle_action(tmp_path, "MyGame", "learnedThisWeek", {})
    item = listing["items"][0]["id"]
    with pytest.raises(PermissionError):
        lw.handle_action(tmp_path, "MyGame", "learnedItem", {"op": "undo", "id": item})
    with pytest.raises(ValueError):
        lw.handle_action(tmp_path, "MyGame", "learnedItem", {"op": "approveEverything", "id": item, "approved": True})
    with pytest.raises(PermissionError):
        lw.handle_action(tmp_path, "MyGame", "setSetting", {})
    done = lw.handle_action(tmp_path, "MyGame", "learnedItem", {"op": "undo", "id": item, "approved": True})
    assert done["counts"]["undone"] == 1


def test_shipped_bundle_is_applied_once_per_version(tmp_path, bundle):
    path = tmp_path / "learning_bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    home = tmp_path / "home"
    assert lw.import_bundled(home, "1.0.0", bundle=path, project="Obby")["live"] == 1
    assert lw.import_bundled(home, "1.0.0", bundle=path, project="Obby") == {"status": "already"}
    assert lw.import_bundled(home, "1.0.0", bundle=tmp_path / "absent.json") == {"status": "none"}
    assert PROMOTED in recalled(home, "Obby", "sprint stamina math.clamp")


def test_cli_builds_and_imports_a_bundle(tmp_path, capsys):
    out = tmp_path / "bundle.json"
    assert lw.main(["bundle", "--outbox", str(outbox(tmp_path)), "--out", str(out)]) == 0
    assert "1 with a PROMOTE verdict" in capsys.readouterr().out
    assert lw.main(["bundle", "--outbox", str(tmp_path / "outbox"), "--out", str(out)]) == 2     # never overwrites
    assert lw.main(["import", str(out), "--home", str(tmp_path / "h"), "--project", "P"]) == 0
    assert "Live for 14 days: 1 lessons, 1 worked examples" in capsys.readouterr().out


def test_bundle_skips_worked_examples_the_importer_refuses(tmp_path):
    box = outbox(tmp_path)
    rows = (box / "worked-examples.jsonl").read_text(encoding="utf-8").splitlines()
    big = json.loads(rows[0])
    big.update(id="night-school-P-99", group_id="P-99", response="x" * 5000)
    (box / "worked-examples.jsonl").write_text("\n".join(rows + [json.dumps(big)]) + "\n", encoding="utf-8")
    report: dict = {}
    data = lw.build_bundle(box, report=report)
    assert len(data["examples"]) == 1 and report["skipped_examples"] == {"Invalid response": 1}
