"""Evidence-backed, read-only dependency graph for selected game-engine projects.

Godot text resources and Unity YAML/GUID assets are traced without launching any
editor, loading plugins, scanning outside the workspace, or treating project text
as instructions. Unreal binary .uasset dependencies require an approved editor.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from . import game_projects

MAX_FILES = 300
MAX_EDGES = 120
MAX_FILE_BYTES = 64_000
GODOT_PATH = re.compile(r'res://([A-Za-z0-9 _./@+\-]+)')
UNITY_GUID = re.compile(r'\bguid:\s*([0-9a-fA-F]{32})\b')
SCANNED = frozenset({".tscn", ".tres", ".gd", ".unity", ".prefab", ".asset",
                     ".mat", ".controller", ".anim", ".overridecontroller"})
UNITY_ASSETS = frozenset({".unity", ".prefab", ".asset", ".mat", ".controller",
                          ".anim", ".overridecontroller"})


def _read(workspace, file: Path) -> str | None:
    if file.is_symlink() or not file.is_file():
        return None
    try:
        if file.stat().st_size > MAX_FILE_BYTES:
            return None
        workspace.resolve(file.relative_to(workspace.root).as_posix())
        return file.read_text(encoding="utf-8-sig")
    except (ValueError, PermissionError, OSError, UnicodeError):
        return None


def _safe_target(workspace, project: Path, value: str) -> Path | None:
    # No URLs, platform paths, absolute paths, traversal, or secret files.
    if not value or len(value) > 260 or "\\" in value or ":" in value:
        return None
    if any(bit in ("", ".", "..") for bit in value.split("/")):
        return None
    try:
        result = workspace.resolve((project / value).relative_to(workspace.root).as_posix(),
                                   allow_missing=True)
    except (ValueError, PermissionError, OSError):
        return None
    return result if result.is_relative_to(project) else None


def inspect(workspace, path: str) -> dict:
    project = workspace.resolve(path)
    if not project.is_dir():
        raise ValueError("Choose a game-engine project directory")
    found = game_projects._engine(workspace, project)
    if found is None:
        raise ValueError("Project must have a recognized Godot, Unity or Unreal manifest")
    engine = found["engine"]
    entries = []
    # The existing walker caps paths, depth, symlinks and skipped generated folders.
    for file in game_projects._walk(workspace, project, depth=8, budget=game_projects.MAX_SCAN_ENTRIES):
        if file.suffix.lower() in SCANNED or file.suffix.lower() == ".meta":
            entries.append(file)
            if len(entries) >= MAX_FILES:
                break
    entries.sort(key=lambda file: file.relative_to(project).as_posix().casefold())
    edges: list[dict] = []
    missing: list[dict] = []
    notes: list[str] = []
    guid_to_asset: dict[str, str] = {}
    collisions = 0
    if engine == "unity":
        for file in entries:
            if file.suffix.lower() != ".meta":
                continue
            text = _read(workspace, file)
            if text is None:
                continue
            found_guid = UNITY_GUID.search(text)
            if found_guid is None:
                continue
            guid = found_guid.group(1).lower()
            asset = file.relative_to(project).as_posix()[:-5]  # strip .meta
            if guid in guid_to_asset and guid_to_asset[guid] != asset:
                collisions += 1
            else:
                guid_to_asset[guid] = asset

    examined = 0
    skipped = 0
    external_guids = 0
    for file in entries:
        suffix = file.suffix.lower()
        if suffix == ".meta":
            continue
        if engine == "godot" and suffix not in {".tscn", ".tres", ".gd"}:
            continue
        if engine == "unity" and suffix not in UNITY_ASSETS:
            continue
        if engine == "unreal":
            continue
        text = _read(workspace, file)
        if text is None:
            skipped += 1
            continue
        examined += 1
        source = file.relative_to(project).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if len(edges) >= MAX_EDGES:
                break
            if engine == "godot":
                targets = set(GODOT_PATH.findall(line[:4096]))
                for asset in sorted(targets):
                    # Strings such as inline IDs can contain punctuation; reject
                    # anything that cannot be safely resolved as an in-project path.
                    resolved = _safe_target(workspace, project, asset)
                    if resolved is None:
                        continue
                    exists = resolved.is_file() and not resolved.is_symlink()
                    item = {"from": source, "to": asset, "line": lineno,
                            "kind": "godot_res_path", "resolved": exists}
                    edges.append(item)
                    if not exists and len(missing) < 40:
                        missing.append(item)
                    if len(edges) >= MAX_EDGES:
                        break
            else:
                for guid in sorted({value.lower() for value in UNITY_GUID.findall(line[:4096])}):
                    target = guid_to_asset.get(guid)
                    # GUIDs may also come from installed packages or Unity itself.
                    if target is None:
                        external_guids += 1
                    edges.append({"from": source, "to": target, "guid": guid,
                                  "line": lineno, "kind": "unity_guid",
                                  "resolved_in_project": target is not None})
                    if len(edges) >= MAX_EDGES:
                        break
        if len(edges) >= MAX_EDGES:
            break

    if engine == "unreal":
        notes.append("Unreal .uasset and .umap dependency graphs require the installed Unreal Editor Asset Registry; no binary was parsed.")
        manifest = project / found["manifest"]
        parsed = _read(workspace, manifest)
        plugins = []
        if parsed is not None:
            try:
                conf = json.loads(parsed)
                if isinstance(conf, dict):
                    plugins = sorted({str(p.get("Name"))[:80] for p in conf.get("Plugins", [])
                                      if isinstance(p, dict) and isinstance(p.get("Name"), str)})[:32]
            except (TypeError, ValueError):
                notes.append("Unreal project manifest could not be parsed")
    else:
        plugins = []
    if engine == "unity":
        notes.append("Unresolved Unity GUIDs may refer to package or built-in assets, not broken project links.")
        notes.append("Only text/YAML references and locally scanned .meta mappings are counted; no Unity scene was loaded.")
    if engine == "godot":
        notes.append("Godot path references are static hints; uid:// resources and runtime-generated paths are not resolved.")
    if skipped:
        notes.append("Some oversized or unreadable files were skipped.")
    truncated = len(entries) >= MAX_FILES or len(edges) >= MAX_EDGES
    return {
        "engine": engine, "project_path": project.relative_to(workspace.root).as_posix() or ".",
        "read_only": True, "executed": False, "scan_limited": truncated,
        "files_selected": len(entries), "files_examined": examined,
        "files_skipped": skipped, "relationships": edges, "missing_local_resources": missing,
        "unity_external_or_unknown_guid_references": external_guids,
        "unity_duplicate_guid_mappings": collisions,
        "unreal_declared_plugins": plugins, "notes": notes,
        "notice": ("Static, bounded dependency evidence, not a full engine index or build result. "
                   "No editor, REA, debugger or third-party code ran."),
    }
