"""Bounded SteelSeries GG Moments developer-event bridge (opt-in only).

Only locally installed SteelSeries Engine's discovery file is used. Events are
restricted to a human-confirmed STAR_ prefixed *owner-created* game name.
This is an integration for the owner's game development work; it does NOT
control third-party titles, the Outplayed app, or the Medal recorder.

Official protocol:
https://github.com/SteelSeries/gamesense-sdk/blob/master/doc/api/sending-moments-events.md
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

MAX_PROPS = 4096
GAME_ID = re.compile(r"^STAR_[A-Z][A-Z0-9_]{1,31}$")
KEY = "star_highlight"
_RULES = "register_autoclip_rules"
_TRIGGER = "autoclip"


def default_coreprops() -> Path:
    program_data = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
    return Path(program_data) / "SteelSeries" / "SteelSeries Engine 3" / "coreProps.json"


def _local_endpoint(properties: Path) -> str | None:
    """Refuse even a syntactically valid external host in discovery metadata."""
    try:
        if not properties.is_file() or properties.is_symlink() or properties.stat().st_size > MAX_PROPS:
            return None
        payload = json.loads(properties.read_text(encoding="utf-8-sig"))
        raw = payload.get("address") if isinstance(payload, dict) else None
        if not isinstance(raw, str) or not raw.startswith("127.0.0.1:"):
            return None
        port = raw.split(":", 1)[1]
        if not port.isdecimal() or not 1024 <= int(port) <= 65535:
            return None
        return "http://127.0.0.1:" + str(int(port))
    except (ValueError, OSError, UnicodeError):
        return None


def _post(endpoint: str, path: str, payload: dict) -> None:
    """Fixed host and paths only, short timeout; no cookies, tokens or redirects."""
    if not re.fullmatch(r"http://127\.0\.0\.1:\d{4,5}", endpoint):
        raise PermissionError("SteelSeries developer events require a local GG endpoint.")
    if path not in (_RULES, _TRIGGER):
        raise PermissionError("Unsupported GameSense event action.")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = Request(endpoint + "/" + path, data=body,
                      headers={"Content-Type": "application/json"}, method="POST")
    # urllib's default redirect handler may redirect POSTs. Refuse redirection
    # so a compromised local service can't forward event data externally.
    from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    with build_opener(ProxyHandler({}), NoRedirect).open(request, timeout=2.0) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("SteelSeries GG did not accept the event request.")
        response.read(256)


class MomentsEvents:
    """Explicit development-session events, never an automatic game listener."""

    def __init__(self, properties: Path | None = None, poster=None):
        self.properties = properties or default_coreprops()
        self.poster = poster or _post
        self.registered: set[str] = set()

    @staticmethod
    def _approved(body: dict) -> str:
        if body.get("confirm") is not True or body.get("ownsGame") is not True:
            raise PermissionError("Confirm that this is a game you develop and authorize the event.")
        game = body.get("game")
        if not isinstance(game, str) or not GAME_ID.fullmatch(game):
            raise ValueError("Use a STAR_ prefixed development game ID, e.g. STAR_MY_GAME.")
        return game

    def handle(self, action: str, body: dict) -> dict:
        if action == "clipMomentsStatus":
            endpoint = _local_endpoint(self.properties)
            return {"available": bool(endpoint), "registered": sorted(self.registered),
                    "message": ("SteelSeries GG local GameSense endpoint found. Recording is not verified."
                                if endpoint else "SteelSeries GG GameSense local endpoint was not found.")}
        if action not in ("clipMomentsRegister", "clipMomentsTrigger"):
            raise PermissionError("Unsupported Moments integration action.")
        if not isinstance(body, dict):
            raise ValueError("Invalid request.")
        game = self._approved(body)
        endpoint = _local_endpoint(self.properties)
        if endpoint is None:
            raise ConnectionError("SteelSeries GG is not running with a valid loopback GameSense server.")
        if action == "clipMomentsTrigger" and game not in self.registered:
            raise PermissionError("Register this STAR development game event before triggering it.")
        path, payload = (
            (_RULES, {"game": game, "rules": [{"rule_key": KEY,
                                            "label": "STAR highlight", "default_enabled": False}]})
            if action == "clipMomentsRegister"
            else (_TRIGGER, {"game": game, "key": KEY})
        )
        try:
            self.poster(endpoint, path, payload)
        except (PermissionError, ValueError):
            raise
        except Exception:
            # Never expose local endpoint logs or external server bodies in UI.
            raise ConnectionError("SteelSeries GG did not accept the developer event. "
                                  "Check GG and its GameSense/Moments settings.") from None
        if action == "clipMomentsRegister":
            self.registered.add(game)
        return {"accepted": True, "game": game, "event": KEY,
                "message": ("Developer event registered. Enable its rule in SteelSeries GG Moments."
                            if action == "clipMomentsRegister"
                            else "Autoclip event sent to GG. Verify whether a real clip was saved.")}
