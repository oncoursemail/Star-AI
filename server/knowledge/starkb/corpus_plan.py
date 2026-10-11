"""Read-only planning and explicit, separate candidate-index construction. No fetch/model calls."""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import quote

from .corpus_formats import parse_source
from .corpus_manifest import CorpusError, digest, git_read, read_manifest, tracked_read, verify_snapshot
from . import store
from .quiet import wait_while_locked


def _quiet() -> None:
    wait_while_locked(log=lambda message: print(message, file=sys.stderr))

MAX_PREVIOUS_BYTES = 256 * 1024 * 1024


def readonly_index(path: Path) -> sqlite3.Connection:
    if not path.is_file() or path.stat().st_size > MAX_PREVIOUS_BYTES:
        raise CorpusError("previous index is missing or exceeds 256 MiB")
    if Path(str(path) + "-wal").exists() or Path(str(path) + "-shm").exists():
        raise CorpusError("use a stable checkpointed index snapshot, not a live WAL index")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def _previous(path: Path | None) -> dict:
    if path is None:
        return {"files": {}, "sources": {}, "policy": {}, "sha256": None}
    with closing(readonly_index(path)) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"sources", "docs", "chunks", "meta", "embeddings"} <= tables:
            raise CorpusError("previous index is not a supported knowledge snapshot")
        sources = {r["name"]: dict(r) for r in db.execute("SELECT * FROM sources")}
        if len(sources) > 12:
            raise CorpusError("previous source count exceeds candidate bounds")
        files = {}
        if "candidate_files" in tables:
            for row in db.execute("SELECT source,path,sha256 FROM candidate_files"):
                files[(row[0], row[1])] = row[2]
                if len(files) > 10000:
                    raise CorpusError("previous inventory exceeds candidate bounds")
        policies = {}
        if "candidate_policies" in tables:
            policies = dict(db.execute("SELECT source,policy_sha FROM candidate_policies"))
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            _quiet()
            sha.update(piece)
    return {"files": files, "sources": sources, "policy": policies, "sha256": sha.hexdigest()}


def prepare(manifest: Path, sources_dir: Path, *, previous: Path | None = None,
            selected: list[str] | None = None) -> tuple[dict, dict, dict, dict]:
    config = read_manifest(manifest)
    before = _previous(previous)
    known = {s["name"] for s in config["sources"]}
    if selected is not None and (len(set(selected)) != len(selected) or not set(selected) <= known):
        raise CorpusError("source selection contains duplicate/unknown IDs")
    report = {"candidate_only": True, "network": False, "model_calls": False,
              "manifest_sha256": digest(config), "previous_sha256": before["sha256"],
              "preserved_sources": sorted(set(before["sources"]) - set(selected or known)), "sources": []}
    parsed = {}
    metadata = {}
    ready = {}
    global_bytes = global_chunks = 0
    for source in config["sources"]:
        _quiet()
        name = source["name"]
        if selected is not None and name not in selected:
            continue
        entry = {"name": name, "status": "unavailable", "revision": source.get("revision"),
                 "permission": source.get("permission"), "warnings": []}
        report["sources"].append(entry)
        try:
            info = verify_snapshot(source, sources_dir)
            documents = []
            inventory = []
            total_bytes = chunks = 0
            for path in source["paths"]:
                _quiet()
                raw = tracked_read(info["repo"], path, source["limits"]["file_bytes"])
                total_bytes += len(raw)
                if total_bytes > source["limits"]["total_bytes"]:
                    raise CorpusError("selected source exceeds total byte bound")
                url = source["repo"].removesuffix(".git") + "/blob/" + info["commit"] + "/" + quote(path, safe="/")
                document = parse_source(raw, path, url)
                chunks += len(document.doc.chunks)
                if chunks > source["limits"]["chunks"]:
                    raise CorpusError("selected source exceeds chunk bound")
                documents.append(document)
                inventory.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(),
                                  "bytes": len(raw), "chunks": len(document.doc.chunks),
                                  "source_kind": document.spans[0]["source_kind"],
                                  "warnings": document.warnings, "url": url})
            if git_read(info["repo"], "rev-parse", "HEAD") != info["commit"] or git_read(
                    info["repo"], "status", "--porcelain=v1", "--untracked-files=all"):
                raise CorpusError("snapshot changed while its selected files were inspected")
            global_bytes += total_bytes
            global_chunks += chunks
            if global_bytes > 64 * 1024 * 1024 or global_chunks > 50000:
                raise CorpusError("combined candidate exceeds 64 MiB / 50000 chunks")
            old = {p: h for (n, p), h in before["files"].items() if n == name}
            current = {f["path"]: f["sha256"] for f in inventory}
            policy_sha = digest({k: v for k, v in source.items() if k not in ("revision", "branch")})
            entry.update(status="verified-local", verification=info["verification"], files=inventory,
                         bytes=total_bytes, chunks=chunks, policy_sha256=policy_sha,
                         added=sorted(set(current) - set(old)), removed=sorted(set(old) - set(current)),
                         changed=sorted(p for p in set(current) & set(old) if current[p] != old[p]),
                         unchanged=sorted(p for p in set(current) & set(old) if current[p] == old[p]),
                         policy_changed=before["policy"].get(name) != policy_sha,
                         attribution=source["attribution"], prose_licence=source["prose_licence"],
                         code_licence=source["code_licence"], compatibility=source["compatibility"])
            parsed[name] = documents
            metadata[name] = info
            ready[name] = source
        except (CorpusError, OSError, UnicodeError, sqlite3.Error, subprocess.SubprocessError) as exc:
            entry["error"] = str(exc)
    report["preserved_sources"] = sorted(set(before["sources"]) - set(ready))
    report["plan_sha256"] = digest(report)
    return report, parsed, metadata, ready


