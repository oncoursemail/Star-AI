"""Good-neighbour rules for background jobs on the shared CPU server.

The "quiet please" lock (default `/opt/star/lock`) pauses work between requests,
documents and batches. Its most recent directory/owner timestamp is used; a lock
15 minutes old is stale and ignored, but never removed by a job.
SIGTERM / SIGINT request a clean stop after the current unit of work.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import sys
import time

LOCK_DIR = Path(os.environ.get("STAR_LOCK_DIR", "/opt/star/lock"))
STALE_SECONDS = float(os.environ.get("STAR_LOCK_STALE_S", "900"))


def lock_held(lock_dir: Path | None = None, stale_seconds: float | None = None, *,
              clock=None) -> bool:
    lock_dir = LOCK_DIR if lock_dir is None else lock_dir
    stale = STALE_SECONDS if stale_seconds is None else stale_seconds
    try:
        newest = lock_dir.stat().st_mtime
    except OSError:
        return False
    try:
        newest = max(newest, (lock_dir / "owner").stat().st_mtime)
    except OSError:
        pass
    current = time.time() if clock is None else clock()
    return current - newest < stale


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
                      sleep=None, *, max_wait: float | None = None, clock=None, held=None) -> float | None:
    """Wait at a work boundary. Return seconds waited, or None if max_wait expires.

    Log exactly one pause and one resume per uninterrupted wait. A stopped or timed-out
    wait does not log a resume. Inject clock/sleep/held to test without real delays.
    """
    if poll <= 0:
        raise ValueError("poll must be positive")
    sleep = time.sleep if sleep is None else sleep
    is_locked = held if held is not None else lambda: lock_held(lock_dir, clock=clock)
    waited = 0.0
    paused = False
    while is_locked() and not stop():
        if not paused:
            log("quiet: server lock present, pausing")
            paused = True
        if max_wait is not None and waited >= max_wait:
            log("quiet: maximum wait reached while locked")
            return None
        interval = poll if max_wait is None else min(poll, max_wait - waited)
        sleep(interval)
        waited += interval
    if paused and not stop():
        log(f"quiet: continuing after {waited:.0f}s")
    return waited


def planner_pacer(job: str, *, holder: str = "knowledge", log=print, stop=lambda: False):
    """A lease + pacing helper from STAR's resource planner for a long knowledge batch job ("reindex" class), or None.

    Only when $STAR_PLANNER_URL is set (the refresh unit sets it to the planner on this machine). The planner admits
    the job, slows it to a quarter duty while chat is active and pauses it for timing windows. Unreachable planner:
    the Pacer answers "fallback" and the job runs exactly as before (quiet lock + its own --duty)."""
    url = os.environ.get("STAR_PLANNER_URL", "")
    if not url or url.lower() in ("off", "0", "none"):
        return None
    try:
        from . import _planner_client as client_module      # copied next to starkb by deploy.sh
    except ImportError:
        try:
            from star import planner_client as client_module  # a repository checkout
        except ImportError:
            return None
    client = client_module.PlannerClient(url, key_file=os.environ.get("STAR_BRAIN_KEY_FILE",
                                                                      "/opt/star/secrets/api_keys"), timeout=2.0)
    return client_module.Pacer(client, "reindex", holder, job, log=log, stop=stop)


if __name__ == "__main__":
    wait_while_locked(log=lambda message: print(message, file=sys.stderr))
