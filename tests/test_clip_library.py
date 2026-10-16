"""No recorder installed: these validate the folder boundary and metadata only."""
from pathlib import Path
import pytest

from star.clip_library import ClipLibrary, MAX_ITEMS


def test_empty_scope_and_read_only_metadata(tmp_path):
    library = ClipLibrary()
    assert library.list_clips()["selected"] is False
    folder = tmp_path / "Medal"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"video")
    (folder / "notes.txt").write_text("private")
    report = library.choose(folder)
    assert report["folder"] == "Medal"
    assert len(report["clips"]) == 1
    assert report["clips"][0]["relative"] == "clip.mp4"
    assert "notes.txt" not in str(report)
    assert library.allowed_clip(report["clips"][0]["id"]) == folder / "clip.mp4"
    assert (folder / "clip.mp4").read_bytes() == b"video"


def test_nested_recorders_supported_with_depth_limit(tmp_path):
    folder = tmp_path / "Outplayed"
    (folder / "Game" / "Match").mkdir(parents=True)
    (folder / "Game" / "Match" / "win.MKV").write_bytes(b"rec")
    result = ClipLibrary().choose(folder)
    assert [item["relative"] for item in result["clips"]] == ["Game/Match/win.MKV"]


def test_symlink_escape_and_forged_id_refused(tmp_path):
    folder = tmp_path / "Clips"
    folder.mkdir()
    outside = tmp_path / "private.mp4"
    outside.write_bytes(b"PRIVATE")
    link = folder / "escape.mp4"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks require special permissions on this runner")
    lib = ClipLibrary()
    assert lib.choose(folder)["clips"] == []
    with pytest.raises((ValueError, PermissionError)):
        lib.allowed_clip("../private.mp4")
    with pytest.raises(PermissionError):
        lib.allowed_clip("a" * 20)
    with pytest.raises(ValueError):
        lib.choose(link)


def test_stale_file_replaced_with_symlink_is_refused(tmp_path):
    folder = tmp_path / "Medal"
    folder.mkdir()
    path = folder / "clip.mp4"
    path.write_bytes(b"ok")
    lib = ClipLibrary()
    file_id = lib.choose(folder)["clips"][0]["id"]
    path.unlink()
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"private")
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks require special permissions on this runner")
    with pytest.raises(PermissionError):
        lib.allowed_clip(file_id)


def test_selection_replaces_scope_and_disconnect_revokes(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir(); b.mkdir()
    (a / "a.mp4").write_bytes(b"a")
    (b / "b.mp4").write_bytes(b"b")
    lib = ClipLibrary()
    old = lib.choose(a)["clips"][0]["id"]
    new = lib.choose(b)["clips"][0]["id"]
    with pytest.raises(PermissionError):
        lib.allowed_clip(old)
    assert lib.allowed_clip(new).parent == b
    lib.clear()
    with pytest.raises(PermissionError):
        lib.allowed_clip(new)


def test_cap_and_sort_recent_clips_first(tmp_path):
    for i in range(MAX_ITEMS + 5):
        p = tmp_path / f"clip-{i:04d}.mp4"
        p.write_bytes(b"v")
        p.touch()
    result = ClipLibrary().choose(tmp_path)
    assert len(result["clips"]) == MAX_ITEMS
    assert result["truncated"]
    assert len({x["id"] for x in result["clips"]}) == MAX_ITEMS
