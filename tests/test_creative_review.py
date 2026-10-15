"""Make review evidence falsifiable without claiming the pictures are aesthetically good."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from star.creative_review import assess, capture_evidence, compare_pixels, main, record_owner_review


def _fixture(tmp_path: Path) -> dict:
    (tmp_path / "app.tsx").write_text("export const App = () => 1", encoding="utf-8")
    Image.new("RGB", (320, 200), "#12161b").save(tmp_path / "wide.png")
    Image.new("RGB", (220, 300), "#12161b").save(tmp_path / "compact.png")
    return {"project": "STAR", "artifact": "desktop-chat", "source": "app.tsx", "views": {
        "desktop": {"file": "wide.png", "width": 320, "height": 200},
        "compact": {"file": "compact.png", "width": 220, "height": 300}}}


def test_owner_rejection_cannot_be_lost_and_owner_approval_is_exact(tmp_path):
    manifest = _fixture(tmp_path)
    database = tmp_path / "reviews.db"
    first = capture_evidence(tmp_path, manifest)
    assert assess(database, first)["status"] == "awaiting_owner_review"
    record_owner_review(database, first, "reject", "Typography overlaps the toolbar")
    rejected = assess(database, first)
    assert rejected["status"] == "owner_rejected"
    assert "Typography overlaps" in rejected["previous_rejection"]
    with pytest.raises(ValueError, match="actionable"):
        record_owner_review(database, first, "reject")
    # New source candidate is NOT automatically accepted; objection remains available.
    (tmp_path / "app.tsx").write_text("export const App = () => 2", encoding="utf-8")
    updated = capture_evidence(tmp_path, manifest)
    assert updated["evidence_key"] != first["evidence_key"]
    assert assess(database, updated)["status"] == "awaiting_owner_review"
    assert assess(database, updated)["previous_rejection"] == "Typography overlaps the toolbar"
    record_owner_review(database, updated, "approve", "Accepted after rendered comparison")
    assert assess(database, updated)["owner_approved"]
    assert not assess(database, first)["owner_approved"]


def test_new_screenshot_invalidates_prior_approval(tmp_path):
    manifest = _fixture(tmp_path)
    db = tmp_path / "reviews.db"
    original = capture_evidence(tmp_path, manifest)
    record_owner_review(db, original, "approve")
    assert assess(db, original)["owner_approved"]
    Image.new("RGB", (320, 200), "#191d22").save(tmp_path / "wide.png")
    newer = capture_evidence(tmp_path, manifest)
    assert newer["evidence_key"] != original["evidence_key"]
    assert assess(db, newer)["status"] == "awaiting_owner_review"


def test_pixel_drift_is_measured_not_confused_with_design_approval(tmp_path):
    manifest = _fixture(tmp_path)
    Image.new("RGB", (320, 200), "#12161b").save(tmp_path / "baseline.png")
    manifest["baselines"] = {"desktop": "baseline.png"}
    evidence = capture_evidence(tmp_path, manifest)
    assert evidence["captures"]["desktop"]["pixel_change_ratio"] == 0.0
    actual = Image.new("RGB", (320, 200), "#12161b")
    for x in range(30):
        for y in range(30):
            actual.putpixel((x, y), (255, 255, 255))
    actual.save(tmp_path / "wide.png")
    changed = capture_evidence(tmp_path, manifest)
    assert changed["captures"]["desktop"]["pixel_change_ratio"] == round(900 / 64000, 8)
    assert "never establish design quality" in changed["warning"]
    assert compare_pixels(Image.new("RGB", (20, 20)), Image.new("RGB", (20, 20))) == 0.0
    with pytest.raises(ValueError):
        compare_pixels(Image.new("RGB", (20, 20)), Image.new("RGB", (19, 20)))


@pytest.mark.parametrize("bad", [
    {"source": "../private.txt"}, {"source": "/etc/passwd"},
    {"views": {}},
    {"views": {"desktop": {"file": "wide.png", "width": True, "height": 200}}},
    {"views": {"desktop": {"file": "wide.png", "width": 300, "height": 200}}},
])
def test_invalid_evidence_fails_closed(tmp_path, bad):
    manifest = _fixture(tmp_path)
    manifest.update(bad)
    with pytest.raises((ValueError, FileNotFoundError)):
        capture_evidence(tmp_path, manifest)


def test_screenshot_symlink_refused(tmp_path):
    manifest = _fixture(tmp_path)
    (tmp_path / "shortcut.png").symlink_to(tmp_path / "wide.png")
    manifest["views"]["desktop"]["file"] = "shortcut.png"
    with pytest.raises(ValueError, match="symlink"):
        capture_evidence(tmp_path, manifest)


def test_review_cli_refuses_automated_approval(tmp_path, capsys):
    manifest = _fixture(tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    db = tmp_path / "state" / "reviews.db"
    assert main(["inspect", "manifest.json", "--workspace", str(tmp_path), "--database", str(db)]) == 0
    assert "awaiting_owner_review" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["review", "manifest.json", "--workspace", str(tmp_path), "--database", str(db),
              "--decision", "approve"])
    assert assess(db, capture_evidence(tmp_path, manifest))["status"] == "awaiting_owner_review"
