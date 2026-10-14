"""Offline end-to-end updater fixtures; no GitHub, installer execution, or Qt needed."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from star import react_shell, updates
from star.react_shell import finish_desktop_update, prepare_desktop_update, run_desktop


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """The harness must run offline: any real socket connection fails the test."""
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("updater harness attempted a real network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _patch_release(delta: int) -> str:
    """The running version with its patch number raised, so a release bump cannot break these tests."""
    major, minor, patch = updates.Version(updates.__version__).parts
    return f"{major}.{minor}.{patch + delta}"


# A release bump must not break these tests: derive the versions from the running one.
NEWER, CURRENT, OLDER = _patch_release(1), _patch_release(0), "0.0.0"


def _payload(header: bytes = b"MZ") -> bytes:
    return header + b"U" * (updates.MIN_INSTALLER_BYTES + 64)


def _release(version: str, payload: bytes, checksum: str | None = None) -> dict:
    filename = f"STAR-Setup-v{version}.exe"
    return {
        "tag_name": f"v{version}",
        "assets": [{
            "name": filename,
            "size": len(payload),
            "digest": "sha256:" + (checksum or hashlib.sha256(payload).hexdigest()),
            "browser_download_url":
                f"https://github.com/{updates.REPO}/releases/download/v{version}/{filename}",
        }],
    }


def _feed(release: dict, payload: bytes, requests: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url) == updates.API:
            return httpx.Response(200, json=release)
        assert str(request.url) == release["assets"][0]["browser_download_url"]
        return httpx.Response(200, content=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("version,offered", [
    (NEWER, True), (CURRENT, False), (OLDER, False),
])
def test_release_feed_only_offers_newer_versions(version, offered):
    requests = []
    with _feed(_release(version, _payload()), _payload(), requests) as client:
        result = updates.get_latest(client)
    assert result.available is offered
    assert result.anonymous_access
    assert requests == [updates.API]


def test_download_verified_and_installer_arguments_after_clean_shutdown(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys, "platform", "win32")
    payload = _payload()
    requests = []
    with _feed(_release(NEWER, payload), payload, requests) as client:
        result = updates.get_latest(client)
        candidate = updates.stage_installer(result, tmp_path, client)
    assert candidate.checksum_verified
    assert candidate.path.read_bytes() == payload
    assert len(requests) == 2

    events = []
    monkeypatch.setattr(
        updates.subprocess, "Popen",
        lambda args, **kw: events.append(("launch", args, kw)),
    )
    class Shell:
        def __init__(self):
            self.bridge = SimpleNamespace(pending_update=candidate)
        def close(self):
            events.append(("close",))
    class Instance:
        def close(self):
            events.append(("release_lock",))
    finish_desktop_update(Shell(), Instance())
    assert [event[0] for event in events] == ["close", "release_lock", "launch"]
    args, kwargs = events[-1][1:]
    assert args == [str(candidate.path), "/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"]
    assert kwargs["cwd"] == str(candidate.path.parent)
    assert kwargs["shell"] is False
    assert kwargs["stdin"] == updates.subprocess.DEVNULL
    assert kwargs["close_fds"] is True


def test_corrupted_payload_is_refused_and_no_exe_is_staged(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys, "platform", "win32")
    payload = _payload()
    requests = []
    with _feed(_release(NEWER, payload, "a" * 64), payload, requests) as client:
        result = updates.get_latest(client)
        with pytest.raises(ValueError, match="SHA-256"):
            updates.stage_installer(result, tmp_path, client)
    assert not list(tmp_path.rglob("*.exe"))
    assert not list(tmp_path.rglob("*.part"))


def test_cancel_without_pending_installer_only_closes_app(monkeypatch):
    events = []
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("Cancellation must not run Setup"),
    )
    shell = SimpleNamespace(
        bridge=SimpleNamespace(pending_update=None),
        close=lambda: events.append("close"),
    )
    instance = SimpleNamespace(close=lambda: events.append("release_lock"))
    finish_desktop_update(shell, instance)
    assert events == ["close", "release_lock"]


def test_close_failure_does_not_launch_installer(monkeypatch):
    """Setup cannot race a failed shutdown, but the instance lock is released."""
    events = []
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("Must not launch if close fails"),
    )
    shell = SimpleNamespace(
        bridge=SimpleNamespace(pending_update=object()),
        close=lambda: (_ for _ in ()).throw(RuntimeError("close failed")),
    )
    with pytest.raises(RuntimeError, match="close failed"):
        finish_desktop_update(shell, SimpleNamespace(close=lambda: events.append("released")))
    assert events == ["released"]


def test_real_bridge_worker_records_pending_before_requesting_shutdown(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys, "platform", "win32")
    payload = _payload()
    requests = []
    events = []
    with _feed(_release(NEWER, payload), payload, requests) as client:
        original_get_latest = updates.get_latest
        monkeypatch.setattr(updates, "get_latest", lambda: original_get_latest(client))
        original_stage = updates.stage_installer
        monkeypatch.setattr(
            updates, "stage_installer",
            lambda result, home, progress: original_stage(result, home, client, progress),
        )
        class Bridge:
            pending_update = None
            def __init__(self):
                self.shutdownRequested = SimpleNamespace(emit=self.request_shutdown)
            def _emit(self, _rid, kind, data):
                events.append((kind, data))
            def request_shutdown(self):
                assert self.pending_update is not None
                assert self.pending_update.checksum_verified
                events.append(("shutdown",))
        bridge = Bridge()
        outcome = prepare_desktop_update(bridge, "test-request", tmp_path)
    assert outcome == {"status": "pending_restart", "version": NEWER, "administrator_prompt": False}
    assert events[-1] == ("shutdown",)
    assert bridge.pending_update.path.is_file()


def test_real_bridge_worker_does_not_quit_for_current_release(tmp_path, monkeypatch):
    requests = []
    with _feed(_release(CURRENT, _payload()), _payload(), requests) as client:
        original_get_latest = updates.get_latest
        monkeypatch.setattr(updates, "get_latest", lambda: original_get_latest(client))
        bridge = SimpleNamespace(
            pending_update=None,
            shutdownRequested=SimpleNamespace(
                emit=lambda: pytest.fail("No upgrade must not request shutdown"),
            ),
        )
        with pytest.raises(RuntimeError, match="No newer"):
            prepare_desktop_update(bridge, "request", tmp_path)
        assert bridge.pending_update is None


def test_finish_without_instance_lock_still_closes_window(monkeypatch):
    """STAR_ALLOW_MULTIPLE_INSTANCES and the doctor flags run without a lock object."""
    events = []
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("Cancellation must not run Setup"),
    )
    shell = SimpleNamespace(
        bridge=SimpleNamespace(pending_update=None),
        close=lambda: events.append("close"),
    )
    finish_desktop_update(shell, None)
    assert events == ["close"]


def test_missing_window_still_releases_lock_and_runs_nothing(monkeypatch):
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("No window means no staged update"),
    )
    events = []
    finish_desktop_update(None, SimpleNamespace(close=lambda: events.append("release_lock")))
    assert events == ["release_lock"]


def test_unverified_candidate_is_never_queued_or_quit(tmp_path, monkeypatch):
    candidate = updates.InstallerCandidate(tmp_path / "x.exe", NEWER, checksum_verified=False)
    monkeypatch.setattr(updates, "get_latest", lambda: updates.UpdateResult(True, NEWER, "u"))
    monkeypatch.setattr(updates, "stage_installer", lambda *args, **kwargs: candidate)
    bridge = SimpleNamespace(
        pending_update=None,
        _emit=lambda *args: None,
        shutdownRequested=SimpleNamespace(emit=lambda: pytest.fail("Must not quit")),
    )
    with pytest.raises(PermissionError, match="checksum-verified"):
        prepare_desktop_update(bridge, "request", tmp_path)
    assert bridge.pending_update is None


def test_installer_that_setup_would_refuse_is_reported_before_the_window_closes(tmp_path, monkeypatch):
    """The checksum matches, but a file without the MZ header cannot run: say so while the UI is open."""
    monkeypatch.setattr(updates.sys, "platform", "win32")
    payload = _payload(header=b"XX")
    with _feed(_release(NEWER, payload), payload, []) as client:
        original_get_latest, original_stage = updates.get_latest, updates.stage_installer
        monkeypatch.setattr(updates, "get_latest", lambda: original_get_latest(client))
        monkeypatch.setattr(
            updates, "stage_installer",
            lambda result, home, progress: original_stage(result, home, client, progress),
        )
        bridge = SimpleNamespace(
            pending_update=None,
            _emit=lambda *args: None,
            shutdownRequested=SimpleNamespace(emit=lambda: pytest.fail("Must not quit")),
        )
        with pytest.raises(ValueError, match="not a Windows executable"):
            prepare_desktop_update(bridge, "request", tmp_path)
    assert bridge.pending_update is None


class _LoopApp:
    def __init__(self, events, code=0, error=None):
        self.events, self.code, self.error = events, code, error

    def exec(self):
        self.events.append("exec")
        if self.error:
            raise self.error
        return self.code


def _window(events, candidate):
    return SimpleNamespace(
        bridge=SimpleNamespace(pending_update=candidate),
        show=lambda: events.append("show"),
        close=lambda: events.append("close"),
    )


def test_event_loop_runs_staged_setup_only_after_window_and_lock_are_closed(tmp_path, monkeypatch):
    """The real desktop tail: what the owner's Install & restart ends with."""
    monkeypatch.setattr(updates.sys, "platform", "win32")
    payload = _payload()
    with _feed(_release(NEWER, payload), payload, []) as client:
        candidate = updates.stage_installer(updates.get_latest(client), tmp_path, client)
    events = []
    monkeypatch.setattr(
        updates.subprocess, "Popen",
        lambda args, **kw: events.append(("launch", args[1:])),
    )
    code = run_desktop(
        _LoopApp(events, code=7),
        lambda: _window(events, candidate),
        SimpleNamespace(close=lambda: events.append("release_lock")),
        adopt=lambda window: events.append("adopt"),
    )
    assert code == 7
    assert events == ["adopt", "show", "exec", "close", "release_lock",
                      ("launch", ["/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"])]


