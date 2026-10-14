"""Project-bound Graphify retrieval with freshness and candidate-only feedback.

This consumes Graphify exports; it does not generate a second graph, execute
code, authorize tools, train models, or turn retrieved text into instructions.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
from time import perf_counter, sleep
import uuid

from ..graphify_bridge import GraphifyGraph, MAX_EDGES, MAX_GRAPH_BYTES, MAX_NODES
from ..lessons import has_secret

MAX_SOURCE_BYTES = 8_000_000
MAX_MANIFEST_BYTES = 8_000_000
_LOCATION = re.compile(r"L([1-9][0-9]*)(?:-L?([1-9][0-9]*))?")
_CONTROL = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_SECRET = re.compile(r"(?:\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|credentials(?:\..*)?|secrets(?:\..*)?|server_api_key|star\.env|.*\.(?:pem|key|p12|pfx|sqlite3?))", re.I)
_DENIED_DIRS = frozenset({".git", ".ssh", ".star", ".venv", "secrets", "credentials", "worktrees", "graphify-out"})


def serialize(value: dict | list) -> str:
    """The exact encoding used to enforce response character budgets."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _text(value, limit: int) -> str:
    return _CONTROL.sub("", value)[:limit] if isinstance(value, str) else ""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _link(path: Path) -> bool:
    """Reject symbolic links and Windows junction/reparse paths, including 3.10."""
    if path.is_symlink():
        return True
    try:
        # Windows exposes reparse attributes through lstat even on Python
        # versions that predate Path.is_junction(). No target bytes are read.
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return False


def _at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@contextmanager
def _initializing(directory: Path):
    """Serialize the brief first-open/schema step across assistant processes."""
    lock = directory / ".shared-brain-init.lock"
    deadline = perf_counter() + 10
    while True:
        if _link(lock):
            raise ValueError("Shared store initialization lock cannot be a link")
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            if perf_counter() >= deadline:
                raise RuntimeError("Shared store initialization is in use; retry after the host operation finishes") from None
            sleep(.025)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _relpath(value) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 400:
        return None
    if _CONTROL.search(value) or "\\" in value or ":" in value or value.startswith("/"):
        return None
    parts = value.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        return None
    if any(p.casefold() in _DENIED_DIRS for p in parts[:-1]) or _SECRET.fullmatch(parts[-1]):
        return None
    return str(PurePosixPath(value))


