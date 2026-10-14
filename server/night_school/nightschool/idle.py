"""Polite scheduling: night school works only while nobody else uses the brain.

The brain is a llama.cpp router. `GET /v1/models` lists the loaded models and `GET /slots?model=<id>` lists each
model's slots with `is_processing` and `id_task` (the number of the last request the slot served). Somebody else is
using the brain when a slot is processing, or when a slot's `id_task` changed since the last look, and the change
is not night school's own request (night school only ever uses one slot, never slot 0).

Limits, stated plainly: activity is sampled (every `poll_s` seconds while waiting, every `watch_s` seconds during a
request); a request from somebody else that is pinned to night school's own slot while night school is generating
waits in the server's queue until night school's request ends and cannot be seen before that.
"""
from __future__ import annotations

import json
from pathlib import Path
import time
import urllib.error
import urllib.request

HELPERS = ("embed", "rerank")       # models the knowledge service calls for night school's own searches
LOCK_STALE_S = 1200


class BrainUnreachable(OSError):
    pass


def read_key(key_file: str) -> str:
    """The first key in the file, in memory only. Never printed or logged."""
    try:
        for line in Path(key_file).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.strip().startswith("#"):
                return line.strip()
    except OSError:
        pass
    return ""


class BrainWatch:
    """Reads the brain's slot table. `fetch(path) -> parsed JSON` exists for tests."""

    def __init__(self, url: str, key: str = "", fetch=None, timeout: float = 6.0):
        self._url, self._key, self._timeout = url.rstrip("/"), key, timeout
        self._fetch = fetch or self._http

    def _http(self, path: str):
        request = urllib.request.Request(self._url + path)
        if self._key:
            request.add_header("Authorization", "Bearer " + self._key)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as reply:
                return json.loads(reply.read(4 * 1024 * 1024).decode("utf-8", "replace"))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise BrainUnreachable(type(exc).__name__) from None      # the text may hold the address

    def models(self) -> dict[str, list[str]]:
        """{loaded model id: its other names}."""
        data = self._fetch("/v1/models")
        found = {}
        for row in (data.get("data") or []) if isinstance(data, dict) else []:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            status = row.get("status")
            if isinstance(status, dict) and status.get("value") not in (None, "loaded"):
                continue
            found[row["id"]] = [a for a in (row.get("aliases") or []) if isinstance(a, str)]
        return found

    def snapshot(self) -> dict[tuple[str, int], tuple[bool, int]]:
        """{(model, slot id): (is processing, last task number)} for every loaded model."""
        table = {}
        for model in self.models():
            slots = self._fetch("/slots?model=" + model)
            if not isinstance(slots, list):
                raise BrainUnreachable("slots")
            for slot in slots:
                if isinstance(slot, dict) and type(slot.get("id")) is int:
                    task = slot.get("id_task")
                    table[(model, slot["id"])] = (bool(slot.get("is_processing")), task if type(task) is int else -1)
        return table

    def slot_for(self, wanted: int) -> dict[str, int]:
        """{model or alias: the slot night school may use}: `wanted` when the model has it, else its highest slot.
        A model with a single slot maps to 0, which callers must refuse."""
        names = self.models()
        highest: dict[str, int] = {}
        for (model, slot) in self.snapshot():
            highest[model] = max(highest.get(model, 0), slot)
        chosen = {}
        for model, top in highest.items():
            slot = wanted if 0 < wanted <= top else top
            for name in (model, *names.get(model, [])):
                chosen[name] = slot
        return chosen


def activity(before: dict, after: dict, *, own_slot: int | None = None, skip_helpers: bool = False) -> list[str]:
    """Signs of another client between two snapshots, as "model/slot" strings. With `own_slot` set, that slot of
    every model is night school's own and is ignored (as are the helper models when `skip_helpers`)."""
    seen = []
    for (model, slot), (busy, task) in after.items():
        if own_slot is not None and slot == own_slot:
            continue
        if skip_helpers and any(word in model for word in HELPERS):
            continue
        old = before.get((model, slot))
        if busy or (old is not None and old[1] != task):
            seen.append(f"{model}/{slot}")
    return seen


class IdleGate:
    """`wait()` returns only after `idle_s` seconds with no sign of another client, no HOLD file and no quiet lock."""

    def __init__(self, settings, watch: BrainWatch, *, log=print, clock=time.monotonic, sleep=time.sleep):
        self.settings, self.watch, self._log, self._clock, self._sleep = settings, watch, log, clock, sleep
        self._last: dict | None = None          # the newest snapshot
        self._quiet_since: float | None = None  # start of the current quiet period
        self._said = ""
        self._said_at = -1e9

    def _say(self, text: str, every: float = 900.0) -> None:
        now = self._clock()
        if text != self._said or now - self._said_at >= every:
            self._log(text)
            self._said, self._said_at = text, now

    def lock_held(self) -> bool:
        try:
            newest = Path(self.settings.lock_dir).stat().st_mtime
        except OSError:
            return False
        return time.time() - newest < LOCK_STALE_S          # an older lock is stale and ignored, never removed

    def look(self) -> str:
        """One look. "" when nothing speaks against working now, else the reason. Updates the quiet timer."""
        now = self._clock()
        if Path(self.settings.hold_file).exists():
            self._quiet_since = None
            return "HOLD file present, paused"
        if self.lock_held():
            self._quiet_since = None
            return "quiet lock held, waiting"
        try:
            table = self.watch.snapshot()
        except OSError:
            self._last, self._quiet_since = None, None
            return "brain not reachable, waiting"
        signs = activity(self._last if self._last is not None else {}, table)
        self._last = table
        if signs:
            self._quiet_since = None
            return "brain busy, waiting"
        if self._quiet_since is None:
            self._quiet_since = now
        if now - self._quiet_since < self.settings.idle_s:
            return f"brain quiet, waiting until it has been quiet for {int(self.settings.idle_s)} s"
        return ""

    def wait(self, stop=lambda: False) -> bool:
        """Block until the brain has been idle long enough. False when asked to stop."""
        while not stop():
            reason = self.look()
            if not reason:
                self._say("brain idle, working")
                return True
            self._say(reason)
            self._sleep(self.settings.poll_s)
        return False

    def intruder(self, own_slot: int) -> str:
        """During night school's own request: "" or the sign of another client. Resets the quiet timer on a sign."""
        if Path(self.settings.hold_file).exists():
            return "HOLD file"
        if self.lock_held():
            return "quiet lock"
        try:
            table = self.watch.snapshot()
        except OSError:
            return ""            # one failed look does not stop a running request; the next look decides
        signs = activity(self._last if self._last is not None else table, table, own_slot=own_slot, skip_helpers=True)
        self._last = table
        if signs:
            self._quiet_since = None
            return "another client on " + ", ".join(sorted(signs)[:4])
        return ""

    def own_work_done(self) -> None:
        """Night school's own request ended: take a fresh snapshot so its task numbers are not read as a stranger's."""
        try:
            self._last = self.watch.snapshot()
        except OSError:
            self._last, self._quiet_since = None, None