def test_event_loop_ending_normally_starts_no_setup(monkeypatch):
    events = []
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("Closing the window is not an update"),
    )
    code = run_desktop(
        _LoopApp(events), lambda: _window(events, None),
        SimpleNamespace(close=lambda: events.append("release_lock")),
    )
    assert code == 0
    assert events == ["show", "exec", "close", "release_lock"]


def test_event_loop_error_still_releases_the_lock(monkeypatch):
    events = []
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("A crash is not an update"),
    )
    with pytest.raises(RuntimeError, match="loop failed"):
        run_desktop(
            _LoopApp(events, error=RuntimeError("loop failed")), lambda: _window(events, None),
            SimpleNamespace(close=lambda: events.append("release_lock")),
        )
    assert events == ["show", "exec", "close", "release_lock"]


def test_window_that_cannot_be_built_still_releases_the_lock(monkeypatch):
    events = []
    monkeypatch.setattr(
        updates, "launch_installer",
        lambda *args, **kwargs: pytest.fail("No window, no update"),
    )
    def broken():
        raise RuntimeError("no window")
    with pytest.raises(RuntimeError, match="no window"):
        run_desktop(
            _LoopApp(events), broken,
            SimpleNamespace(close=lambda: events.append("release_lock")),
        )
    assert events == ["release_lock"]


def test_desktop_launch_runs_the_update_tail():
    """launch() needs Qt WebEngine and cannot run here; make sure it still ends through run_desktop.

    Before this check, the staged Setup could be recorded and the window closed
    with nothing left to start Setup, so Install & restart would only quit STAR.
    """
    import inspect
    source = inspect.getsource(react_shell.launch)
    assert "run_desktop(app, make_shell, instance" in source
    # Pull request 126's session-end and quit hooks must stay wired to the shell.
    assert "app.commitDataRequest.connect" in source and "app.aboutToQuit.connect" in source
