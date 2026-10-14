"""A tiny status file the running bot keeps current, so STAR Desktop can show "connected".

``~/.star/discord-status.json`` holds only: the bot's process id, a state word, a timestamp and
two counters. No token, no Discord IDs, no message text. Writes are best effort and atomic.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

STATUS_FILE = "discord-status.json"
STATES = frozenset({"starting", "connected", "reconnecting", "stopped"})
# A "connected" report older than this no longer counts (the heartbeat runs every 30 s).
FRESH_SECONDS = 120.0


class StatusReporter:
    def __init__(self, folder: Path, *, pid: int | None = None, clock=time.time):
        self.path = Path(folder) / STATUS_FILE
        self.pid = os.getpid() if pid is None else pid
        self._clock = clock

    def write(self, state: str, **numbers: int | float) -> None:
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        payload = {"pid": self.pid, "state": state, "updated_at": round(self._clock(), 3)}
        payload.update({key: value for key, value in numbers.items()
                        if key in {"guilds", "latency_ms"} and isinstance(value, (int, float))})
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(self.path.name + f".{self.pid}.tmp")
            temp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError:
            pass


def read_status(folder: Path) -> dict | None:
    path = Path(folder) / STATUS_FILE
    try:
        if path.stat().st_size > 4096:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("state") not in STATES:
        return None
    if not isinstance(data.get("pid"), int) or not isinstance(data.get("updated_at"), (int, float)):
        return None
    return data
