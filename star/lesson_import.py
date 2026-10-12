"""Strict, offline importer for STAR's star-lessons-v1 export format."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .knowledge import _project, now
from .lessons import (MAX_EVIDENCE, RECALLED_KINDS, SOURCE_TYPES, STATUSES, LessonStore,
                      check_lesson_text, has_secret, _normal, redact, subject_key)

MAX_IMPORT_BYTES = 1024 * 1024
MAX_IMPORT_ROWS = 500
_ROW_KEYS = frozenset(("id project kind text status source source_type evidence created updated "
                       "supersedes_id merged_into uses last_used origin").split())
_ROOT_KEYS = frozenset(("format", "project", "exported", "counts", "lessons"))
_COUNT_KEYS = frozenset((*STATUSES, "pending", "uses"))
_PRACTICE = re.compile(r"night-school:[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z")


def _fields(value, required, *, optional=frozenset(), label="object"):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError(f"Invalid {label} fields")


def _int(value, label, minimum=0):
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ValueError(f"Invalid {label}")
    return value


def _text(value, label, limit, *, empty=False, multiline=False):
    if (not isinstance(value, str) or len(value) > limit or
            (not empty and not value.strip()) or has_secret(value) or
            any(ord(c) < 32 and (not multiline or c not in "\r\n\t") for c in value)):
        raise ValueError(f"Invalid {label}")
    return value


def _time(value, label, *, empty=False):
    value = _text(value, label, 48, empty=empty)
    if empty and not value:
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid {label}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"Invalid {label}")
    return value


def parse_export(data: object) -> tuple[str, list[dict]]:
    """Validate every metadata and lesson field before the first database write.

    Imported IDs, owner claims and accepted statuses are never trusted.
    """
    _fields(data, _ROOT_KEYS, optional=frozenset({"note"}), label="export")
    if data["format"] != "star-lessons-v1":
        raise ValueError("Unsupported lessons format")
    project = _project(data["project"])
    _time(data["exported"], "export date")
    if "note" in data:
        _text(data["note"], "export note", 500, empty=True, multiline=True)
    _fields(data["counts"], _COUNT_KEYS, label="counts")
    for key in _COUNT_KEYS:
        _int(data["counts"][key], "count")
    rows = data["lessons"]
    if not isinstance(rows, list) or len(rows) > MAX_IMPORT_ROWS:
        raise ValueError("Invalid lessons list or too many lessons")
    imported, ids = [], set()
    for index, row in enumerate(rows):
        _fields(row, _ROW_KEYS, label=f"lesson {index}")
        old_id = _int(row["id"], "lesson ID", 1)
        if old_id in ids:
            raise ValueError("Repeated lesson ID")
        ids.add(old_id)
        if _project(row["project"]) != project:
            raise ValueError("Lesson project mismatch")
        if type(row["kind"]) is not str or row["kind"] not in RECALLED_KINDS:
            raise ValueError("Invalid lesson kind")
        if type(row["status"]) is not str or row["status"] not in STATUSES:
            raise ValueError("Invalid lesson status")
        if type(row["source_type"]) is not str or row["source_type"] not in SOURCE_TYPES:
            raise ValueError("Invalid lesson source type")
        source = _text(row["source"], "lesson source", 300)
        body = check_lesson_text(row["text"])
        evidence = _text(row["evidence"], "lesson evidence", MAX_EVIDENCE, empty=True, multiline=True)
        _text(row["origin"], "lesson origin", 250, empty=True)
        for field in ("created", "updated"):
            _time(row[field], field)
        _time(row["last_used"], "last used", empty=True)
        _int(row["uses"], "uses")
        for field in ("supersedes_id", "merged_into"):
            if row[field] is not None:
                _int(row[field], field, 1)
        practice = row["source_type"] == "verified-fix" and bool(_PRACTICE.fullmatch(source))
        provenance = (source if practice else "import:" + hashlib.sha256(
            (project + "\0" + row["source_type"] + "\0" + source).encode("utf-8")
        ).hexdigest())
        imported.append({"kind": row["kind"], "text": body, "status": row["status"],
                         "source_type": "practice" if practice else "import",
                         "source": provenance, "evidence": evidence})
    return project, imported


def read_export(path: Path) -> dict:
    """Read no more than 1 MiB, even if the file changes or is a pipe."""
    with Path(path).open("rb") as file:
        raw = file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError("Lesson file exceeds 1 MiB")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Lesson file is not UTF-8 JSON") from exc
    parse_export(value)
    return value


def import_export(store: LessonStore, data: object) -> dict:
    """Atomic new-candidate insertion, including idempotence after human review/edit."""
    project, entries = parse_export(data)
    added = skipped = 0
    try:
        store._begin()
        found = store.db.execute(
            "SELECT text,source_type,source FROM notes WHERE project=? AND status IS NOT NULL",
            (project,)).fetchall()
        texts = {_normal(r["text"]) for r in found}
        sources = {(r["source_type"], r["source"]) for r in found}
        for entry in entries:
            identity = (entry["source_type"], entry["source"])
            normal = _normal(entry["text"])
            # Do not resurrect rejected, superseded or folded-away exports.
            if entry["status"] not in ("candidate", "accepted") or identity in sources or normal in texts:
                skipped += 1
                continue
            stamp = now()
            store.db.execute(
                """INSERT INTO notes(project,kind,text,source,revision,reviewed,created,
                                     status,source_type,updated,subject,evidence)
                   VALUES(?,?,?,?,?,0,?,'candidate',?,?,?,?)""",
                (project, entry["kind"], entry["text"], entry["source"], "candidate-imported",
                 stamp, entry["source_type"], stamp, subject_key(entry["text"]), redact(entry["evidence"])))
            texts.add(normal)
            sources.add(identity)
            added += 1
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return {"project": project, "imported": added, "skipped": skipped}


def bundled_once(home: Path, version: str, *, enabled=False, bundle: Path | None = None) -> dict:
    """Import a shipped bundle only once per version, and only with an explicit opt-in."""
    if enabled is not True:
        return {"status": "off", "imported": 0}
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,39}", version):
        raise ValueError("Invalid bundle version")
    store = LessonStore(home)
    try:
        store.db.execute("CREATE TABLE IF NOT EXISTS lesson_bundle_imports "
                         "(version TEXT PRIMARY KEY, imported_at TEXT NOT NULL)")
        if store.db.execute("SELECT 1 FROM lesson_bundle_imports WHERE version=?", (version,)).fetchone():
            return {"status": "already", "imported": 0}
        path = bundle or Path(__file__).parent / "skill_packs" / "lessons_bundled.json"
        result = import_export(store, read_export(path))
        store.db.execute("INSERT INTO lesson_bundle_imports VALUES(?,?)", (version, now()))
        store.db.commit()
        return {"status": "imported", **result}
    finally:
        store.close()
