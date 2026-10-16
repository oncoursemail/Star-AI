"""Safety and reproducibility checks for owner-triggered offline delivery packets."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zipfile

import pytest

from star.delivery_package import build_delivery_packet


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "creator-work"
    (workspace / "art").mkdir(parents=True)
    (workspace / "source").mkdir()
    (workspace / "art" / "cover.png").write_bytes(b"PNG test fixture, not a real print image")
    (workspace / "source" / "notes.md").write_text("# Original description\n", encoding="utf-8")
    return workspace


def _spec(**changes: object) -> dict[str, object]:
    spec: dict[str, object] = {
        "channel": "fiverr",
        "brief": "Original indie-game UI reference and delivery notes.",
        "files": ["art/cover.png", "source/notes.md"],
    }
    spec.update(changes)
    return spec


def test_draft_zip_contains_only_selected_assets_and_hash_receipts(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target = tmp_path / "delivery.zip"
    result = build_delivery_packet(workspace, _spec(), target)

    assert result["classification"] == "local_draft_packet_not_a_customer_delivery"
    assert result["seller_action_executed"] is False
    assert result["output_sha256"] == sha256(target.read_bytes()).hexdigest()
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [
            "MANIFEST.json", "REVIEW_BEFORE_SENDING.txt",
            "deliverables/art/cover.png", "deliverables/source/notes.md",
        ]
        receipt = json.loads(archive.read("MANIFEST.json"))
        assert receipt["status"] == "draft_pending_independent_owner_review"
        assert receipt["marketplace_actions_executed"] is False
        assert receipt["rights_and_design_verified"] is False
        assert len(receipt["review_required"]) == 5
        for item in receipt["files"]:
            contents = archive.read("deliverables/" + item["path"])
            assert item["bytes"] == len(contents)
            assert item["sha256"] == sha256(contents).hexdigest()
        assert b"NOT APPROVED" in archive.read("REVIEW_BEFORE_SENDING.txt")


def test_draft_is_reproducible_and_approval_claims_are_ignored(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = tmp_path / "one.zip"
    second = tmp_path / "two.zip"
    spec = _spec(channel="etsy", owner_approved=True, visual_qa_passed=True)
    a = build_delivery_packet(workspace, spec, first)
    b = build_delivery_packet(workspace, spec, second)
    assert a["output_sha256"] == b["output_sha256"]
    assert b["manifest"]["rights_and_design_verified"] is False
    assert b["manifest"]["status"] == "draft_pending_independent_owner_review"


@pytest.mark.parametrize("path", [
    "../outside.png", "/etc/passwd", "art/../cover.png", "art//cover.png",
    "art/.env", ".git/config", "secrets/token.txt", "art\\cover.png",
    "C:/Users/file.png", "art/image.exe",
])
def test_unsafe_paths_are_rejected(tmp_path: Path, path: str) -> None:
    root = _workspace(tmp_path)
    with pytest.raises(ValueError):
        build_delivery_packet(root, _spec(files=[path]), tmp_path / "package.zip")
    assert not (tmp_path / "package.zip").exists()


def test_symlink_out_of_workspace_is_rejected(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    outsider = tmp_path / "other.png"
    outsider.write_bytes(b"private data")
    link = root / "art" / "shortcut.png"
    try:
        link.symlink_to(outsider)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this runner")
    with pytest.raises(ValueError, match="symlink"):
        build_delivery_packet(root, _spec(files=["art/shortcut.png"]), tmp_path / "package.zip")


def test_no_overwrites_and_no_nested_outputs(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    target = tmp_path / "package.zip"
    target.write_bytes(b"preserve existing buyer package")
    with pytest.raises(ValueError, match="already exists"):
        build_delivery_packet(root, _spec(), target)
    assert target.read_bytes() == b"preserve existing buyer package"

    with pytest.raises(ValueError, match="outside"):
        build_delivery_packet(root, _spec(), root / "package.zip")


def test_missing_files_bad_briefs_and_collisions_fail(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    for spec in (
        _spec(files=[]),
        _spec(files=["art/missing.png"]),
        _spec(brief="  "),
        _spec(channel="another-marketplace"),
        _spec(files=["art/cover.png", "ART/COVER.PNG"]),
        _spec(files=["source/notes.md", "source/notes.md"]),
    ):
        with pytest.raises(ValueError):
            build_delivery_packet(root, spec, tmp_path / "package.zip")
    assert not (tmp_path / "package.zip").exists()


def test_size_guard_prevents_zip_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from star import delivery_package
    root = _workspace(tmp_path)
    monkeypatch.setattr(delivery_package, "MAX_EACH_BYTES", 3)
    with pytest.raises(ValueError, match="limit"):
        build_delivery_packet(root, _spec(), tmp_path / "package.zip")
    assert not (tmp_path / "package.zip").exists()
