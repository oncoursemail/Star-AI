"""Bounded cursors and observed-message receipts over the existing shared log.

BOARD/MESSAGES/ledger remain authoritative. This adds no second message bus,
claim takeover, assistant scheduler or permission to edit another owner's files.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import stat

from .store import SharedBrain, serialize

MAX_LOG_BYTES = 500_000


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _read(root: Path, name: str) -> bytes:
    path = root / name
    for parent in (path, *path.parents):
        if parent == root.parent:
            break
        reparse = (getattr(parent.lstat(), "st_file_attributes", 0)
                   & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)) if parent.exists() else 0
        if reparse or parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Coordination files cannot follow links")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Coordination file left the selected root")
    if not path.is_file():
        return b""
    if path.stat().st_size > MAX_LOG_BYTES:
        raise ValueError("Coordination source exceeds the read budget")
    with path.open("rb") as stream:
        raw = stream.read(MAX_LOG_BYTES + 1)
    if len(raw) > MAX_LOG_BYTES:
        raise ValueError("Coordination source exceeds the read budget")
    raw.decode("utf-8-sig")
    return raw


def snapshot(brain: SharedBrain, collab_root: Path, *, after: str = "", actor: str = "",
             acknowledge: bool = False, budget_chars: int = 6000) -> dict:
    root = collab_root.resolve(strict=True)
    if not brain.workspace.is_relative_to(root):
        raise ValueError("Coordination root must contain the selected project")
    if type(budget_chars) is not int or not 1000 <= budget_chars <= 12000:
        raise ValueError("Coordination budget must be 1000..12000 characters")
    if actor and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", actor):
        raise ValueError("Invalid host-selected coordination actor")
    if acknowledge and not actor:
        raise ValueError("An observed-message receipt needs an actor")
    log = _read(root, "COLLAB/MESSAGES.md")
    board = _read(root, "COLLAB/BOARD.md").decode("utf-8-sig")
    starts = [m.start() for m in re.finditer(rb"(?m)^- \d{4}-\d{2}-\d{2} ", log)]
    offset = 0
    if after:
        parsed = re.fullmatch(r"([0-9]{1,7}):([a-f0-9]{64})", after)
        if not parsed:
            raise ValueError("Invalid coordination cursor")
        offset = int(parsed[1])
        if offset > len(log) or _sha(log[:offset]) != parsed[2]:
            raise ValueError("Shared log changed before the cursor; read from the start")
        if offset not in {0, len(log), *starts}:
            next_start = next((start for start in starts if start > offset), len(log))
            if log[offset:next_start].strip():
                raise ValueError("Coordination cursor must end at a complete message boundary")
    claims = []
    for line in board.splitlines():
        match = re.match(r"- \[(OPEN|CLAIMED|DONE|BLOCKED)\] (.+)", line)
        if match:
            fields = [p.strip()[:240] for p in match[2].split("|")]
            claims.append({"state": match[1], "item": fields[0],
                           **{key: fields[i] if len(fields)>i else ""
                              for i, key in enumerate(("item", "owner", "branch", "claimed_utc", "notes")) if i}})
    result = {"claims": claims[:40], "messages": [], "cursor": after or "0:" + _sha(b""),
              "truncated": False, "acknowledged": False,
              "notice": "Snapshot and observed-message receipts only. Board and ledger govern ownership; receipts grant no permissions."}
    # Claims may be large; report truncation rather than exceed the whole envelope.
    while len(serialize(result)) > budget_chars and result["claims"]:
        result["claims"].pop()
        result["truncated"] = True
    boundaries = starts + [len(log)]
    consumed = offset
    for i, start in enumerate(starts):
        end = boundaries[i + 1]
        if start < offset:
            continue
        message = log[start:end]
        text = message.decode("utf-8-sig").strip()
        entry = {"id": _sha(str(start).encode() + b":" + message)[:24], "text": text[:2500],
                 "clipped": len(text) > 2500}
        result["messages"].append(entry)
        trial_cursor = str(end) + ":" + _sha(log[:end])
        old_cursor = result["cursor"]
        result["cursor"] = trial_cursor
        # The first pending message must make progress even on a large board.
        if len(result["messages"]) == 1:
            while len(serialize(result)) > budget_chars and result["claims"]:
                result["claims"].pop()
                result["truncated"] = True
            while len(serialize(result)) > budget_chars and entry["text"]:
                excess = len(serialize(result)) - budget_chars
                entry["text"] = entry["text"][:-max(1, excess)]
                entry["clipped"] = True
                result["truncated"] = True
        if len(serialize(result)) > budget_chars:
            result["messages"].pop()
            result["cursor"] = old_cursor
            result["truncated"] = True
            break
        consumed = end
    # A header-only log is acknowledged without inventing a message.
    if not starts:
        consumed = len(log)
        result["cursor"] = str(consumed) + ":" + _sha(log[:consumed])
    while len(serialize(result)) > budget_chars and result["claims"]:
        result["claims"].pop()
        result["truncated"] = True
    if len(serialize(result)) > budget_chars:
        raise ValueError("Coordination envelope exceeds the budget")
    if acknowledge:
        root_id = _sha(str(root).encode("utf-8"))
        with brain.db:
            brain.db.execute("CREATE TABLE IF NOT EXISTS coordination_receipts(root_id TEXT,actor TEXT,cursor TEXT,at TEXT,PRIMARY KEY(root_id,actor))")
            brain.db.execute("INSERT OR REPLACE INTO coordination_receipts VALUES(?,?,?,?)",
                             (root_id, actor, result["cursor"], datetime.now(timezone.utc).isoformat()))
        result["acknowledged"] = True
    return result
