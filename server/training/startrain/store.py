"""Durable state: append-only JSONL files plus a small state file written atomically after every candidate.

kept.jsonl       one line per kept example (the dataset, with the evidence of every gate)
rejected.jsonl   one line per rejected candidate (gate, reason, and the texts, for tuning and later preference data)
vectors.jsonl    task-text embeddings of kept examples (for the embedding near-duplicate gate)
state.json       counters, cursors, idea pool, run history; rebuilt from the JSONL files if missing or damaged
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .quiet import atomic_write_text

SCHEMA = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_jsonl(path: Path, row: dict) -> None:
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue                # a torn last line after a crash; the candidate is simply redone
    return rows


def empty_state() -> dict:
    return {"schema": SCHEMA, "created": now_iso(), "candidates": 0, "kept": 0,
            "rejected": {}, "by_category": {}, "by_topic": {}, "tokens": {"prompt": 0, "completion": 0},
            "seconds": {"active": 0.0, "llm": 0.0, "gates": 0.0},
            "paused": {}, "ideas": {}, "runs": [], "infra_errors": 0}


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.kept_path = data_dir / "kept.jsonl"
        self.rejected_path = data_dir / "rejected.jsonl"
        self.vectors_path = data_dir / "vectors.jsonl"
        self.state_path = data_dir / "state.json"
        self.state = self._load()

    def _load(self) -> dict:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if state.get("schema") == SCHEMA:
                return self.reconcile(state)
        except (OSError, ValueError):
            pass
        return self.rebuild()

    def reconcile(self, state: dict) -> dict:
        """A crash between appending a row and saving the state leaves the files ahead of state.json. The files
        are authoritative for the counts (so candidate ids are never reused); everything else is kept."""
        built = self.rebuild()
        if built["candidates"] != state.get("candidates") or built["kept"] != state.get("kept"):
            for key in ("candidates", "kept", "rejected", "by_category", "by_topic"):
                state[key] = built[key]
        return state

    def rebuild(self) -> dict:
        """Counters from the two JSONL files (used when state.json is missing or unreadable)."""
        state = empty_state()
        for row in read_jsonl(self.kept_path):
            state["kept"] += 1
            state["candidates"] += 1
            cat = state["by_category"].setdefault(row.get("category", "?"), {"candidates": 0, "kept": 0})
            cat["candidates"] += 1
            cat["kept"] += 1
            top = state["by_topic"].setdefault(row.get("topic", "?"), {"candidates": 0, "kept": 0})
            top["candidates"] += 1
            top["kept"] += 1
        for row in read_jsonl(self.rejected_path):
            state["candidates"] += 1
            gate = state["rejected"].setdefault(row.get("gate", "?"), {})
            gate[row.get("code", "?")] = gate.get(row.get("code", "?"), 0) + 1
            cat = state["by_category"].setdefault(row.get("category", "?"), {"candidates": 0, "kept": 0})
            cat["candidates"] += 1
            top = state["by_topic"].setdefault(row.get("topic", "?"), {"candidates": 0, "kept": 0})
            top["candidates"] += 1
        return state

    def save(self) -> None:
        atomic_write_text(self.state_path, json.dumps(self.state, indent=1, sort_keys=True))

    # --- recording a finished candidate --------------------------------------------------------------------------
    def record_kept(self, row: dict, vector: list[float] | None) -> None:
        append_jsonl(self.kept_path, row)
        if vector is not None:
            append_jsonl(self.vectors_path, {"id": row["id"], "vec": [round(x, 5) for x in vector]})
        st = self.state
        st["kept"] += 1
        self._count(row)

    def record_rejected(self, row: dict) -> None:
        append_jsonl(self.rejected_path, row)
        gate = self.state["rejected"].setdefault(row["gate"], {})
        gate[row["code"]] = gate.get(row["code"], 0) + 1
        self._count(row)

    def _count(self, row: dict) -> None:
        st = self.state
        st["candidates"] += 1
        kept = 1 if "gates" in row and "gate" not in row else 0
        cat = st["by_category"].setdefault(row.get("category", "?"), {"candidates": 0, "kept": 0})
        cat["candidates"] += 1
        cat["kept"] += kept
        top = st["by_topic"].setdefault(row.get("topic", "?"), {"candidates": 0, "kept": 0})
        top["candidates"] += 1
        top["kept"] += kept

    def load_vectors(self) -> list[tuple[str, list[float]]]:
        return [(r["id"], r["vec"]) for r in read_jsonl(self.vectors_path) if "id" in r and "vec" in r]
