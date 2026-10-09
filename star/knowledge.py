"""Project-scoped, evidence-carrying knowledge and immutable local artifacts.

No vector database or model call is required for this first exact/keyword retrieval layer.
Entries are candidate knowledge unless an explicit trusted caller promotes them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Literal

Kind = Literal["requirement", "reference", "decision", "fix", "observation", "unknown"]
VALID_KINDS = frozenset({"requirement", "reference", "decision", "fix", "observation", "unknown"})
MAX_ARTIFACT = 32 * 1024 * 1024
PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project(value: str) -> str:
    if not isinstance(value, str) or not PROJECT.fullmatch(value):
        raise ValueError("Project identifier must contain 1-96 safe characters")
    return value


@dataclass(frozen=True)
class Note:
    id: int
    project: str
    kind: str
    text: str
    source: str
    revision: str
    reviewed: bool
    created: str


class KnowledgeStore:
    """Small, auditable memory for references, decisions, and checked results.

    Ordinary AI-written notes are *candidate*, not ground truth. Use review_note()
    only from an authorized human or independently verified acceptance workflow.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "knowledge.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
            source TEXT NOT NULL, revision TEXT NOT NULL,
            reviewed INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_notes_project ON notes(project,reviewed,created)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS artifacts (
            digest TEXT PRIMARY KEY, size INTEGER NOT NULL, media_type TEXT NOT NULL,
            created TEXT NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS project_artifacts (
            project TEXT NOT NULL, digest TEXT NOT NULL, origin TEXT NOT NULL,
            PRIMARY KEY(project,digest,origin),
            FOREIGN KEY(digest) REFERENCES artifacts(digest)
        )""")
        self.db.commit()

    def add_note(self, *, project: str, kind: str, text: str, source: str, revision: str = "unknown") -> int:
        project = _project(project)
        if kind not in VALID_KINDS:
            raise ValueError("Unknown note kind")
        if not isinstance(text, str) or not text.strip() or len(text) > 16_000:
            raise ValueError("Knowledge note must be 1–16000 nonempty characters")
        if not isinstance(source, str) or not source.strip() or len(source) > 2048:
            raise ValueError("A provenance reference is required")
        if not isinstance(revision, str) or not revision.strip() or len(revision) > 200:
            raise ValueError("A revision identifier is required")
        row = self.db.execute(
            "INSERT INTO notes(project,kind,text,source,revision,created) VALUES(?,?,?,?,?,?)",
            (project, kind, text, source, revision, now()),
        )
        self.db.commit()
        return int(row.lastrowid)

    def review_note(self, *, project: str, note_id: int, evidence: str) -> None:
        """Called only from a *trusted* review or test-acceptance path, not by model prose."""
        project = _project(project)
        if not evidence.strip() or len(evidence) > 2048:
            raise ValueError("Verified evidence identifier is required")
        # Append the review evidence as a separate immutable observation note.
        row = self.db.execute("SELECT id FROM notes WHERE project=? AND id=?", (project, note_id)).fetchone()
        if row is None:
            raise ValueError("Knowledge note doesn't belong to this project")
        self.add_note(project=project, kind="observation", text=f"Reviewed note {note_id}: {evidence}",
                      source=f"review:{note_id}", revision="accepted")
        self.db.execute("UPDATE notes SET reviewed=1 WHERE project=? AND id=?", (project, note_id))
        self.db.commit()

    def find(self, project: str, query: str = "", *, reviewed_only: bool = True, limit: int = 12) -> list[Note]:
        project = _project(project)
        if not 1 <= limit <= 50:
            raise ValueError("limit must be 1..50")
        tokens = re.findall(r"[A-Za-z0-9_]{2,}", query.lower())[:8]
        sql = "SELECT * FROM notes WHERE project=?"
        params: list[object] = [project]
        if reviewed_only:
            sql += " AND reviewed=1"
        if tokens:
            sql += " AND (" + " OR ".join("lower(text) LIKE ? ESCAPE '\\'" for _ in tokens) + ")"
            params.extend("%" + t.replace("_", "\\_").replace("%", "\\%") + "%" for t in tokens)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [Note(id=int(row["id"]), project=row["project"], kind=row["kind"],
                     text=row["text"], source=row["source"], revision=row["revision"],
                     reviewed=bool(row["reviewed"]), created=row["created"])
                for row in self.db.execute(sql, params)]

    def ingest_artifact(self, *, project: str, path: Path, origin: str, media_type: str) -> tuple[str, Path]:
        """Store original bytes by SHA256; never treat file content as executable instructions."""
        project = _project(project)
        if not origin or len(origin) > 2048:
            raise ValueError("Artifact origin required")
        if not media_type or len(media_type) > 100:
            raise ValueError("Artifact MIME type required")
        if not path.is_file() or path.stat().st_size > MAX_ARTIFACT:
            raise ValueError("Artifact missing or too large")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        dest = self.root / "artifacts" / digest[:2] / digest
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as stream:
                name = Path(stream.name)
                try:
                    stream.write(raw)
                except BaseException:
                    name.unlink(missing_ok=True)
                    raise
            os.replace(name, dest)
        self.db.execute("INSERT OR IGNORE INTO artifacts(digest,size,media_type,created) VALUES(?,?,?,?)",
                        (digest, len(raw), media_type, now()))
        self.db.execute("INSERT OR IGNORE INTO project_artifacts(project,digest,origin) VALUES(?,?,?)",
                        (project, digest, origin))
        self.db.commit()
        return digest, dest

    def artifact(self, project: str, digest: str) -> Path:
        project = _project(project)
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid sha256 digest")
        row = self.db.execute("SELECT 1 FROM project_artifacts WHERE project=? AND digest=?",
                              (project, digest)).fetchone()
        if not row:
            raise ValueError("Artifact isn't accessible in this project")
        path = self.root / "artifacts" / digest[:2] / digest
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Artifact missing or checksum failed")
        return path

    def close(self) -> None:
        self.db.close()
