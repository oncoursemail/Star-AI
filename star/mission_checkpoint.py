"""Opt-in, read-only durable checkpoints for STAR specialist plans.

The trusted application supplies the database path, project, mission and two
revision identifiers. This module never runs workers, executes tools, requests
permissions, or selects files from model output. A checkpoint is deliberately
UNAVAILABLE for tasks that declare writes: external side effects require their
own approval and reconciliation ledger, not automatic replay.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from .orchestration import Task, TaskPlan

_SCHEMA = 1
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
_PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,95}\Z")
_REVISION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,127}\Z")


def _label(value: str, pattern: re.Pattern, name: str) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise ValueError(f"Invalid {name}: use a nonempty, bounded identifier")
    return value


def _fingerprint(plan: TaskPlan) -> str:
    """Hash every meaningful task field, declaration order, and concurrency."""
    tasks = [
        {
            "id": t.id, "role": t.role, "goal": t.goal,
            "dependencies": t.dependencies, "reads": t.reads,
            "writes": t.writes, "references": t.references,
            "evidence": t.evidence,
        }
        for t in plan.tasks.values()
    ]
    raw = json.dumps({"v": _SCHEMA, "parallel": plan.max_parallel, "tasks": tasks},
                     ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _result_payload(answer: str, evidence: tuple[str, ...], elapsed_ms: int) -> str:
    if (type(answer) is not str or not answer.strip() or len(answer) > 12000
            or type(evidence) is not tuple or len(evidence) > 20
            or any(type(e) is not str or len(e) > 500 for e in evidence)
            or type(elapsed_ms) is not int or not 0 <= elapsed_ms <= 3_600_000):
        raise ValueError("Invalid checkpoint result")
    return json.dumps({"answer": answer, "evidence": evidence, "elapsed_ms": elapsed_ms},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class MissionCheckpoint:
    """Local SQLite checkpoint for **completed read-only** DAG nodes.

    Reuse requires exactly the same project, mission ID, entire task plan,
    worker/model revision, and source-context revision. These revisions are
    supplied by trusted application code: callers MUST change them whenever
    models, prompts, worker implementations or evidence snapshots change.

    One instance is intended for one run at a time; SQLite serializes writes
    from distinct instances. Store only under STAR's private application data.
    Do not use it for untrusted code or mutable side-effecting workers.
    """

    def __init__(self, database: Path, *, project: str, mission_id: str,
                 worker_revision: str, context_revision: str):
        self.project = _label(project, _PROJECT, "project")
        self.mission_id = _label(mission_id, _ID, "mission_id")
        self.worker_revision = _label(worker_revision, _REVISION, "worker_revision")
        self.context_revision = _label(context_revision, _REVISION, "context_revision")
        if not isinstance(database, Path):
            raise TypeError("The trusted host must supply a Path")
        if database.exists() and (database.is_symlink() or not database.is_file()):
            raise PermissionError("Checkpoint database must be an ordinary file")
        if database.is_symlink():
            raise PermissionError("Symlinked checkpoint databases are not allowed")
        if not database.parent.is_dir():
            raise FileNotFoundError("Create a private checkpoint directory before starting")
        self._db = sqlite3.connect(database, timeout=10)
        self._db.execute("PRAGMA busy_timeout=10000")
        if os.name == "posix":
            os.chmod(database, 0o600)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS missions ("
            " project TEXT NOT NULL, id TEXT NOT NULL, plan_hash TEXT NOT NULL,"
            " worker_rev TEXT NOT NULL, context_rev TEXT NOT NULL,"
            " PRIMARY KEY(project,id))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS completed ("
            " project TEXT NOT NULL, mission_id TEXT NOT NULL, task_id TEXT NOT NULL,"
            " role TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,"
            " PRIMARY KEY(project,mission_id,task_id))"
        )
        self._db.commit()
        self._bound_hash: str | None = None
        self._tasks: dict[str, Task] = {}

    def __enter__(self) -> "MissionCheckpoint":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    def load(self, plan: TaskPlan) -> dict[str, dict]:
        """Return validated completed nodes; refuse changed or damaged missions."""
        if len(plan.tasks) > 32 or any(t.writes for t in plan.tasks.values()):
            raise PermissionError("Durable resume only supports bounded read-only plans")
        fingerprint = _fingerprint(plan)
        if self._bound_hash is not None and self._bound_hash != fingerprint:
            raise ValueError("Checkpoint instance already bound to another task plan")
        existing = self._db.execute(
            "SELECT plan_hash,worker_rev,context_rev FROM missions WHERE project=? AND id=?",
            (self.project, self.mission_id),
        ).fetchone()
        expected = (fingerprint, self.worker_revision, self.context_revision)
        if existing is None:
            with self._db:
                self._db.execute(
                    "INSERT INTO missions(project,id,plan_hash,worker_rev,context_rev)"
                    " VALUES(?,?,?,?,?)",
                    (self.project, self.mission_id, *expected),
                )
        elif tuple(existing) != expected:
            raise ValueError("Mission checkpoint revision or task plan changed; use a new mission ID")

        rows = self._db.execute(
            "SELECT task_id,role,payload,digest FROM completed"
            " WHERE project=? AND mission_id=? ORDER BY task_id",
            (self.project, self.mission_id),
        ).fetchall()
        restored = {}
        for task_id, role, payload, digest in rows:
            task = plan.tasks.get(task_id)
            if task is None or role != task.role or hashlib.sha256(
                payload.encode("utf-8")).hexdigest() != digest:
                raise ValueError("Stored mission evidence is damaged")
            try:
                data = json.loads(payload)
                if type(data) is not dict or set(data) != {"answer", "evidence", "elapsed_ms"}:
                    raise ValueError("Unexpected checkpoint payload fields")
                evidence = data["evidence"]
                if type(evidence) is not list:
                    raise ValueError("Invalid stored evidence")
                normalized = _result_payload(data["answer"], tuple(evidence), data["elapsed_ms"])
                if normalized != payload:
                    raise ValueError("Noncanonical checkpoint payload")
            except (TypeError, KeyError, ValueError) as exc:
                raise ValueError("Stored mission result is invalid") from exc
            restored[task_id] = {
                "answer": data["answer"],
                "evidence": tuple(evidence),
                "elapsed_ms": data["elapsed_ms"],
            }
        self._bound_hash = fingerprint
        self._tasks = dict(plan.tasks)
        return restored

    def save(self, task: Task, *, answer: str, evidence: tuple[str, ...],
             elapsed_ms: int) -> None:
        """Atomically record a completed result, refusing accidental replacement."""
        if self._bound_hash is None or self._tasks.get(task.id) != task or task.writes:
            raise PermissionError("Load an approved read-only plan before saving")
        payload = _result_payload(answer, evidence, elapsed_ms)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        existing = self._db.execute(
            "SELECT payload,digest FROM completed"
            " WHERE project=? AND mission_id=? AND task_id=?",
            (self.project, self.mission_id, task.id),
        ).fetchone()
        if existing is not None:
            if tuple(existing) != (payload, digest):
                raise ValueError("Refusing to replace an existing completed checkpoint")
            return
        with self._db:
            self._db.execute(
                "INSERT INTO completed(project,mission_id,task_id,role,payload,digest)"
                " VALUES(?,?,?,?,?,?)",
                (self.project, self.mission_id, task.id, task.role, payload, digest),
            )
