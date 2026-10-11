"""Offline end-to-end updater fixtures; no GitHub, installer execution, or Qt needed."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from star import updates
from star.react_shell import finish_desktop_update


def _payload() -> bytes:
    return b"MZ" + b"U" * (updates.MIN_INSTALLER_BYTES + 64)


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
    ("0.9.1", True), ("0.9.0", False), ("0.8.9", False),
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
    with _feed(_release("0.9.1", payload), payload, requests) as client:
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
    with _feed(_release("0.9.1", payload, "a" * 64), payload, requests) as client:
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
