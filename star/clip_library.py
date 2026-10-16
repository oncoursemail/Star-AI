"""Read-only external game clip folder browser for STAR Clips.

Medal, Outplayed, OBS, RePlays, ShadowPlay and other recorders can all save
ordinary video files. The owner explicitly chooses ONE folder through Qt;
STAR reads bounded video metadata only and neither copies nor modifies media.

No agent-facing tools, shell commands, network calls or automatic scanning.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import threading

VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".webm", ".avi"})
MAX_ENTRIES = 1500
MAX_ITEMS = 120
MAX_DIRECTORIES = 36
MAX_DEPTH = 2
MAX_FILE_BYTES = 64 * (1024 ** 3)
_ID = re.compile(r"^[0-9a-f]{20}$")


class ClipLibrary:
    """Ephemeral scope: only directories chosen by the human via Qt are visited."""

    def __init__(self):
        self.root: Path | None = None
        self._index: dict[str, Path] = {}
        self._lock = threading.RLock()

    def choose(self, folder: Path) -> dict:
        # The Qt file chooser supplies the folder; no web/model-provided paths.
        folder = Path(folder).expanduser()
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("Choose a real local recording folder, not a symlink.")
        root = folder.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("The selected recording folder is unavailable.")
        with self._lock:
            self.root = root
            self._index.clear()
            return self.list_clips()

    def clear(self) -> dict:
        with self._lock:
            self.root = None
            self._index.clear()
            return {"selected": False, "clips": [], "message": "Clip folder disconnected."}

    def list_clips(self) -> dict:
        with self._lock:
            if self.root is None:
                return {"selected": False, "clips": [],
                        "message": "Choose a local recording folder to browse clips."}
            root = self.root
            if not root.is_dir():
                self._index.clear()
                return {"selected": True, "folder": root.name, "clips": [],
                        "message": "The selected folder is no longer available."}
            queue = deque([(root, 0)])
            scanned = 0
            directories = 0
            truncated = False
            candidates: list[tuple[int, dict, Path]] = []
            while queue and scanned < MAX_ENTRIES and directories < MAX_DIRECTORIES:
                current, depth = queue.popleft()
                directories += 1
                if current.is_symlink():
                    continue
                try:
                    with os.scandir(current) as entries:
                        for entry in entries:
                            scanned += 1
                            if scanned > MAX_ENTRIES:
                                truncated = True
                                break
                            # Don't traverse symlinks, even if a folder has been swapped.
                            if entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False) and depth < MAX_DEPTH:
                                if not entry.name.startswith("."):
                                    queue.append((Path(entry.path), depth + 1))
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            if Path(entry.name).suffix.lower() not in VIDEO_EXTENSIONS:
                                continue
                            info = entry.stat(follow_symlinks=False)
                            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE_BYTES:
                                continue
                            path = Path(entry.path)
                            relative = path.relative_to(root).as_posix()
                            file_id = sha256(relative.encode("utf-8", errors="replace")).hexdigest()[:20]
                            item = {"id": file_id, "name": entry.name, "relative": relative,
                                    "bytes": info.st_size, "modified": datetime.fromtimestamp(
                                        info.st_mtime, tz=timezone.utc).isoformat()}
                            candidates.append((info.st_mtime_ns, item, path))
                except (OSError, PermissionError):
                    continue
            if queue or scanned > MAX_ENTRIES or directories >= MAX_DIRECTORIES:
                truncated = True
            candidates.sort(key=lambda row: (-row[0], row[1]["relative"]))
            shown = candidates[:MAX_ITEMS]
            if len(candidates) > MAX_ITEMS:
                truncated = True
            self._index = {item["id"]: path for _, item, path in shown}
            return {"selected": True, "folder": root.name,
                    "clips": [item for _, item, _ in shown],
                    "truncated": truncated, "scanned_entries": min(scanned, MAX_ENTRIES),
                    "message": ("Partial clip list. Choose a more specific folder."
                                if truncated else "Read-only local clip list.")}

    def allowed_clip(self, file_id: str) -> Path:
        """Recheck a previously listed clip; never accept a caller-supplied path."""
        with self._lock:
            if not isinstance(file_id, str) or not _ID.fullmatch(file_id):
                raise ValueError("Choose a clip from the current library list.")
            path = self._index.get(file_id)
            root = self.root
            if path is None or root is None:
                raise PermissionError("This clip was not selected in the current folder.")
            # Verify every path component is still an ordinary directory.
            parts = path.relative_to(root).parts
            current = root
            for component in parts[:-1]:
                current = current / component
                if current.is_symlink() or not current.is_dir():
                    raise PermissionError("This recording folder contains a changed link.")
            if path.is_symlink() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                raise PermissionError("Only listed local video files can be opened.")
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise PermissionError("Recording file moved outside the approved folder.")
            return resolved
