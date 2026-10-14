"""settings.json is written in one step and a damaged file no longer stops STAR from starting."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os

import pytest

from star import atomic_io
from star.atomic_io import atomic_write_text, move_aside
from star.desktop_core import Settings


def test_atomic_write_creates_parent_and_leaves_no_temporary(tmp_path):
    target = tmp_path / "deep" / "settings.json"
    atomic_write_text(target, '{"a": 1}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert [p.name for p in target.parent.iterdir()] == ["settings.json"]


def test_failed_swap_keeps_the_old_file_and_removes_the_temporary(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def broken_replace(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr(atomic_io.os, "replace", broken_replace)
    with pytest.raises(OSError):
        atomic_write_text(target, '{"new": true}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


def test_save_goes_through_the_atomic_writer(tmp_path, monkeypatch):
    seen = []
    real = atomic_io.os.replace

    def spy(source, destination):
        seen.append((os.path.basename(source), os.path.basename(destination)))
        return real(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", spy)
    file = tmp_path / "settings.json"
    Settings(project="Atomic").save(file)
    assert seen and seen[0][1] == "settings.json" and seen[0][0] != "settings.json"
    assert Settings.load(file).project == "Atomic"


@pytest.mark.parametrize("content", [
    b'{"project": "Half',           # truncated mid-write (the old non-atomic save)
    b"",                            # zero-length file after a crash
    b"\xff\xfe\x00garbage",         # not UTF-8
    b"[1, 2, 3]",                   # valid JSON that is not an object
    b"null",
])
def test_damaged_settings_load_defaults_and_keep_a_copy(tmp_path, content, caplog):
    file = tmp_path / "settings.json"
    file.write_bytes(content)
    with caplog.at_level("WARNING"):
        loaded = Settings.load(file)
    assert asdict(loaded) == asdict(Settings())
    assert not file.exists()
    backups = list(tmp_path.glob("settings.json.corrupt-*"))
    assert len(backups) == 1 and backups[0].read_bytes() == content
    assert "using defaults" in caplog.text
    # The next save writes a clean file and the copy stays for the owner.
    loaded.save(file)
    assert Settings.load(file).project == Settings().project
    assert backups[0].exists()


def test_defaults_after_recovery_keep_risky_tools_off(tmp_path):
    file = tmp_path / "settings.json"
    file.write_text('{"studio_edit": true, "studio_luau": tru', encoding="utf-8")
    loaded = Settings.load(file)
    assert loaded.studio_edit is False and loaded.studio_luau is False


def test_good_settings_are_not_moved(tmp_path):
    file = tmp_path / "settings.json"
    Settings(project="Keep").save(file)
    assert Settings.load(file).project == "Keep"
    assert list(tmp_path.glob("*.corrupt-*")) == []


def test_move_aside_never_overwrites_an_earlier_copy(tmp_path):
    moment = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
    first, second = tmp_path / "a.json", tmp_path / "a.json"
    first.write_text("one", encoding="utf-8")
    one = move_aside(first, now=moment)
    second.write_text("two", encoding="utf-8")
    two = move_aside(second, now=moment)
    assert one != two
    assert one.read_text(encoding="utf-8") == "one" and two.read_text(encoding="utf-8") == "two"
    assert one.name == "a.json.corrupt-20261013T120000Z"


def test_a_locked_settings_file_is_not_treated_as_damaged(tmp_path, monkeypatch):
    """Review fix: a sharing violation while another STAR process swaps the file in (Windows) or a permission
    error is not damage: the owner's file must stay where it is instead of being moved aside for defaults."""
    from pathlib import Path
    target = tmp_path / "settings.json"
    Settings(model="kept").save(target)
    real = Path.read_text
    failures = [0]

    def locked(self, *args, **kwargs):
        if self == target:
            failures[0] += 1
            raise PermissionError(13, "The process cannot access the file", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(PermissionError):
        Settings.load(target)
    assert failures[0] == 4 and [p.name for p in tmp_path.iterdir()] == ["settings.json"]

    failures[0] = 0
    calls = iter([True, False])               # locked once, then readable: the saved settings load

    def briefly_locked(self, *args, **kwargs):
        if self == target and next(calls, False):
            raise PermissionError(13, "busy", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", briefly_locked)
    assert Settings.load(target).model == "kept"


def test_swap_waits_out_a_brief_windows_sharing_lock(tmp_path, monkeypatch):
    # On Windows, os.replace fails with PermissionError while another handle has the old file open.
    target = tmp_path / "settings.json"
    target.write_text('{"old": true}', encoding="utf-8")
    real, refusals = atomic_io.os.replace, []

    def locked_twice(source, destination):
        if len(refusals) < 2:
            refusals.append(destination)
            raise PermissionError(13, "The process cannot access the file")
        return real(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", locked_twice)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _seconds: None)
    atomic_write_text(target, '{"new": true}')
    assert len(refusals) == 2 and json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


def test_a_lasting_lock_still_fails_and_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def always_locked(source, destination):
        raise PermissionError(13, "The process cannot access the file")

    monkeypatch.setattr(atomic_io.os, "replace", always_locked)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _seconds: None)
    with pytest.raises(PermissionError):
        atomic_write_text(target, '{"new": true}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]
