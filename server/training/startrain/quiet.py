"""Good-neighbour rules for this job on the shared CPU server.

* The quiet lock: while the directory `/opt/star/lock` exists somebody is taking a timing measurement; a lock
  whose newest timestamp is older than the stale limit (20 minutes) is ignored and never removed here.
* A PAUSE file in the training home pauses the job without stopping the service (`touch PAUSE` / `rm PAUSE`).
* An optional UTC window ("04:00-10:00") confines the job to a nightly quiet period.
* SIGTERM / SIGINT only set a flag; the job stops between steps and exits 0.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import time


def lock_held(lock_dir: str | Path, stale_seconds: float = 1200.0, now: float | None = None) -> bool:
    lock_dir = Path(lock_dir)
    try:
        newest = lock_dir.stat().st_mtime
    except OSError:
        return False
    try:
        newest = max(newest, (lock_dir / "owner").stat().st_mtime)
    except OSError:
        pass
    return (time.time() if now is None else now) - newest < stale_seconds


def parse_window(spec: str) -> tuple[int, int] | None:
    """"04:00-10:00" -> (minutes since midnight start, end). Empty -> None (always)."""
    spec = (spec or "").strip()
    if not spec:
        return None
    try:
        left, right = spec.split("-")
        h1, m1 = (int(x) for x in left.split(":"))
        h2, m2 = (int(x) for x in right.split(":"))
    except ValueError as exc:
        raise ValueError(f"window must look like 04:00-10:00, got {spec!r}") from exc
    return h1 * 60 + m1, h2 * 60 + m2


def in_window(spec: str, now: datetime | None = None) -> bool:
    window = parse_window(spec)
    if window is None:
        return True
    now = now or datetime.now(timezone.utc)
    minute = now.hour * 60 + now.minute
    start, end = window
    if start <= end:
        return start <= minute < end
    return minute >= start or minute < end      # a window that crosses midnight


class Stopper:
    """`stopper()` is True after SIGTERM or SIGINT. Install once, in the main thread."""

    def __init__(self, install: bool = True):
        self.requested = False
        if install:
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    signal.signal(sig, self._on_signal)
                except (ValueError, OSError):
                    pass

    def _on_signal(self, *_args) -> None:
        self.requested = True

    def __call__(self) -> bool:
        return self.requested


def pause_reason(settings, brain=None, now: datetime | None = None) -> str:
    """"" when the job may send a request now, else the reason: pause-file, lock, window or interactive."""
    if Path(settings.pause_file).exists():
        return "pause-file"
    if lock_held(settings.lock_dir, settings.lock_stale_s):
        return "lock"
    if not in_window(settings.window_utc, now):
        return "window"
    if brain is not None and brain.others_active():
        return "interactive"
    return ""


def wait_until_clear(settings, brain, stop, log, sleep=time.sleep) -> dict[str, float]:
    """Block until the job may send a request. Returns the seconds waited per reason.

    After any activity by someone else the job also waits `idle_s` quiet seconds, so a chat that sends one
    request after another is not interrupted between its turns.
    """
    waited: dict[str, float] = {}
    last_reason = ""
    while not stop():
        reason = pause_reason(settings, brain)
        if not reason and brain is not None and settings.idle_s > 0                 and brain.seconds_since_other_activity() < settings.idle_s:
            reason = "interactive"
        if not reason:
            if last_reason:
                log("quiet: continuing after " + ", ".join(f"{k} {v:.0f}s" for k, v in waited.items()))
            return waited
        if reason != last_reason:
            log(f"quiet: pausing ({reason})")
            last_reason = reason
        step = min(settings.poll_s * (4 if reason in ("window", "pause-file") else 1), 30.0)
        sleep(step)
        waited[reason] = waited.get(reason, 0.0) + step
    return waited


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