def plan(manifest: Path, sources_dir: Path, *, previous: Path | None = None,
         selected: list[str] | None = None) -> dict:
    """No writes, network, models, checkout changes or Git object creation."""
    return prepare(manifest, sources_dir, previous=previous, selected=selected)[0]


def build_candidate(manifest: Path, sources_dir: Path, output: Path, *, selected: list[str],
                    previous: Path | None = None) -> dict:
    """Create a new candidate file; preserve other sources and never replace a supplied DB."""
    if not selected:
        raise CorpusError("build requires explicit source IDs")
    output = output.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise CorpusError("candidate output must be a new file in an existing directory")
    if previous is not None and output.resolve() == previous.resolve():
        raise CorpusError("candidate output cannot be the previous index")
    report, parsed, metadata, ready = prepare(manifest, sources_dir, previous=previous, selected=selected)
    errors = [e for e in report["sources"] if e["status"] != "verified-local"]
    if errors or set(ready) != set(selected):
        raise CorpusError("candidate not built: " + "; ".join(e["name"] + ": " + e.get("error", "unavailable") for e in errors))
    if previous is not None and _previous(previous)["sha256"] != report["previous_sha256"]:
        raise CorpusError("previous index changed during planning")
    # All file writes are inside this explicit output directory; only the final exclusive
    # link publishes a file. It fails atomically if somebody creates the target meanwhile.
    with tempfile.TemporaryDirectory(prefix=".corpus-candidate-", dir=output.parent) as temporary:
        temp = Path(temporary)
        candidate = temp / "candidate.sqlite3"
        if previous is not None:
            source_db = readonly_index(previous)
            target_db = sqlite3.connect(candidate)
            try:
                source_db.backup(target_db)
            finally:
                source_db.close()
                target_db.close()
        db = store.connect(candidate)
        old_counts = dict(db.execute("SELECT d.source,COUNT(*) FROM chunks c JOIN docs d ON d.id=c.doc_id GROUP BY d.source"))
        old_paths = {name: {r[0] for r in db.execute("SELECT path FROM docs WHERE source=?", (name,))}
                     for name in selected}
        db.close()
        for name in selected:
            _quiet()
            new_count = sum(len(d.doc.chunks) for d in parsed[name])
            if old_counts.get(name, 0) and new_count < old_counts[name] * store.MIN_REBUILD_RATIO:
                raise CorpusError("candidate would remove over 20% of " + name + " chunks; review scope first")
            remaining = old_paths[name] & {d.doc.path for d in parsed[name]}
            if old_paths[name] and len(remaining) < len(old_paths[name]) * store.MIN_REBUILD_RATIO:
                raise CorpusError("candidate would remove over 20% of " + name + " source paths; review scope first")
        adapted = {"sources": [{**s, "content_root": "", "licence": s["prose_licence"] +
                   "; code: " + s["code_licence"]} for s in ready.values()]}
        adapted_path = temp / "build-manifest.json"
        adapted_path.write_text(json.dumps(adapted), encoding="utf-8")
        walkers = {name: (lambda _root, _base, docs=documents: (d.doc for d in docs))
                   for name, documents in parsed.items()}
        stats = store.build(candidate, sources_dir, adapted_path, walkers=walkers, source_metadata=metadata,
                            preserve_other_sources=True)
        db = store.connect(candidate)
        try:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS candidate_files(source TEXT,path TEXT,sha256 TEXT,metadata TEXT,
                    PRIMARY KEY(source,path));
                CREATE TABLE IF NOT EXISTS candidate_chunks(chunk_id INTEGER PRIMARY KEY,metadata TEXT);
                CREATE TABLE IF NOT EXISTS candidate_policies(source TEXT PRIMARY KEY,policy_sha TEXT,metadata TEXT);
            """)
            for entry in report["sources"]:
                _quiet()
                name = entry["name"]
                # IDs can be reused when the affected source is replaced. Remove metadata
                # that is absent or belongs to updated sources before assigning new spans.
                db.execute("DELETE FROM candidate_chunks WHERE chunk_id NOT IN (SELECT id FROM chunks)")
                db.execute("DELETE FROM candidate_files WHERE source=?", (name,))
                db.execute("INSERT OR REPLACE INTO candidate_policies VALUES(?,?,?)",
                           (name, entry["policy_sha256"], json.dumps(ready[name])))
                by_path = {d.doc.path: d for d in parsed[name]}
                for file in entry["files"]:
                    _quiet()
                    db.execute("INSERT INTO candidate_files VALUES(?,?,?,?)",
                               (name, file["path"], file["sha256"], json.dumps(file)))
                    rows = db.execute("SELECT c.id,c.ord FROM chunks c JOIN docs d ON d.id=c.doc_id WHERE d.source=? AND d.path=? ORDER BY c.ord",
                                      (name, file["path"])).fetchall()
                    for row, span in zip(rows, by_path[file["path"]].spans):
                        db.execute("INSERT OR REPLACE INTO candidate_chunks VALUES(?,?)", (row[0], json.dumps({
                            **span, "source": name, "path": file["path"], "source_sha256": file["sha256"],
                            "warnings": file["warnings"], "prose_licence": ready[name]["prose_licence"],
                            "code_licence": ready[name]["code_licence"], "attribution": ready[name]["attribution"],
                            "compatibility": ready[name]["compatibility"]})))
            db.execute("INSERT OR REPLACE INTO meta VALUES('candidate_only','true')")
            db.execute("INSERT OR REPLACE INTO meta VALUES('candidate_plan',?)", (json.dumps(report),))
            db.commit()
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            db.close()
        # Verify input snapshots a second time before making the completed candidate visible.
        fresh = plan(manifest, sources_dir, previous=previous, selected=selected)
        if fresh["plan_sha256"] != report["plan_sha256"]:
            raise CorpusError("inputs changed during build; candidate was discarded")
        os.link(candidate, output)  # exclusive destination; no os.replace / clobber
    return {"candidate_only": True, "output": str(output), "plan": report, "index": stats,
            "activated": False, "embedded_now": 0}
