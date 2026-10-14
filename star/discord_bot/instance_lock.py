"""One Discord bot per owner: a lock file in the owner's ``~/.star`` folder.

Two bots with the same token would both answer every message. The bot takes this lock when
it runs (a terminal, STAR Desktop's supervisor or Task Scheduler), so a second start exits
at once with a clear message instead of answering twice. The lock is released by the
operating system when the process ends, even after a crash, so it never goes stale.
``probe`` lets STAR Desktop see whether a bot is running somewhere else.
"""
from __future__ import annotations

import os
from pathlib import Path

LOCK_FILE = "discord-bot.lock"
# Windows locks are mandatory for the locked bytes, so lock one byte far away from the PID text.
_LOCK_OFFSET = 4096


def _try_lock(handle) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(_LOCK_OFFSET)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(_LOCK_OFFSET)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


class InstanceLock:
    """``acquire()`` is True for the one process that may run the bot."""

    def __init__(self, folder: Path, name: str = LOCK_FILE):
        self.path = Path(folder) / name
        self._handle = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        if not _try_lock(handle):
            handle.close()
            return False
        handle.seek(0)
        handle.truncate(0)
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        self._handle = handle
        return True

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            _unlock(handle)
            handle.close()


def held_elsewhere(folder: Path) -> bool:
    """True when a running bot holds the lock (checked by trying to take it and letting go)."""
    path = Path(folder) / LOCK_FILE
    if not path.is_file():
        return False
    try:
        handle = open(path, "a+b")
    except OSError:
        return False
    try:
        if _try_lock(handle):
            _unlock(handle)
            return False
        return True
    finally:
        handle.close()
