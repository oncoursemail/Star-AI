"""Offline contract tests. A fake OBS client is not evidence of real capture."""
from __future__ import annotations

import pytest
from star.clips_obs import ClipService, CLIP_ACTIONS


class FakeReply:
    def __init__(self, active=False):
        self.output_active = active


class FakeObs:
    def __init__(self):
        self.running = False
        self.saved = 0
        self.started = 0
        self.stopped = 0

    def get_version(self):
        return object()

    def get_replay_buffer_status(self):
        return FakeReply(self.running)

    def start_replay_buffer(self):
        self.started += 1
        self.running = True

    def stop_replay_buffer(self):
        self.stopped += 1
        self.running = False

    def save_replay_buffer(self):
        self.saved += 1


def make_service():
    fake = FakeObs()
    params = []
    def factory(**kwargs):
        params.append(kwargs)
        return fake
    return ClipService(client_factory=factory), fake, params


def test_no_recording_without_explicit_consent():
    service, fake, _ = make_service()
    assert service.handle("clipStatus", {})["connected"] is False
    with pytest.raises(PermissionError):
        service.handle("clipConnect", {"password": "a secret"})
    with pytest.raises(PermissionError):
        service.handle("clipStartBuffer", {})
    assert fake.started == 0


def test_local_only_connection_and_ephemeral_password():
    service, _, params = make_service()
    result = service.handle("clipConnect", {"confirm": True, "password": "secret"})
    assert result["connected"] is True
    assert params == [{"host": "127.0.0.1", "port": 4455,
                       "password": "secret", "timeout": 3}]
    assert "secret" not in str(result)
    assert not hasattr(service, "password")


def test_replay_lifecycle_and_truthful_save_ack():
    service, fake, _ = make_service()
    service.handle("clipConnect", {"confirm": True, "password": "test"})
    with pytest.raises(RuntimeError, match="Start"):
        service.handle("clipSaveReplay", {"confirm": True})
    assert service.handle("clipStartBuffer", {"confirm": True})["buffer_active"]
    service.handle("clipStartBuffer", {"confirm": True})
    assert fake.started == 1  # idempotent
    response = service.handle("clipSaveReplay", {"confirm": True})
    assert response["save_requested"]
    assert "Verify" in response["message"]
    assert fake.saved == 1
    assert service.handle("clipStopBuffer", {"confirm": True})["buffer_active"] is False
    service.handle("clipStopBuffer", {"confirm": True})
    assert fake.stopped == 1


def test_disconnect_never_stops_obs():
    service, fake, _ = make_service()
    service.handle("clipConnect", {"confirm": True, "password": "test"})
    service.handle("clipStartBuffer", {"confirm": True})
    result = service.handle("clipDisconnect", {"confirm": True})
    assert result["connected"] is False
    assert fake.stopped == 0 and fake.running


def test_connection_errors_do_not_echo_password():
    def broken(**kwargs):
        raise ValueError("bad password: " + kwargs["password"])
    service = ClipService(client_factory=broken)
    with pytest.raises(ConnectionError) as exc:
        service.handle("clipConnect", {"confirm": True, "password": "supersecret"})
    assert "supersecret" not in str(exc.value)


def test_failed_status_drops_stale_connection():
    service, fake, _ = make_service()
    service.handle("clipConnect", {"confirm": True, "password": "test"})
    fake.get_replay_buffer_status = lambda: (_ for _ in ()).throw(OSError("closed"))
    result = service.handle("clipStatus", {})
    assert result["connected"] is False
    assert not result["buffer_active"]


def test_replay_unavailable_does_not_lose_valid_obs_connection():
    service, fake, _ = make_service()
    service.handle("clipConnect", {"confirm": True, "password": "test"})
    fake.get_replay_buffer_status = lambda: (_ for _ in ()).throw(
        RuntimeError("Replay buffer is not available.")
    )
    report = service.handle("clipStatus", {})
    assert report["connected"] is True
    assert report["buffer_active"] is False
    assert "Enable Replay Buffer" in report["message"]


def test_invalid_requests_and_unprivileged_actions_are_rejected():
    service, _, _ = make_service()
    assert len(CLIP_ACTIONS) == 6
    with pytest.raises(PermissionError):
        service.handle("clipDeleteAllFiles", {"confirm": True})
    with pytest.raises(ValueError):
        service.handle("clipConnect", {"confirm": True, "password": ""})


def test_missing_obs_package_says_so_instead_of_a_connection_error(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_obsws(name, *args, **kwargs):
        if name == "obsws_python":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_obsws)
    service = ClipService()
    with pytest.raises(RuntimeError, match="obsws-python"):
        service.handle("clipConnect", {"confirm": True, "password": "pw"})
    assert service.handle("clipStatus", {})["connected"] is False
