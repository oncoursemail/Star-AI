"""Read-only live-work status for STAR's owner-scoped Discord bot.

A trusted worker/supervisor writes a bounded JSON snapshot. Discord NEVER chooses
a path or executes a job. Producer-reported observations are not independent proof.
An absent/stale report is explicitly unknown, not simulated "studying" activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Mapping

MAX_BYTES = 16_384
MAX_WORKERS = 12
FRESH_SECONDS = 180
FINISHED_SECONDS = 86_400
_KINDS = frozenset({"coding", "studying", "researching", "testing", "building", "designing",
                    "generating", "dubbing", "reviewing", "planning", "operating"})
_STATES = frozenset({"queued", "working", "waiting", "paused", "completed", "failed"})
_ACTIVE = frozenset({"working"})
_ID = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,31}\Z")
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_LINE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,;:!?()'&#+_-]{0,179}\Z")
_FIELDS = frozenset({"id", "kind", "state", "task", "last_step", "next_step",
                     "done", "total", "updated_at"})
_TOP_FIELDS = frozenset({"version", "updated_at", "workers"})


@dataclass(frozen=True)
class WorkSettings:
    enabled: bool = False
    report_path: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WorkSettings":
        source = os.environ if env is None else env
        flag = str(source.get("STAR_DISCORD_WORK_STATUS", "0")).strip() or "0"
        if flag not in {"0", "1"}:
            raise ValueError("STAR_DISCORD_WORK_STATUS must be 0 or 1")
        if flag == "0":
            return cls()
        raw = str(source.get("STAR_DISCORD_WORK_REPORT", "")).strip()
        path = Path(raw)
        if (not raw or len(raw) > 2048 or not path.is_absolute()
                or path.suffix.lower() != ".json" or path.is_symlink()):
            raise ValueError("Work status needs a trusted absolute .json report path")
        return cls(True, path)


@dataclass(frozen=True)
class WorkItem:
    id: str
    kind: str
    state: str
    task: str
    last_step: str
    next_step: str
    done: int
    total: int
    updated_at: datetime

    def fresh(self, now: datetime) -> bool:
        seconds = (now - self.updated_at).total_seconds()
        limit = FINISHED_SECONDS if self.state in {"completed", "failed"} else FRESH_SECONDS
        return 0 <= seconds <= limit


@dataclass(frozen=True)
class WorkSnapshot:
    updated_at: datetime
    workers: tuple[WorkItem, ...]

    def fresh(self, now: datetime) -> bool:
        return 0 <= (now - self.updated_at).total_seconds() <= FRESH_SECONDS


def _utc_stamp(value: object) -> datetime:
    if not isinstance(value, str) or not _STAMP.fullmatch(value):
        raise ValueError("Work report timestamps must be UTC with seconds")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid work report date") from exc


def _plain(value: object, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    if not isinstance(value, str) or not _LINE.fullmatch(value) or value != value.strip():
        raise ValueError("Work status labels must be short plain text without mentions or paths")
    return value


def _count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 10_000:
        raise ValueError("Invalid work progress count")
    return value


def parse_work_report(raw: bytes) -> WorkSnapshot:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Work report missing or oversized")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Work report is not valid JSON") from exc
    if not isinstance(data, dict) or set(data) != _TOP_FIELDS or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Unsupported work report schema")
    entries = data["workers"]
    if not isinstance(entries, list) or len(entries) > MAX_WORKERS:
        raise ValueError("Work report has too many workers")
    workers = []
    seen = set()
    timestamp = _utc_stamp(data["updated_at"])
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _FIELDS:
            raise ValueError("Invalid work item fields")
        ident = entry["id"]
        if not isinstance(ident, str) or not _ID.fullmatch(ident) or ident in seen:
            raise ValueError("Invalid or duplicate work ID")
        seen.add(ident)
        kind, state = entry["kind"], entry["state"]
        if kind not in _KINDS or state not in _STATES:
            raise ValueError("Invalid work kind or state")
        done, total = _count(entry["done"]), _count(entry["total"])
        if done > total:
            raise ValueError("Work progress cannot exceed total")
        work_time = _utc_stamp(entry["updated_at"])
        if work_time > timestamp:
            raise ValueError("Worker timestamp is later than snapshot")
        workers.append(WorkItem(ident, kind, state,
                                _plain(entry["task"]), _plain(entry["last_step"], optional=True),
                                _plain(entry["next_step"], optional=True), done, total, work_time))
    return WorkSnapshot(timestamp, tuple(workers))


def read_work_report(settings: WorkSettings) -> WorkSnapshot:
    if not settings.enabled or settings.report_path is None:
        raise ValueError("Live worker reporting has not been connected")
    path = settings.report_path
    if not path.is_absolute() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Work report path is not trusted")
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_BYTES:
            raise ValueError("Work report must be a small regular JSON file")
        with path.open("rb") as handle:
            payload = handle.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError("No current work report from STAR's workers") from exc
    return parse_work_report(payload)


def _age(dt: datetime, now: datetime) -> str:
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"


def format_work_report(snapshot: WorkSnapshot, *, now: datetime | None = None) -> str:
    """Never call a stale worker active. No LLM guesses, hidden paths or bot mentions."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Status clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if not snapshot.fresh(now):
        return ("I can't confirm what I'm doing right now. The last work snapshot is "
                f"stale ({_age(snapshot.updated_at, now)}), so I won't pretend those jobs are still running.")
    live = [w for w in snapshot.workers if w.fresh(now) and w.state in _ACTIVE]
    pending = [w for w in snapshot.workers if w.fresh(now) and w.state in {"queued", "waiting", "paused"}]
    finished = [w for w in snapshot.workers if w.fresh(now) and w.state in {"completed", "failed"}]
    stale = len(snapshot.workers) - len(live) - len(pending) - len(finished)
    lines = ["**STAR · What I'm actually working on**",
             f"Worker-reported snapshot: {_age(snapshot.updated_at, now)}. Not independently verified by Discord."]
    if not live:
        lines.append("**Active now:** No fresh worker has reported active work.")
    else:
        lines.append(f"**Active now: {len(live)}**")
    for work in (*live, *pending, *finished):
        state = ("Working" if work.state == "working" else work.state.capitalize())
        count = f" · checks {work.done}/{work.total}" if work.total else ""
        lines.append(f"**{work.kind.capitalize()} · {state}** — {work.task}{count}")
        if work.last_step:
            lines.append(f"  Last recorded action: {work.last_step}")
        if work.next_step and work.state != "completed":
            lines.append(f"  Next recorded step: {work.next_step}")
        lines.append(f"  Updated {_age(work.updated_at, now)}")
    if stale:
        lines.append(f"**Unconfirmed:** {stale} worker report(s) expired; no live state inferred.")
    if not snapshot.workers:
        lines.append("No worker jobs were included in the last report.")
    return "\n".join(lines)


def classify_work_question(text: str) -> bool:
    """Route only explicit owner questions about STAR's *own* current work."""
    if not isinstance(text, str) or len(text) > 190:
        return False
    normalized = re.sub(r"\s+", " ", text.strip().lower()).rstrip("?.!")
    normalized = re.sub(r"^(?:hey |hi |hello )?(?:star(?: ai)?[,! ]+)", "", normalized).strip()
    return normalized in {
        "what are you working on", "what are you working on right now",
        "what are you doing", "what are you doing right now",
        "what is star working on", "what is star ai working on",
        "what have you been doing", "what have you finished",
        "what are your agents doing", "what are the agents working on",
        "are you coding", "are you studying", "are you researching",
        "what are you studying", "what are you coding", "what are you researching",
        "show me your progress", "how is the work going", "how's the work going",
        "what is brain 1 working on", "what is brain 2 working on",
    }
