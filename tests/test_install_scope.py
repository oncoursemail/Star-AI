"""Issue 121: the updater says beforehand when Windows will ask for administrator approval.

An all-users copy of STAR is registered under HKEY_LOCAL_MACHINE and Setup upgrades it in
administrative mode (Inno Setup's UsePreviousPrivileges), so the UAC prompt on every such upgrade is
required. Nothing here avoids it; these tests cover the read-only detection and the notice.
"""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from star import updates
from star.react_shell import prepare_desktop_update


def reader(entries):
    asked = []

    def read(hive):
        asked.append(hive)
        value = entries.get(hive)
        if isinstance(value, Exception):
            raise value
        return value
    read.asked = asked
    return read


def test_the_running_folder_decides_the_scope(tmp_path):
    app = tmp_path / "Programs" / "STAR"
    other = tmp_path / "Program Files" / "STAR"
    # Inno writes InstallLocation with a trailing separator.
    assert updates.install_scope(app, reader({"HKCU": str(app) + os.sep})) == "per-user"
    assert updates.install_scope(app, reader({"HKCU": str(app)})) == "per-user"
    assert updates.install_scope(other, reader({"HKLM": str(other)})) == "all-users"
    # Both registered: the copy that is running is the one that counts.
    both = {"HKCU": str(app), "HKLM": str(other)}
    assert updates.install_scope(app, reader(both)) == "per-user"
    assert updates.install_scope(other, reader(both)) == "all-users"
    # Not this folder (the portable ZIP, or another account's copy), empty values, unreadable entries.
    for entries in ({}, {"HKCU": str(other)}, {"HKLM": "  "}, {"HKCU": None, "HKLM": None},
                    {"HKCU": OSError("denied"), "HKLM": PermissionError("denied")}):
        assert updates.install_scope(app, reader(entries)) == "unknown"
    # A failing per-user read does not hide an all-users entry.
    assert updates.install_scope(other, reader({"HKCU": OSError("x"), "HKLM": str(other)})) == "all-users"


def test_outside_a_packaged_windows_build_nothing_is_read(monkeypatch):
    monkeypatch.setattr(updates, "_read_install_location", lambda hive: pytest.fail("must not read the registry"))
    monkeypatch.setattr(updates.sys, "frozen", False, raising=False)
    assert updates.install_scope() == "unknown"


def test_the_uninstall_entry_matches_the_installer_app_id():
    script = (Path(__file__).resolve().parents[1] / "installer" / "STAR.iss").read_text(encoding="utf-8")
    app_id = script.split("AppId={", 1)[1].split("\n", 1)[0].strip()          # "{E2B5...}" after Inno's "{{" escape
    assert updates.UNINSTALL_KEY == r"Software\Microsoft\Windows\CurrentVersion\Uninstall" + "\\" + app_id + "_is1"


def test_the_registry_is_only_opened_for_reading():
    import inspect
    source = inspect.getsource(updates._read_install_location)
    assert "KEY_READ" in source and "OpenKey(" in source
    for writer in ("SetValue", "CreateKey", "DeleteKey", "DeleteValue", "KEY_WRITE", "KEY_ALL_ACCESS"):
        assert writer not in source


@pytest.mark.parametrize("scope, warned", [("all-users", True), ("per-user", False), ("unknown", False)])
def test_the_update_progress_names_the_administrator_prompt(monkeypatch, tmp_path, scope, warned):
    candidate = SimpleNamespace(path=tmp_path / "STAR-Setup-v9.9.9.exe", version="9.9.9",
                                checksum_verified=True, expected_sha256="a" * 64)
    monkeypatch.setattr(updates, "get_latest", lambda: SimpleNamespace(available=True))

    def stage(result, home, progress):
        progress(5, 10)
        return candidate
    monkeypatch.setattr(updates, "stage_installer", stage)
    monkeypatch.setattr(updates, "select_downloaded_installer", lambda path: candidate)
    monkeypatch.setattr(updates, "install_scope", lambda: scope)
    events = []
    bridge = SimpleNamespace(pending_update=None, _emit=lambda rid, kind, data: events.append(data),
                             shutdownRequested=SimpleNamespace(emit=lambda: events.append("shutdown")))
    outcome = prepare_desktop_update(bridge, "request", tmp_path)
    assert outcome == {"status": "pending_restart", "version": "9.9.9", "administrator_prompt": warned}
    phases = [event["phase"] for event in events if isinstance(event, dict)]
    assert len(phases) == 2 and events[-1] == "shutdown"
    assert all((updates.ADMIN_PROMPT_NOTE in phase) is warned for phase in phases)
    assert bridge.pending_update is candidate
