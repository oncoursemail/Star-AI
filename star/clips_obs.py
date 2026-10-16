"""Opt-in, local-only OBS replay bridge for STAR Clips.

This controls the owner's already-running OBS Studio through obs-websocket v5.
No games are hooked, no microphone is enabled, and no data is uploaded by STAR.
Only explicit desktop UI actions can call this class. The OBS scene and replay
settings (including audio) are configured by the owner in OBS Studio.

Do not expose these actions in the model tool registry: model output is not
permission to record a screen or send a clip.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

CLIP_ACTIONS = frozenset({
    "clipStatus", "clipConnect", "clipStartBuffer", "clipSaveReplay",
    "clipStopBuffer", "clipDisconnect",
})


def _obs_client(**kwargs):
    try:
        import obsws_python
    except ImportError as exc:
        raise RuntimeError(
            "OBS control needs the optional obsws-python package. "
            "Install STAR's Windows desktop dependencies, then try again."
        ) from exc
    return obsws_python.ReqClient(**kwargs)


class ClipService:
    """Connection is memory-only; the OBS password is not saved to a STAR file."""

    def __init__(self, client_factory: Callable[..., Any] | None = None):
        self._client_factory = client_factory or _obs_client
        self._client: Any | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _confirm(body: dict):
        if body.get("confirm") is not True:
            raise PermissionError("Recording controls require an explicit user action.")

    def _status(self) -> dict:
        if self._client is None:
            return {"connected": False, "buffer_active": False,
                    "message": "Connect to OBS Studio to use its replay buffer."}
        try:
            state = self._client.get_replay_buffer_status()
            return {"connected": True, "buffer_active": bool(state.output_active),
                    "message": "OBS replay buffer is running." if state.output_active
                    else "Connected to OBS. Replay buffer is stopped."}
        except Exception as exc:
            # OBS can be connected while its Replay Buffer feature is disabled.
            # Show an actionable status, but never forward the raw exception text.
            detail = str(exc).lower()
            if "replay" in detail and ("not available" in detail or "not enabled" in detail):
                return {"connected": True, "buffer_active": False,
                        "message": "Enable Replay Buffer in OBS → Settings → Output."}
            # OBS may close or revoke its WebSocket while STAR is open.
            self._client = None
            return {"connected": False, "buffer_active": False,
                    "message": "OBS connection was lost. Reconnect from STAR Clips."}

    def handle(self, action: str, body: dict) -> dict:
        if action not in CLIP_ACTIONS:
            raise PermissionError("Unsupported STAR Clips action.")
        if not isinstance(body, dict):
            raise ValueError("Invalid STAR Clips request.")
        with self._lock:
            if action == "clipStatus":
                return self._status()
            if action == "clipConnect":
                self._confirm(body)
                password = body.get("password")
                if not isinstance(password, str) or not 1 <= len(password) <= 256:
                    raise ValueError(
                        "Enter the OBS WebSocket password from Tools → WebSocket Server Settings."
                    )
                try:
                    # Never accept model-selected hosts, remote IPs, URLs or custom ports.
                    client = self._client_factory(
                        host="127.0.0.1", port=4455, password=password, timeout=3
                    )
                    client.get_version()
                except Exception:
                    # Do not echo third-party errors; they may contain authentication data.
                    raise ConnectionError(
                        "Could not connect to local OBS WebSocket on port 4455. "
                        "Open OBS → Tools → WebSocket Server Settings, enable "
                        "authentication and check the password."
                    ) from None
                self._client = client
                return self._status()
            if action == "clipDisconnect":
                self._confirm(body)
                self._client = None  # Leave any existing OBS recording untouched.
                return self._status()

            self._confirm(body)
            if self._client is None:
                raise RuntimeError("Connect to OBS Studio first.")
            state = self._status()
            if not state["connected"]:
                raise ConnectionError("OBS connection lost. Reconnect.")
            running = state["buffer_active"]
            # An expected user-state error must not be disguised as an OBS RPC failure.
            if action == "clipSaveReplay" and not running:
                raise RuntimeError("Start the OBS replay buffer before saving a clip.")
            try:
                if action == "clipStartBuffer":
                    if not running:
                        self._client.start_replay_buffer()
                    return {"connected": True, "buffer_active": True,
                            "message": "OBS accepted the replay-buffer start request."}
                if action == "clipStopBuffer":
                    if running:
                        self._client.stop_replay_buffer()
                    return {"connected": True, "buffer_active": False,
                            "message": "OBS accepted the replay-buffer stop request."}
                # A successful request is not proof that the file was written.
                self._client.save_replay_buffer()
                return {"connected": True, "buffer_active": True, "save_requested": True,
                        "message": "Save requested. Verify the video in OBS's recording folder."}
            except Exception:
                raise RuntimeError(
                    "OBS could not complete the replay action. Check OBS's log and replay settings."
                ) from None