class SharedBrain:
    """One local graph store bound to exactly one resolved workspace root.

    A schema-1 manifest must contain project_id, graph_sha256 and a sources
    mapping of relative paths to {sha256}. It attests hashes at extraction time;
    hashing current files beside an older export is not an extraction attestation.
    """

    def __init__(self, workspace: Path, store_dir: Path | None = None):
        self.workspace = Path(workspace).expanduser().resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError("Workspace must be an existing directory")
        self.project_id = _sha(os.path.normcase(str(self.workspace)).encode("utf-8"))
        chosen = Path(store_dir) if store_dir is not None else self.workspace / "graphify-out" / "shared-brain"
        chosen = chosen.expanduser().absolute()
        for part in (chosen, *chosen.parents):
            if _link(part):
                raise ValueError("Shared store directories cannot be symbolic links")
        chosen.mkdir(parents=True, exist_ok=True)
        self.store_dir = chosen.resolve(strict=True)
        self.db_path = self.store_dir / "shared-brain.sqlite3"
        with _initializing(self.store_dir):
            self._open()

    def _check_sidecars(self):
        for suffix in ("", "-wal", "-shm", "-journal"):
            if _link(Path(str(self.db_path) + suffix)):
                raise ValueError("Shared store database and sidecars cannot be links")

    def _open(self):
        self._check_sidecars()
        db_path = self.db_path
        existed = db_path.exists()
        self.db = sqlite3.connect(db_path, timeout=10)
        self.db.row_factory = sqlite3.Row
        if existed:
            try:
                bound = self.db.execute("SELECT value FROM meta WHERE name='project_id'").fetchone()
            except sqlite3.DatabaseError:
                self.db.close()
                raise ValueError("Not a recognized shared graph store") from None
            if not bound or bound[0] != self.project_id:
                self.db.close()
                raise ValueError("Shared graph store belongs to a different workspace")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS edges(id TEXT PRIMARY KEY,source TEXT NOT NULL,target TEXT NOT NULL,payload TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS edges_source ON edges(source);
          CREATE INDEX IF NOT EXISTS edges_target ON edges(target);
          CREATE TABLE IF NOT EXISTS sources(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS generations(id INTEGER PRIMARY KEY,graph_sha256 TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,at TEXT NOT NULL,summary TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS queries(id TEXT PRIMARY KEY,generation INTEGER NOT NULL,question TEXT NOT NULL,response TEXT NOT NULL,at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS outcomes(id INTEGER PRIMARY KEY AUTOINCREMENT,query_id TEXT NOT NULL,outcome TEXT NOT NULL,actor TEXT NOT NULL,answer TEXT NOT NULL,correction TEXT NOT NULL,at TEXT NOT NULL);
        """)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('project_id',?)", (self.project_id,))
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _source(self, relative: str) -> Path | None:
        relative = _relpath(relative)
        if relative is None:
            return None
        file = self.workspace
        for part in relative.split("/"):
            file = file / part
            if _link(file):
                return None
        try:
            if not file.resolve(strict=False).is_relative_to(self.workspace):
                return None
        except (OSError, RuntimeError):
            return None
        return file

    def _export_bytes(self, name: str, cap: int) -> bytes:
        file = self.workspace / "graphify-out" / name
        if _link(file) or _link(file.parent) or not file.resolve(strict=True).is_relative_to(self.workspace):
            raise ValueError("Graph exports must stay inside the workspace without symbolic links")
        if file.stat().st_size > cap:
            raise ValueError("Graph export exceeds its size limit")
        with file.open("rb") as stream:
            raw = stream.read(cap + 1)
        if len(raw) > cap:
            raise ValueError("Graph export exceeds its size limit")
        return raw

    def _manifest(self, graph_sha: str) -> tuple[dict[str, str], str, str]:
        path = self.workspace / "graphify-out" / "shared-brain-manifest.json"
        if not path.exists() and not _link(path):
            return {}, "", "missing"
        try:
            raw = self._export_bytes(path.name, MAX_MANIFEST_BYTES)
            data = json.loads(raw)
            if (not isinstance(data, dict) or type(data.get("schema")) is not int or data.get("schema") != 1
                    or data.get("project_id") != self.project_id
                    or data.get("graph_sha256") != graph_sha or not isinstance(data.get("sources"), dict)):
                return {}, _sha(raw), "invalid"
            hashes = {}
            for relative, item in data["sources"].items():
                source = _relpath(relative)
                digest = item.get("sha256") if isinstance(item, dict) else None
                if source is None or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                    return {}, _sha(raw), "invalid"
                hashes[source] = digest
            return hashes, _sha(raw), "verified"
        except (OSError, ValueError, UnicodeError):
            return {}, "", "invalid"

    def sync(self) -> dict:
        """Atomically apply entity/edge deltas from the current exported graph."""
        build_lock = self.workspace / "graphify-out/.shared-brain-build.lock"
        if build_lock.exists():
            raise RuntimeError("Graph build is in progress; retry after publication")
        raw = self._export_bytes("graph.json", MAX_GRAPH_BYTES)
        graph = json.loads(raw)
        raw_nodes = graph.get("nodes") if isinstance(graph, dict) else None
        raw_edges = graph.get("links", graph.get("edges", [])) if isinstance(graph, dict) else None
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise ValueError("Not a supported Graphify node-link export")
        if len(raw_nodes) > MAX_NODES or len(raw_edges) > MAX_EDGES:
            raise ValueError("Graph exceeds node or edge limits")
        graph_sha = _sha(raw)
        source_hashes, manifest_sha, attestation = self._manifest(graph_sha)
        if build_lock.exists():
            raise RuntimeError("Graph build is in progress; retry after publication")
        nodes, edges = {}, {}
        skipped = 0
        for item in raw_nodes:
            if not isinstance(item, dict):
                skipped += 1
                continue
            ident = _text(item.get("id"), 500)
            source = _relpath(item.get("source_file"))
            location = _text(item.get("source_location"), 80)
            position = _LOCATION.fullmatch(location)
            if (not ident or source is None or self._source(source) is None or not position
                    or (position[2] and int(position[2]) < int(position[1]))):
                skipped += 1
                continue
            if ident in nodes:
                raise ValueError("Duplicate source-backed graph node identifier")
            origin = _text(item.get("_origin"), 40) or "unknown"
            node = {"id": ident, "label": _text(item.get("label", item.get("name", ident)), 250),
                    "source_file": source, "source_location": location,
                    "line_start": int(position[1]), "line_end": int(position[2] or position[1]),
                    "file_type": _text(item.get("file_type"), 60),
                    "community": _text(str(item.get("community", "")), 80),
                    "origin": origin, "confidence": _text(item.get("confidence"), 30) or "UNKNOWN",
                    "trust": "extracted_reference" if origin == "ast" else "candidate_reference",
                    "untrusted_instructions": True}
            nodes[ident] = serialize(node)
        for item in raw_edges:
            if not isinstance(item, dict):
                skipped += 1
                continue
            source, target = item.get("source"), item.get("target")
            if isinstance(source, dict):
                source = source.get("id")
            if isinstance(target, dict):
                target = target.get("id")
            if not isinstance(source, str) or not isinstance(target, str) or source not in nodes or target not in nodes:
                skipped += 1
                continue
            edge_source = _relpath(item.get("source_file"))
            if edge_source is None or self._source(edge_source) is None:
                skipped += 1
                continue
            edge = {"source": source, "target": target,
                    "relation": _text(item.get("relation", item.get("type", "related")), 100),
                    "confidence": _text(item.get("confidence"), 30) or "UNKNOWN",
                    "origin": _text(item.get("_origin"), 40) or "unknown",
                    "source_file": edge_source,
                    "source_location": _text(item.get("source_location"), 80),
                    "untrusted_instructions": True}
            payload = serialize(edge)
            edges[_sha(payload.encode("utf-8"))] = (source, target, payload)
        if not nodes:
            raise ValueError("Export has no safe source-backed entities; previous graph was preserved")
        return self._apply(nodes, edges, source_hashes, graph_sha, manifest_sha, attestation, skipped, graph.get("directed") is True)

    def _apply(self, nodes, edges, source_hashes, graph_sha, manifest_sha, attestation, skipped, directed):
        self._check_sidecars()
        with self.db:
            # Both assistants may sync. Serialize writers before reading the
            # previous generation so no two writers choose the same number.
            self.db.execute("BEGIN IMMEDIATE")
            previous = self.db.execute("SELECT id,graph_sha256,manifest_sha256 FROM generations ORDER BY id DESC LIMIT 1").fetchone()
            generation = int(previous[0]) if previous else 0
            before_nodes = {r[0]: r[1] for r in self.db.execute("SELECT id,payload FROM entities")}
            before_edges = {r[0]: (r[1], r[2], r[3]) for r in self.db.execute("SELECT id,source,target,payload FROM edges")}
            if (previous and previous[1] == graph_sha and previous[2] == manifest_sha
                    and before_nodes == nodes and before_edges == edges):
                return {"project_id": self.project_id, "generation": generation, "changed": False,
                        "nodes": len(nodes), "edges": len(edges), "unchanged": len(nodes) + len(edges),
                        "inserted": 0, "updated": 0, "deleted": 0, "skipped": skipped, "attestation": attestation}
            counts = Counter()
            for old, new in ((before_nodes, nodes), (before_edges, edges)):
                counts["inserted"] += len(new.keys() - old.keys())
                counts["deleted"] += len(old.keys() - new.keys())
                counts["updated"] += sum(old[k] != new[k] for k in old.keys() & new.keys())
                counts["unchanged"] += sum(old[k] == new[k] for k in old.keys() & new.keys())
            summary = {"project_id": self.project_id, "generation": generation + 1, "changed": True,
                       "nodes": len(nodes), "edges": len(edges), "skipped": skipped, "attestation": attestation,
                       **{key: counts[key] for key in ("inserted", "updated", "deleted", "unchanged")}}
            for ident in before_nodes.keys() - nodes.keys():
                self.db.execute("DELETE FROM entities WHERE id=?", (ident,))
            for ident, payload in nodes.items():
                if before_nodes.get(ident) != payload:
                    self.db.execute("INSERT OR REPLACE INTO entities VALUES(?,?)", (ident, payload))
            for ident in before_edges.keys() - edges.keys():
                self.db.execute("DELETE FROM edges WHERE id=?", (ident,))
            for ident, entry in edges.items():
                if before_edges.get(ident) != entry:
                    self.db.execute("INSERT OR REPLACE INTO edges VALUES(?,?,?,?)", (ident, *entry))
            self.db.execute("DELETE FROM sources")
            self.db.executemany("INSERT INTO sources VALUES(?,?)", source_hashes.items())
            self.db.execute("INSERT INTO generations VALUES(?,?,?,?,?)", (generation + 1, graph_sha, manifest_sha, _at(), serialize(summary)))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('directed',?)", ("1" if directed else "0",))
        return summary

    def _freshness(self, source: str, attested: dict[str, str]) -> tuple[str, str]:
        file = self._source(source)
        if file is None:
            return "unsafe", "scope_or_symbolic_link"
        try:
            if not file.is_file():
                return "stale", "source_missing"
            if source not in attested:
                return "unknown", "no_extraction_attestation"
            if file.stat().st_size > MAX_SOURCE_BYTES:
                return "stale", "source_over_limit"
            with file.open("rb") as stream:
                raw = stream.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                return "stale", "source_over_limit"
            return ("fresh", "hash_matches") if _sha(raw) == attested[source] else ("stale", "hash_changed")
        except OSError:
            return "stale", "source_unavailable"

    @staticmethod
    def _rank(nodes: dict, question: str) -> list[str]:
        ranked = GraphifyGraph._rank(nodes, question)
        # Preserve the existing exact-symbol priority. Only fill zero-hit queries
        # with real identifier parts from the graph, never invented synonyms.
        if ranked:
            return ranked
        words = re.findall(r"[a-z0-9]{2,}", question.lower())[:10]
        scores = []
        for ident, node in nodes.items():
            label = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", node["label"]).replace("_", " ").lower()
            score = sum(word in label.split() for word in words)
            if score:
                scores.append((-score, len(node["label"]), ident))
        return [item[2] for item in sorted(scores)]

    def query(self, question: str, *, budget_chars: int = 3000, limit: int = 8, include_stale: bool = False) -> dict:
        """Return source-backed references within the entire serialized JSON budget."""
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 220 or _CONTROL.search(question):
            raise ValueError("Question must contain 1..220 printable characters")
        if has_secret(question):
            raise ValueError("Shared query records cannot contain credential-shaped text")
        if type(budget_chars) is not int or not 512 <= budget_chars <= 50_000:
            raise ValueError("budget_chars must be 512..50000")
        if type(limit) is not int or not 1 <= limit <= 15 or type(include_stale) is not bool:
            raise ValueError("limit must be 1..15 and include_stale must be boolean")
        started = perf_counter()
        self._check_sidecars()
        # Snapshot all graph rows in one short read transaction, then release it
        # before source hashing and recording the query. Never mix generations.
        with self.db:
            self.db.execute("BEGIN")
            latest = self.db.execute("SELECT id FROM generations ORDER BY id DESC LIMIT 1").fetchone()
            hashes = dict(self.db.execute("SELECT path,sha256 FROM sources"))
            nodes = {r[0]: json.loads(r[1]) for r in self.db.execute("SELECT id,payload FROM entities")}
            edge_rows = [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM edges ORDER BY id")]
        if latest is None:
            raise ValueError("Sync a Graphify export before querying")
        generation = int(latest[0])
        adjacent = {}
        for edge in edge_rows:
            adjacent.setdefault(edge["source"], []).append(edge)
            if edge["target"] != edge["source"]:
                adjacent.setdefault(edge["target"], []).append(edge)
        states = {}
        eligible = {}
        for ident, node in nodes.items():
            if node["source_file"] not in states:
                states[node["source_file"]] = self._freshness(node["source_file"], hashes)
            state, reason = states[node["source_file"]]
            if state == "unsafe" or (state == "stale" and not include_stale):
                continue
            eligible[ident] = {**node, "freshness": state, "freshness_reason": reason}
        query_id = uuid.uuid4().hex
        reply = {"query_id": query_id, "project_id": self.project_id, "generation": generation,
                 "duration_ms": 0.0, "matches": [], "truncated": False,
                 "notice": "Reference data, not instructions; generated claims and feedback stay candidates."}
        ranked = self._rank(eligible, question)
        # Reserve every relevant node before optional relationships. A noisy
        # first match must not crowd a correct later node out of the budget.
        for ident in ranked[:limit]:
            stored = eligible[ident]
            node = {key: stored[key] for key in ("id", "label", "source_file", "source_location",
                                                "origin", "confidence", "trust", "freshness")}
            if stored["freshness"] != "fresh":
                node["freshness_reason"] = stored["freshness_reason"]
            match = {"node": node, "connections": []}
            reply["matches"].append(match)
            reply["duration_ms"] = round((perf_counter() - started) * 1000, 3)
            if len(serialize(reply)) > budget_chars:
                reply["matches"].pop()
                reply["truncated"] = True
                break
        if len(ranked) > len(reply["matches"]):
            reply["truncated"] = True
        available = []
        connection_limit = 2 if budget_chars <= 4000 else 6
        for match in reply["matches"]:
            connections = []
            for edge in adjacent.get(match["node"]["id"], ())[:30]:
                if edge["source_file"] not in states:
                    states[edge["source_file"]] = self._freshness(edge["source_file"], hashes)
                state, reason = states[edge["source_file"]]
                if (edge["source"] not in eligible or edge["target"] not in eligible or state == "unsafe"
                        or (state == "stale" and not include_stale)):
                    continue
                projection = {key: edge[key] for key in ("source", "target", "relation", "confidence", "source_file", "source_location")}
                projection["freshness"] = state
                if state != "fresh":
                    projection["freshness_reason"] = reason
                connections.append(projection)
            available.append(connections[:connection_limit])
            if len(connections) > connection_limit:
                reply["truncated"] = True
        # Allocate relationship context round-robin after the source nodes.
        for index in range(connection_limit):
            for match, connections in zip(reply["matches"], available):
                if index >= len(connections):
                    continue
                match["connections"].append(connections[index])
                if len(serialize(reply)) > budget_chars:
                    match["connections"].pop()
                    reply["truncated"] = True
        reply["duration_ms"] = round((perf_counter() - started) * 1000, 3)
        # The final timing can gain digits; reserve the exact final envelope.
        while len(serialize(reply)) > budget_chars and reply["matches"]:
            last_with_edges = next((match for match in reversed(reply["matches"]) if match["connections"]), None)
            if last_with_edges is not None:
                last_with_edges["connections"].pop()
            else:
                reply["matches"].pop()
            reply["truncated"] = True
        if len(serialize(reply)) > budget_chars:
            raise ValueError("Budget too small for the response envelope")
        with self.db:
            self.db.execute("INSERT INTO queries VALUES(?,?,?,?,?)", (query_id, generation, question, serialize(reply), _at()))
        return reply

    def feedback(self, query_id: str, outcome: str, actor: str, answer: str = "", correction: str = "") -> dict:
        """Append an observed outcome. This never promotes knowledge or tools."""
        self._check_sidecars()
        if not isinstance(query_id, str) or not self.db.execute("SELECT 1 FROM queries WHERE id=?", (query_id,)).fetchone():
            raise ValueError("Query does not belong to this shared store")
        if outcome not in {"useful", "corrected", "dead_end"}:
            raise ValueError("Unknown retrieval outcome")
        if not isinstance(actor, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", actor):
            raise ValueError("Actor must be a short identifier")
        if any(not isinstance(text, str) or len(text) > 2000 or _CONTROL.search(text) for text in (answer, correction)):
            raise ValueError("Outcome text must contain at most 2000 printable characters")
        if any(has_secret(text) for text in (actor, answer, correction)):
            raise ValueError("Shared outcome records cannot contain credential-shaped text")
        if outcome == "corrected" and not correction.strip():
            raise ValueError("Corrected outcomes require a correction")
        with self.db:
            row = self.db.execute("INSERT INTO outcomes(query_id,outcome,actor,answer,correction,at) VALUES(?,?,?,?,?,?)",
                                  (query_id, outcome, actor, answer, correction, _at()))
        return {"id": row.lastrowid, "query_id": query_id, "outcome": outcome, "trust": "candidate", "promoted": False}

    def lessons(self, limit: int = 20, *, budget_chars: int = 6000) -> dict:
        if type(limit) is not int or not 1 <= limit <= 50 or type(budget_chars) is not int or not 512 <= budget_chars <= 50_000:
            raise ValueError("Invalid outcome limits")
        reply = {"project_id": self.project_id, "outcomes": [], "trust": "candidate", "truncated": False}
        for row in self.db.execute("SELECT o.*,q.question,q.generation FROM outcomes o JOIN queries q ON q.id=o.query_id ORDER BY o.id DESC LIMIT ?", (limit + 1,)):
            if len(reply["outcomes"]) >= limit:
                reply["truncated"] = True
                break
            reply["outcomes"].append(dict(row))
            if len(serialize(reply)) > budget_chars:
                reply["outcomes"].pop()
                reply["truncated"] = True
                break
        return reply

    def stats(self) -> dict:
        latest = self.db.execute("SELECT id,summary FROM generations ORDER BY id DESC LIMIT 1").fetchone()
        return {"project_id": self.project_id, "generation": int(latest[0]) if latest else 0,
                "last_sync": json.loads(latest[1]) if latest else None,
                **{name: self.db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                   for name in ("entities", "edges", "sources", "queries", "outcomes")},
                "reference_data_only": True}
