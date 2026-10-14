"""Crash-safe small-file writes and recovery from a damaged JSON file.

`atomic_write_text` writes the new content to a unique temporary file in the same folder, flushes
it to disk and then swaps it into place with `os.replace`, so a reader (or a crash, power cut or
full disk) sees either the old file or the new one, never half of it. The unique name avoids the
symlink and collision problems of a fixed `.tmp` name.

`move_aside` renames a file that cannot be read into `<name>.corrupt-<UTC time>` so the owner can
inspect or restore it, instead of the program refusing to start or silently overwriting it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time


def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> None:
    """Replace `path` with `text` in one step. The parent folder is created if needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode(encoding)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _replace(source: Path, target: Path, attempts: int = 10) -> None:
    """os.replace, retried briefly when Windows refuses because another handle has `target` open.

    Python opens files on Windows without FILE_SHARE_DELETE, so while another STAR thread or process is
    reading the old file the swap fails with PermissionError for a moment. The old in-place write did not.
    """
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.02 * (attempt + 1))


def move_aside(path: Path | str, *, now: datetime | None = None) -> Path | None:
    """Rename a damaged file to `<name>.corrupt-<UTC time>`; the new path, or None if it failed."""
    source = Path(path)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    for attempt in range(100):
        suffix = f".corrupt-{stamp}" + (f"-{attempt}" if attempt else "")
        backup = source.with_name(source.name + suffix)
        if backup.exists():
            continue
        try:
            os.replace(source, backup)
        except OSError:
            return None
        return backup
    return None
