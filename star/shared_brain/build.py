"""Deterministic, scoped Graphify extraction with a bound freshness manifest.

Graphify remains the graph generator. Its per-file AST cache provides incremental
parsing; all selected files participate in relationship resolution on every build.
No model, network, credential, or semantic extraction backend is invoked.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import time
import uuid

DEFAULT_SOURCES = (
    "star/graphify_bridge.py", "star/intelligence.py", "star/knowledge.py",
    "star/memory.py", "star/learning.py", "star/lessons.py", "star/lesson_digest.py",
    "star/tool_workshop.py", "star/selfbuild.py", "star/orchestration.py",
    "star/agent.py", "star/evals.py", "star/brain_router.py", "star/mcp_connections.py",
    "star/shared_brain/store.py", "star/shared_brain/improve.py",
    "star/shared_brain/build.py", "star/shared_brain/__main__.py",
    "star/shared_brain/protocol.py", "star/shared_brain/coordination.py",
)
EXTENSIONS = frozenset({".py", ".ts", ".tsx", ".js", ".mjs", ".lua", ".luau"})
MAX_SOURCE_BYTES = 500_000
MAX_CORPUS_BYTES = 12_000_000


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_bytes(path: Path) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Source exceeds the extraction size limit")
    return data


def project_id(workspace: Path) -> str:
    return digest(os.path.normcase(str(workspace.resolve())).encode("utf-8"))


def no_links(path: Path, root: Path) -> None:
    for part in (path, *path.parents):
        if part == root.parent:
            break
        reparse = (getattr(part.lstat(), "st_file_attributes", 0)
                   & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)) if part.exists() else 0
        if reparse or part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Project graph paths cannot follow links")


def source_path(root: Path, name: str) -> Path:
    """A source allowlist is data, never a grant to read another project."""
    if not isinstance(name, str):
        raise ValueError("Source name must be a relative string")
    p = PurePosixPath(name)
    if (name != p.as_posix() or p.is_absolute()
            or ".." in p.parts or "\\" in name or ":" in name
            or any(part.startswith(".") for part in p.parts)
            or p.suffix not in EXTENSIONS
            or p.parts[0] not in {"star", "frontend", "server"}
            or any(word in name.casefold() for word in ("credential", "secret", "password", "private_key"))):
        raise ValueError("Source must be an allowed relative project code path")
    path = root / name
    no_links(path, root)
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError("Source is missing or outside the selected project")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Source exceeds the extraction size limit")
    return path


def build(workspace: Path, sources: list[str] | None = None) -> dict:
    root = workspace.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Select a project directory")
    selected = list(sources) if sources is not None else [s for s in DEFAULT_SOURCES if (root / s).is_file()]
    if not selected or len(selected) > 256 or len(selected) != len(set(selected)):
        raise ValueError("Select 1–256 distinct code sources")
    paths = {name: source_path(root, name) for name in sorted(selected)}
    data = {name: source_bytes(path) for name, path in paths.items()}
    if sum(map(len, data.values())) > MAX_CORPUS_BYTES:
        raise ValueError("Selected corpus exceeds 12 MB")
    out = root / "graphify-out"
    no_links(out, root)
    if not out.resolve().is_relative_to(root):
        raise ValueError("Graph output must stay inside this project")
    out.mkdir(exist_ok=True)
    lock = out / ".shared-brain-build.lock"
    no_links(lock, root)
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    started = time.perf_counter()
    try:
        os.close(fd)
        # Optional dependency, imported only by an operator-requested build.
        from graphify.extract import extract
        from graphify.build import build_from_json
        from graphify.export import to_json

        stage = out / "shared-brain-build"
        no_links(stage, root)
        if not stage.resolve().is_relative_to(out):
            raise ValueError("Extraction staging must stay inside project graph output")
        stage.mkdir(exist_ok=True)
        previous_path = out / "shared-brain-manifest.json"
        no_links(previous_path, root)
        previous = {}
        if previous_path.is_file() and not previous_path.is_symlink():
            try:
                with previous_path.open("rb") as handle:
                    manifest_bytes = handle.read(1_000_001)
                if len(manifest_bytes) > 1_000_000:
                    raise ValueError("Prior manifest exceeds the read budget")
                previous = json.loads(manifest_bytes)
            except (ValueError, OSError):
                pass
        old = previous.get("sources", {}) if previous.get("project_id") == project_id(root) else {}
        changed = [name for name, content in data.items() if old.get(name, {}).get("sha256") != digest(content)]
        deleted = sorted(set(old) - set(data))
        for name, content in data.items():
            dest = stage / name
            no_links(dest, root)
            if not dest.resolve().is_relative_to(stage):
                raise ValueError("Unsafe staging source")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.is_file() or source_bytes(dest) != content:
                dest.write_bytes(content)
        # The selected list, not a directory scan, is passed to official Graphify.
        with redirect_stdout(io.StringIO()):
            extraction = extract([stage / n for n in data], cache_root=stage, root=stage,
                                 parallel=False, max_workers=1)
            graph = build_from_json(extraction, root=stage, directed=True)
        if not graph.number_of_nodes():
            raise ValueError("Extraction is empty; prior graph preserved")
        if any(source_bytes(path) != data[name] for name, path in paths.items()):
            raise ValueError("Sources changed during extraction; prior graph preserved")
        commit = None
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                                timeout=10, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            commit = result.stdout.strip()
        temp_graph = out / ".shared-brain-graph.tmp"
        no_links(temp_graph, root)
        no_links(out / "graph.json", root)
        # A fresh temporary output permits deliberate source deletion without
        # disabling the shrink guard on another graph.
        if temp_graph.exists():
            temp_graph.unlink()
        with redirect_stdout(io.StringIO()):
            to_json(graph, {}, str(temp_graph), built_at_commit=commit)
        graph_bytes = temp_graph.read_bytes()
        manifest = {"schema": 1, "project_id": project_id(root), "graph_sha256": digest(graph_bytes),
                    "sources": {name: {"sha256": digest(content)} for name, content in data.items()},
                    "generator": "graphify AST", "semantic_extraction": False,
                    "input_tokens": 0, "output_tokens": 0}
        temp_manifest = out / ".shared-brain-manifest.tmp"
        no_links(temp_manifest, root)
        if temp_manifest.exists():
            temp_manifest.unlink()
        with temp_manifest.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        graph_path = out / "graph.json"
        backup = out / (".shared-brain-previous-" + uuid.uuid4().hex)
        had_graph = graph_path.exists()
        if had_graph:
            os.replace(graph_path, backup)
        try:
            os.replace(temp_graph, graph_path)
            os.replace(temp_manifest, previous_path)
        except OSError:
            if had_graph:
                os.replace(backup, graph_path)
            else:
                graph_path.unlink(missing_ok=True)
            raise
        if had_graph:
            try:
                backup.unlink()
            except OSError:
                pass  # A leftover local backup does not invalidate publication.
        return {"sources": len(data), "changed_sources": len(changed), "reused_sources": len(data)-len(changed),
                "deleted_sources": len(deleted), "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(),
                "duration_ms": round((time.perf_counter()-started)*1000, 3),
                "graph_sha256": manifest["graph_sha256"], "input_tokens": 0, "output_tokens": 0}
    finally:
        lock.unlink(missing_ok=True)
