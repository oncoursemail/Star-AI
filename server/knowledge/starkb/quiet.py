"""Good-neighbour rules for background jobs on the shared CPU server.

* The "quiet please" lock: while the directory `/opt/star/lock` exists somebody is taking a timing
  measurement, and every long-running job must wait before its next request or batch. A lock whose
  newest timestamp is older than `STAR_LOCK_STALE_S` (default 20 minutes; holders may keep it for
  10) is treated as left behind and ignored. It is never removed here.
* A clean stop: SIGTERM / SIGINT only set a flag. The job finishes the request it is in, commits,
  and exits 0, so `systemctl stop` never loses work.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import time

LOCK_DIR = Path(os.environ.get("STAR_LOCK_DIR", "/opt/star/lock"))
STALE_SECONDS = float(os.environ.get("STAR_LOCK_STALE_S", "1200"))


def lock_held(lock_dir: Path | None = None, stale_seconds: float | None = None) -> bool:
    lock_dir = lock_dir or LOCK_DIR
    stale = STALE_SECONDS if stale_seconds is None else stale_seconds
    try:
        newest = lock_dir.stat().st_mtime
    except OSError:
        return False
    try:
        newest = max(newest, (lock_dir / "owner").stat().st_mtime)
    except OSError:
        pass
    return time.time() - newest < stale


class Stopper:
    """`stop()` is True after SIGTERM or SIGINT. Install once, in the main thread."""

    def __init__(self, install: bool = True):
        self.requested = False
        if install:
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    signal.signal(sig, self._on_signal)
                except (ValueError, OSError):   # not the main thread, or not supported
                    pass

    def _on_signal(self, *_args) -> None:
        self.requested = True

    def __call__(self) -> bool:
        return self.requested


def wait_while_locked(log=print, stop=lambda: False, poll: float = 5.0, lock_dir: Path | None = None,
                      sleep=time.sleep) -> float:
    """Block while the server lock is held. Returns the seconds waited (0.0 when it was free)."""
    waited = 0.0
    while lock_held(lock_dir) and not stop():
        if not waited:
            log("quiet: server lock present, pausing")
        sleep(poll)
        waited += poll
    if waited:
        log(f"quiet: continuing after {waited:.0f}s")
    return waited
