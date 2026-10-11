"""Query/stats over an existing, exactly registered shared-brain store.

The trusted host passes the selected workspace and its registered root list to
make_shared_brain_runtime(..., enabled=True). Canonical roots must match exactly;
registering a parent never grants this adapter access to its descendants.

Requires star.shared_brain from PR43 on Python's import path. This adapter never
builds, syncs, initializes a store, changes registration, or exposes feedback,
lessons, review or activation. Read-only describes its source/knowledge behavior:
queries append the existing local query audit, and SQLite may maintain WAL/SHM
sidecars. Project source files and graph generations are not changed.

Each dispatch opens and closes an existing SQLite connection in the calling
thread. The host can combine definitions(prompt) with LocalIntelligence's tool
list and pass that turn's enabled tool names to call(..., enabled=names).
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Iterable


_NAMES = frozenset({"shared_brain_query", "shared_brain_stats"})
_BUDGET = 3000
_COLUMNS = {
    "meta": {"name", "value"},
    "entities": {"id", "payload"},
    "edges": {"id", "source", "target", "payload"},
    "sources": {"path", "sha256"},
    "generations": {"id", "graph_sha256", "manifest_sha256", "at", "summary"},
    "queries": {"id", "generation", "question", "response", "at"},
    "outcomes": {"id", "query_id", "outcome", "actor", "answer", "correction", "at"},
}


def runtime_tools() -> tuple[dict, ...]:
    """Independent schemas; no operator/proposal capabilities enter this registry."""
    from star.shared_brain.protocol import READ_TOOLS
    tools = [deepcopy(t) for t in READ_TOOLS if t["name"] in _NAMES]
    query = next(t for t in tools if t["name"] == "shared_brain_query")["inputSchema"]["properties"]
    query["budget_chars"].update(maximum=_BUDGET, default=_BUDGET)
    query["limit"].update(maximum=8, default=8)
    return tuple(tools)


RUNTIME_TOOLS = runtime_tools()


def registered_workspace(workspace, registered_roots) -> Path | None:
    """Exact host registration; never grant descendants via a parent registration."""
    if workspace is None or isinstance(registered_roots, (str, Path)):
        return None
    try:
        selected = Path(workspace).expanduser().resolve(strict=True)
        if not selected.is_dir():
            return None
        registered = {_key(Path(root).expanduser().resolve(strict=True)) for root in registered_roots}
        return selected if _key(selected) in registered else None
    except (OSError, ValueError, TypeError, RuntimeError):
        return None


def shared_store_present(workspace: Path) -> bool:
    """Preparation markers forbid silently substituting an older raw export.

    lexists detects dangling links without opening their target. An unsafe graph
    directory is also treated as unavailable preparation rather than followed.
    The hub latches this observation, so removing a store cannot restore fallback.
    """
    from star.shared_brain.store import _link
    graph = workspace / "graphify-out"
    try:
        return (_link(graph) or any(os.path.lexists(path) for path in (
            graph / "shared-brain", graph / "shared-brain-manifest.json",
            graph / ".shared-brain-build.lock")))
    except OSError:
        return True


class SharedBrainUnavailable(RuntimeError):
    """The host must prepare the selected registered store before using it."""


def _key(path: Path) -> str:
    return os.path.normcase(str(path))


def _project_id(path: Path) -> str:
    return hashlib.sha256(_key(path).encode("utf-8")).hexdigest()


def _paths(workspace: Path) -> tuple[Path, Path]:
    directory = workspace / "graphify-out/shared-brain"
    database = directory / "shared-brain.sqlite3"
    # Use the same Windows reparse/symlink refusal as the underlying store.
    from star.shared_brain.store import _link
    for part in (directory, *directory.parents):
        if _link(part):
            raise SharedBrainUnavailable("Shared brain unavailable: store paths cannot follow links")
    for suffix in ("", "-wal", "-shm", "-journal"):
        if _link(Path(str(database) + suffix)):
            raise SharedBrainUnavailable("Shared brain unavailable: database paths cannot follow links")
    if not directory.is_dir() or not database.is_file():
        raise SharedBrainUnavailable("Shared brain unavailable: operator-initialized store required")
    for lock in (directory / ".shared-brain-init.lock",
                 workspace / "graphify-out/.shared-brain-build.lock"):
        if _link(lock) or lock.exists():
            raise SharedBrainUnavailable("Shared brain unavailable: operator preparation is in progress")
    return directory, database


def _check_ready(db: sqlite3.Connection, project: str) -> int:
    # All SQL names are fixed host constants, never model arguments.
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if (not _COLUMNS.keys() <= tables
            or db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' LIMIT 1").fetchone()):
        raise SharedBrainUnavailable("Shared brain unavailable: incompatible store schema")
    for table, columns in _COLUMNS.items():
        found = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
        if not columns <= found:
            raise SharedBrainUnavailable("Shared brain unavailable: incompatible store schema")
    binding = db.execute("SELECT value FROM meta WHERE name='project_id'").fetchone()
    latest = db.execute("SELECT id,graph_sha256,manifest_sha256,length(summary) FROM generations ORDER BY id DESC LIMIT 1").fetchone()
    if not binding or binding[0] != project:
        raise SharedBrainUnavailable("Shared brain unavailable: store project binding differs")
    if (not latest or type(latest[0]) is not int or latest[0] < 1
            or not isinstance(latest[1], str) or not re.fullmatch(r"[a-f0-9]{64}", latest[1])
            or (latest[2] != "" and (not isinstance(latest[2], str) or not re.fullmatch(r"[a-f0-9]{64}", latest[2])))
            or type(latest[3]) is not int or not 1 <= latest[3] <= _BUDGET):
        raise SharedBrainUnavailable("Shared brain unavailable: a valid synced generation is required")
    summary = json.loads(db.execute("SELECT summary FROM generations WHERE id=?", (latest[0],)).fetchone()[0])
    if (not isinstance(summary, dict) or summary.get("project_id") != project
            or type(summary.get("generation")) is not int or summary["generation"] != latest[0]
            or not isinstance(summary.get("attestation"), str)
            or summary["attestation"] not in {"verified", "missing", "invalid"}
            or db.execute("SELECT 1 FROM entities LIMIT 1").fetchone() is None):
        raise SharedBrainUnavailable("Shared brain unavailable: inconsistent generation metadata")
    _check_payloads(db)
    return latest[0]


def _check_payloads(db: sqlite3.Connection) -> None:
    """Reject malformed/tampered projections before advertising a ready store.

    Imported projections have bounded fields and graph counts. Check existing
    rows before reading them without initializing or repairing the database.
    """
    from star.graphify_bridge import MAX_EDGES, MAX_GRAPH_BYTES, MAX_NODES
    from star.shared_brain.store import _relpath
    for table, cap in (("entities", MAX_NODES), ("edges", MAX_EDGES)):
        size = db.execute("SELECT COUNT(*),COALESCE(MAX(length(payload)),0),"
                          "COALESCE(SUM(length(payload)),0) FROM " + table).fetchone()
        if size[0] > cap or size[1] > 16000 or size[2] > MAX_GRAPH_BYTES * 4:
            raise SharedBrainUnavailable("Shared brain unavailable: store projection exceeds limits")
        for row in db.execute("SELECT id,payload FROM " + table):
            item = json.loads(row[1])
            fields = (("id", "label", "source_file", "source_location", "origin", "confidence", "trust")
                      if table == "entities" else
                      ("source", "target", "relation", "source_file", "source_location", "origin", "confidence"))
            if (not isinstance(item, dict) or any(not isinstance(item.get(key), str) for key in fields)
                    or _relpath(item["source_file"]) is None or item.get("untrusted_instructions") is not True):
                raise SharedBrainUnavailable("Shared brain unavailable: invalid source projection")
            if table == "entities" and (
                    item["id"] != row[0] or not re.fullmatch(r"L[1-9]\d*(?:-L?[1-9]\d*)?", item["source_location"])
                    or item["trust"] != ("extracted_reference" if item["origin"] == "ast" else "candidate_reference")):
                raise SharedBrainUnavailable("Shared brain unavailable: invalid source provenance")


def _authorizer(*, readonly: bool):
    """Enforce the SQL boundary even if another connection adds a trigger.

    Keep the callback installed for the entire connection: SQLite reauthorizes
    statements recompiled after schema changes. Never IGNORE an action, since
    that can produce incomplete successful data or still allow DELETE.
    """
    def authorize(action, first, second, database, origin):
        first = first.casefold() if isinstance(first, str) else ""
        second = second.casefold() if isinstance(second, str) else ""
        if origin is not None or (database is not None and database.casefold() != "main"):
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_TRANSACTION and first in {"begin", "commit", "rollback"}:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            columns = (_COLUMNS.get(first) if first not in {"sqlite_master", "sqlite_schema"}
                       else {"name", "type", "tbl_name", "rootpage", "sql"})
            if columns is not None and (not second or second in columns):
                return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and (
                (first == "table_info" and second in _COLUMNS)
                or (first == "trusted_schema" and second in {"off", "0"})):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and second in {"length", "count", "max", "sum", "coalesce"}:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_INSERT and not readonly and first == "queries" and database == "main":
            return sqlite3.SQLITE_OK
        # Includes UPDATE/DELETE, trigger-origin INSERT, DDL, ATTACH, extension
        # functions and connection pragmas outside the two fixed host reads.
        return sqlite3.SQLITE_DENY
    return authorize


def _open_existing(workspace: Path, *, readonly: bool):
    """Reuse SharedBrain queries without invoking its initializing constructor."""
    from star.shared_brain.store import SharedBrain
    directory, database = _paths(workspace)
    project = _project_id(workspace)

    class RuntimeConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            cursor = super().execute(sql, parameters)
            if sql.strip().upper() == "BEGIN":
                # SharedBrain.query and stats begin their read snapshots here.
                # Validate within that same transaction before they consume any
                # rows; checks from an earlier readiness transaction can drift.
                _paths(workspace)
                _check_ready(self, project)
            return cursor

    class ExistingSharedBrain(SharedBrain):
        def __init__(self):
            self.workspace, self.store_dir, self.db_path = workspace, directory, database
            self.project_id = project
            # mode=rw refuses a missing DB even if it disappeared after _paths.
            mode = "ro" if readonly else "rw"
            self.db = sqlite3.connect(database.as_uri() + "?mode=" + mode, uri=True,
                                      timeout=5, factory=RuntimeConnection)
            self.db.row_factory = sqlite3.Row
            self.db.set_authorizer(_authorizer(readonly=readonly))
            try:
                self.db.execute("PRAGMA trusted_schema=OFF")
                self.db.execute("BEGIN")
                self.db.commit()
            except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error):
                self.db.close()
                raise SharedBrainUnavailable("Shared brain unavailable: invalid existing store") from None
            except Exception:
                self.db.close()
                raise

    return ExistingSharedBrain()


class SharedBrainRuntime:
    """Exactly two scoped tools over an already prepared project store."""

    def __init__(self, workspace: Path):
        self._workspace = workspace
        self._closed = False
        self._tools = {t["name"]: deepcopy(t) for t in RUNTIME_TOOLS}

    def status(self) -> dict:
        if self._closed:
            return {"enabled": False, "ready": False, "reason": "closed"}
        brain = None
        try:
            brain = _open_existing(self._workspace, readonly=True)
            return {"enabled": True, "ready": True, "reference_data_only": True}
        except (OSError, ValueError, RuntimeError, sqlite3.Error, ImportError):
            return {"enabled": True, "ready": False, "reason": "operator-prepared store unavailable"}
        finally:
            if brain is not None:
                brain.close()

    def definitions(self, prompt: str = "") -> list[dict]:
        return deepcopy(list(self._tools.values())) if self.status()["ready"] else []

    @staticmethod
    def owns(name: str) -> bool:
        return isinstance(name, str) and name in _NAMES

    def call(self, name: str, args: dict, *, enabled: set[str]) -> dict:
        if (self._closed or not self.owns(name) or not isinstance(enabled, (set, frozenset))
                or name not in enabled or not isinstance(args, dict)):
            raise PermissionError("Shared-brain tool is not enabled for this task")
        from jsonschema import Draft202012Validator
        from star.shared_brain.store import serialize
        Draft202012Validator(self._tools[name]["inputSchema"]).validate(args)
        for key in ("limit", "budget_chars"):
            if key in args and type(args[key]) is not int:
                raise ValueError("Shared-brain limits must be integers")
        brain = None
        try:
            brain = _open_existing(self._workspace, readonly=name == "shared_brain_stats")
            if name == "shared_brain_query":
                result = brain.query(**args)
            else:
                # stats() reads several tables; hold one generation snapshot.
                with brain.db:
                    brain.db.execute("BEGIN")
                    result = brain.stats()
            if len(serialize(result)) > args.get("budget_chars", _BUDGET):
                raise SharedBrainUnavailable("Shared brain unavailable: response exceeds its character budget")
            return result
        except (OSError, sqlite3.Error, json.JSONDecodeError, KeyError, TypeError):
            raise SharedBrainUnavailable("Shared brain unavailable: existing store could not be read") from None
        finally:
            if brain is not None:
                brain.close()

    def close(self) -> None:
        self._closed = True


def make_shared_brain_runtime(workspace: Path | str | None,
                             registered_roots: Iterable[Path | str], *,
                             enabled: bool = False) -> SharedBrainRuntime | None:
    """Return None for disabled, unregistered or unprepared workspaces.

    Registration and enabling are trusted host choices, never model tool input.
    No recursive parent registration, automatic preparation or retained DB handle.
    """
    if enabled is not True:
        return None
    try:
        selected = registered_workspace(workspace, registered_roots)
        if selected is None:
            return None
        runtime = SharedBrainRuntime(selected)
        return runtime if runtime.status()["ready"] else None
    except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error, ImportError):
        return None
