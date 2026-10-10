"""The real-shell acceptance tool must be safe to point at an owner's PC.

These tests cover what the tool promises before it starts any window: it skips
when its inputs are absent, it only ever uses a profile folder it created, it
never talks to the real keyring, and its report cannot print the server key.
The live run itself needs PySide6 and a STAR Server and is skipped without them.
"""
import json
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import shell_acceptance as tool
from star.desktop_core import Conversations
from star.providers import validate_lan_endpoint

ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-acceptance-test-key-123456"


def test_skips_with_a_reason_when_the_server_settings_are_absent(monkeypatch, capsys):
    for name in (tool.ENV_KEY, tool.ENV_SERVER, tool.ENV_MODEL):
        monkeypatch.delenv(name, raising=False)
    assert tool.main([]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("SKIPPED: set ")
    for name in (tool.ENV_KEY, tool.ENV_SERVER, tool.ENV_MODEL):
        assert name in printed


def test_the_skip_reason_names_variables_and_never_their_values():
    reason = tool.skip_reason({tool.ENV_KEY: SECRET, tool.ENV_SERVER: "", tool.ENV_MODEL: "  "})
    assert tool.ENV_SERVER in reason and tool.ENV_MODEL in reason
    assert tool.ENV_KEY not in reason and SECRET not in reason


def test_only_a_folder_made_by_the_tool_is_accepted_as_a_profile(tmp_path, monkeypatch):
    assert not tool.is_acceptance_profile(tmp_path)            # no marker: could be anybody's data
    assert not tool.is_acceptance_profile(tmp_path / "missing")
    assert not tool.is_acceptance_profile(None)
    made = tool.new_profile(tmp_path)
    assert made.parent == tmp_path and (made / tool.MARKER).is_file()
    assert tool.is_acceptance_profile(made)
    # Even with a marker, a real data root is never a profile.
    monkeypatch.setattr(tool, "owner_data_roots", lambda: [made])
    assert not tool.is_acceptance_profile(made)


def test_the_owner_data_roots_cover_the_places_star_stores_data():
    roots = [str(path).replace("\\", "/") for path in tool.owner_data_roots()]
    assert any(root.endswith("AppData/Roaming") for root in roots)
    assert any(root.endswith("AppData/Local") for root in roots)


def test_a_phase_refuses_to_start_on_a_profile_it_did_not_make(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("APPDATA", str(tmp_path))  # an ordinary folder, like the owner's real one
    code = tool.main(["--child", "first", "--evidence", str(tmp_path), "--shots", str(tmp_path)])
    assert code == 3
    assert "REFUSED" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []         # nothing was created or written


def test_reusing_a_profile_requires_one_the_tool_created(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tool, "skip_reason", lambda env=None: None)
    monkeypatch.setenv(tool.ENV_KEY, SECRET)
    monkeypatch.setenv(tool.ENV_SERVER, "http://192.168.1.20:8080/v1")
    monkeypatch.setenv(tool.ENV_MODEL, "some-model")
    code = tool.main(["--profile", str(tmp_path), "--evidence", str(tmp_path / "evidence"), "--phases", "first"])
    assert code == 3
    out = capsys.readouterr().out
    assert "REFUSED" in out and SECRET not in out


def test_unknown_phases_are_rejected_before_anything_starts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tool, "skip_reason", lambda env=None: None)
    monkeypatch.setenv(tool.ENV_KEY, SECRET)
    monkeypatch.setenv(tool.ENV_SERVER, "http://192.168.1.20:8080/v1")
    monkeypatch.setenv(tool.ENV_MODEL, "some-model")
    assert tool.main(["--phases", "first,nonsense", "--evidence", str(tmp_path / "evidence")]) == 2
    assert "nonsense" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_a_phase_never_uses_the_real_keyring_or_the_real_profile(tmp_path):
    profile = tool.new_profile(tmp_path)
    env = tool.child_environment(profile, tool.WRONG_KEY, SECRET)
    assert env["APPDATA"] == str(profile)
    assert env["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
    assert env[tool.ENV_KEY] == tool.WRONG_KEY          # the wrong-key phase really sends the wrong key
    assert env["STAR_ACCEPTANCE_REAL_KEY"] == SECRET    # kept only to detect leaks


def test_the_failure_step_targets_a_closed_port_on_this_pc():
    endpoint = tool.closed_loopback_endpoint()
    assert validate_lan_endpoint(endpoint) == endpoint  # the app's own rule accepts it as a server address
    assert endpoint.startswith("http://127.0.0.1:")     # so the key cannot leave the machine
    port = int(endpoint.split(":")[2].split("/")[0])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        assert probe.connect_ex(("127.0.0.1", port)) != 0


def test_the_key_is_scrubbed_from_anything_that_is_written():
    assert tool.scrub(f"Authorization: Bearer {SECRET}", SECRET) == "Authorization: Bearer [key hidden]"
    assert tool.scrub("nothing secret", SECRET) == "nothing secret"
    assert tool.scrub("short keys are left alone: abc", "abc") == "short keys are left alone: abc"


def test_stored_messages_are_read_without_changing_the_database(tmp_path):
    profile = tool.new_profile(tmp_path)
    assert tool.read_messages(profile) == []
    chats = Conversations(profile / "STAR" / "conversations.sqlite3")
    try:
        chat = chats.active_chat("STAR")
        asked = chats.add("STAR", "user", "hello", chat_id=chat)
        chats.add_terminal("STAR", chat, asked, "cancelled", "Request stopped.")
    finally:
        chats.close()
    before = (profile / "STAR" / "conversations.sqlite3").read_bytes()
    rows = tool.read_messages(profile)
    assert [(r["role"], r["status"], r["reply_to"]) for r in rows] == [("user", "complete", None), ("event", "cancelled", asked)]
    assert (profile / "STAR" / "conversations.sqlite3").read_bytes() == before


def test_the_upgrade_profile_is_what_the_released_app_leaves_behind(tmp_path):
    profile = tool.new_profile(tmp_path)
    tool.seed_released_profile(profile, "http://127.0.0.1:8080/v1")
    saved = json.loads((profile / "STAR" / "settings.json").read_text(encoding="utf-8"))
    assert "provider" not in saved and "server_endpoint" not in saved   # fields the release did not have
    with sqlite3.connect(profile / "STAR" / "conversations.sqlite3") as old:
        columns = {row[1] for row in old.execute("PRAGMA table_info(messages)")}
    assert columns == {"id", "project", "role", "body", "created"}      # no chat threads, no turn outcomes yet
    # This build opens it in place: same ids, same text, one "Previous conversation".
    chats = Conversations(profile / "STAR" / "conversations.sqlite3")
    try:
        assert chats.active_chat("STAR") == "legacy"
        assert [(r["id"], r["role"], r["body"]) for r in chats.recent_records("STAR", chat_id="legacy")] == [
            (index + 1, role, body) for index, (role, body) in enumerate(tool.RELEASED_MESSAGES)]
        assert chats.list_chats("STAR")[0]["title"] == "Previous conversation"
    finally:
        chats.close()
    assert len(tool.read_messages(profile)) == len(tool.RELEASED_MESSAGES)


def test_a_step_fails_on_any_failed_check_but_not_on_a_known_defect(capsys):
    step = tool.Step("first", "example")
    assert step.check(True, "works") is True
    assert step.status == "PASS"
    assert step.check(False, "known gap", "detail", known="tracked defect") is False
    assert step.status == "PASS"                         # documented, so the run stays green
    assert step.as_dict()["checks"][1]["known"] == "tracked defect"
    assert step.check(False, "really broken", "detail") is False
    assert step.status == "FAIL"
    out = capsys.readouterr().out
    assert "KNOWN known gap" in out and "FAIL really broken" in out


def test_the_table_lists_failed_checks_and_known_defects():
    step = tool.Step("first", "send")
    step.check(False, "the answer is stored")
    known = tool.Step("pages", "sidebar")
    known.check(False, "the sidebar stays collapsed", known="off-the-record profile")
    table = tool.format_table([step.as_dict(), known.as_dict()])
    assert "first      send                  FAIL" in table and "the answer is stored" in table
    assert "pages      sidebar               PASS" in table
    assert "Known defects seen again" in table and "off-the-record profile" in table


def test_timing_summaries_are_plain_numbers():
    assert tool.summarize([]) == {"n": 0}
    assert tool.summarize([10, 30, 20]) == {"n": 3, "median": 20, "p95": 30, "max": 30}


def test_the_documented_phases_are_the_ones_the_tool_runs():
    for phase in tool.PHASES:
        assert f"    {phase}" in tool.__doc__
    assert tool.build_parser().parse_args(["--phases", "first"]).phases == "first"


@pytest.mark.skipif(tool.skip_reason() is not None, reason=f"live shell run: {tool.skip_reason()}")
def test_live_first_send_stop_failure_and_restart_against_a_real_server(tmp_path):
    """Runs the real window against the real server. Minutes, not seconds."""
    finished = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "shell_acceptance.py"), "--phases", "first,restart",
         "--evidence", str(tmp_path / "evidence")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=3600)
    report = json.loads((tmp_path / "evidence" / "report.json").read_text(encoding="utf-8"))
    failed = [f"{s['phase']}/{s['name']}" for s in report["steps"] if s["status"] == "FAIL"]
    assert finished.returncode == 0 and not failed, finished.stdout[-4000:]
