"""Offline policy for explicitly selected, locally verified documentation snapshots.

A matching origin URL is a local declaration, not cryptographic upstream authentication.
Licence hashes must be reviewed against upstream before preparing a usable manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlsplit

MAX_MANIFEST_BYTES = 256 * 1024
POLICIES = {
    "creator-docs": ("Roblox/creator-docs", ("content/en-us/",), "CC-BY-4.0", "MIT"),
    "luau-site": ("luau-lang/site", ("src/content/docs/", "src/content/news/"), "MIT", "MIT"),
    "godot-guides": ("godotengine/godot-docs", ("tutorials/scripting/", "tutorials/ui/", "tutorials/animation/"), "CC-BY-3.0", "CC-BY-3.0"),
    "godot-api": ("godotengine/godot-docs", ("classes/",), "MIT", "MIT"),
    "godot-xml": ("godotengine/godot", ("doc/classes/",), "MIT", "MIT"),
    "dotnet-docs": ("dotnet/docs", ("docs/csharp/", "docs/core/testing/", "docs/standard/"), "CC-BY-4.0", "MIT"),
    "mdn-content": ("mdn/content", ("files/en-us/web/",), "CC-BY-SA-2.5", "CC0-1.0-or-MIT-by-history"),
    "typescript-handbook": ("microsoft/TypeScript-Website", ("packages/documentation/copy/en/",), "CC-BY-4.0", "MIT"),
    "python-docs": ("python/cpython", ("Doc/tutorial/", "Doc/reference/", "Doc/library/", "Doc/howto/"), "PSF-2.0", "PSF-2.0-or-0BSD"),
}
LICENCE_MARKERS = {
    "MIT": ("permission is hereby granted", "copyright"),
    "CC-BY-4.0": ("attribution 4.0",),
    "CC-BY-3.0": ("attribution 3.0",),
    "CC-BY-SA-2.5": ("attribution-sharealike 2.5",),
    "PSF-2.0": ("python software foundation license version 2",),
    "0BSD": ("zero-clause bsd",),
    "CC0-1.0": ("cc0",),
}
LICENCE_PATHS = {
    "creator-docs": {"LICENSE", "LICENSE-CODE"}, "luau-site": {"LICENSE.md"},
    "godot-guides": {"LICENSE.txt"}, "godot-api": {"README.md", "LICENSE.txt"},
    "godot-xml": {"LICENSE.txt"}, "dotnet-docs": {"LICENSE", "LICENSE-CODE"},
    "mdn-content": {"LICENSE.md"}, "typescript-handbook": {"LICENSE", "LICENSE-CODE"},
    "python-docs": {"Doc/license.rst"},
}


class CorpusError(ValueError):
    """A candidate cannot be verified or exceeds its declared scope."""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":")).encode()).hexdigest()


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise CorpusError("paths must be explicit relative POSIX paths")
    path = PurePosixPath(value)
    parts = value.split("/")
    if (path.is_absolute() or path.as_posix() != value
            or any(not p or p in (".", "..", ".git") or p.rstrip(" .") != p for p in parts)):
        raise CorpusError("path escapes or uses an unsupported component")
    if any(c in value for c in "*?[]") or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise CorpusError("wildcards and control characters are not allowed")
    return value


def read_manifest(path: Path) -> dict:
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise CorpusError("manifest exceeds 256 KiB")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise CorpusError("expected candidate manifest schema_version 1")
    sources = config.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 12:
        raise CorpusError("manifest requires 1..12 sources")
    names = set()
    for source in sources:
        if not isinstance(source, dict):
            raise CorpusError("source must be an object")
        name = source.get("name")
        if not isinstance(name, str) or name in names or name not in {*POLICIES, "unity-links"}:
            raise CorpusError("duplicate or unknown official source")
        names.add(name)
        if name == "unity-links":
            if source.get("permission") != "link-only" or source.get("revision") is not None:
                raise CorpusError("Unity must remain unresolved and link-only")
            continue
        repo, prefixes, prose, code = POLICIES[name]
        if source.get("repo") != "https://github.com/" + repo + ".git":
            raise CorpusError("source does not match the canonical upstream")
        if source.get("prose_licence") != prose or source.get("code_licence") != code:
            raise CorpusError("unknown or mismatched licence policy")
        if source.get("permission") not in ("candidate", "reviewed-copy"):
            raise CorpusError("unknown retrieval permission")
        revision = source.get("revision")
        if revision is not None and not re.fullmatch(r"[0-9a-f]{40}", str(revision)):
            raise CorpusError("revision must be a full commit SHA, never a moving ref")
        for key in ("checkout", "branch", "compatibility", "attribution"):
            if not isinstance(source.get(key), str) or not source[key].strip() or len(source[key]) > 1000:
                raise CorpusError("missing or oversized " + key)
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", source["checkout"]):
            raise CorpusError("invalid checkout name")
        paths = source.get("paths")
        if (not isinstance(paths, list) or not paths or len(paths) > 2000
                or not all(isinstance(p, str) for p in paths) or len(set(paths)) != len(paths)):
            raise CorpusError("source requires unique explicit paths")
        for selected in paths:
            if not relative_path(selected).startswith(prefixes):
                raise CorpusError("selected file is outside this source's allowed scope")
            if Path(selected).suffix not in (".md", ".mdx", ".rst", ".xml", ".yaml"):
                raise CorpusError("unsupported source file kind")
        limits = source.get("limits", {})
        if not isinstance(limits, dict):
            raise CorpusError("source bounds must be an object")
        ceilings = {"files": 2000, "file_bytes": 2 * 1024 * 1024,
                    "total_bytes": 32 * 1024 * 1024, "chunks": 30000}
        for key, ceiling in ceilings.items():
            value = limits.get(key)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise CorpusError("missing or excessive bound: " + key)
        if len(paths) > limits["files"]:
            raise CorpusError("selection exceeds file count bound")
        records = source.get("licence_files")
        if not isinstance(records, list) or not 1 <= len(records) <= 6:
            raise CorpusError("licence files must be explicit")
        for record in records:
            if not isinstance(record, dict):
                raise CorpusError("licence record must be an object")
            relative_path(record.get("path"))
            if record["path"] not in LICENCE_PATHS[name]:
                raise CorpusError("licence file is outside reviewed evidence paths")
            if record.get("id") not in LICENCE_MARKERS:
                raise CorpusError("unknown licence file identifier")
            sha = record.get("sha256")
            if sha is not None and not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
                raise CorpusError("invalid licence hash")
        base = urlsplit(source.get("public_base", ""))
        if base.scheme != "https" or not base.netloc or base.username or base.password:
            raise CorpusError("public_base must be HTTPS without credentials")
    return config


def git_read(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    done = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                           "-C", str(repo), *args], capture_output=True, timeout=30, env=env)
    if done.returncode:
        raise CorpusError("local Git metadata could not be verified")
    if len(done.stdout) > 128 * 1024:
        raise CorpusError("Git metadata exceeds the verification bound")
    return done.stdout.decode("utf-8", errors="strict").strip()


def contained_file(repo: Path, relative: str, limit: int) -> Path:
    target = repo / relative_path(relative)
    current = repo
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise CorpusError("symlink/junction source paths are not supported")
    try:
        target.resolve().relative_to(repo.resolve())
    except ValueError as exc:
        raise CorpusError("source path escapes checkout") from exc
    if not target.is_file() or target.stat().st_size > limit:
        raise CorpusError("selected file is missing or exceeds its byte bound: " + relative)
    return target


def tracked_read(repo: Path, relative: str, limit: int) -> bytes:
    try:
        expected = git_read(repo, "rev-parse", "HEAD:" + relative_path(relative))
    except CorpusError as exc:
        raise CorpusError("selected file is missing or untracked: " + relative) from exc
    target = contained_file(repo, relative, limit)
    # No filters/textconv or network; compare bytes to the tracked blob at HEAD.
    raw = target.read_bytes()
    if len(raw) > limit:
        raise CorpusError("file grew beyond its byte bound")
    actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if actual != expected:
        raise CorpusError("tracked file changed during snapshot verification")
    return raw


def verify_snapshot(source: dict, sources_dir: Path) -> dict:
    if source["name"] == "unity-links" or source.get("permission") != "reviewed-copy":
        raise CorpusError("source is link-only or awaits permission review")
    if source.get("revision") is None or any(r.get("sha256") is None for r in source["licence_files"]):
        raise CorpusError("unresolved commit or reviewed licence hashes")
    repo = sources_dir / source["checkout"]
    if repo.is_symlink() or (hasattr(repo, "is_junction") and repo.is_junction()):
        raise CorpusError("checkout cannot be a symlink/junction")
    if git_read(repo, "rev-parse", "--show-toplevel") != str(repo.resolve()).replace("\\", "/"):
        # Git for Windows emits POSIX separators; also accept the platform-native form.
        if Path(git_read(repo, "rev-parse", "--show-toplevel")).resolve() != repo.resolve():
            raise CorpusError("checkout is not the registered repository root")
    if git_read(repo, "rev-parse", "HEAD") != source["revision"]:
        raise CorpusError("checkout does not match its full pinned revision")
    if git_read(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise CorpusError("dirty or untracked snapshot cannot be called pinned")
    origin = git_read(repo, "config", "--get", "remote.origin.url").rstrip("/")
    if origin.removesuffix(".git") != source["repo"].removesuffix(".git"):
        raise CorpusError("local origin does not match canonical upstream")
    ids = set()
    for record in source["licence_files"]:
        raw = tracked_read(repo, record["path"], 256 * 1024)
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise CorpusError("licence changed; independent review is required")
        text = raw.decode("utf-8-sig").lower()
        if not all(marker in text for marker in LICENCE_MARKERS[record["id"]]):
            raise CorpusError("licence text does not match its reviewed identifier")
        ids.add(record["id"])
    required = {source["prose_licence"]}
    if source["code_licence"] == "MIT":
        required.add("MIT")
    if source["code_licence"] == "PSF-2.0-or-0BSD":
        required.add("0BSD")
    if source["code_licence"] == "CC0-1.0-or-MIT-by-history":
        required.update(("MIT", "CC0-1.0"))
    if not required <= ids:
        raise CorpusError("reviewed licence records do not cover prose and sample rules")
    return {"repo": repo, "commit": source["revision"],
            "commit_date": git_read(repo, "log", "-1", "--format=%cI"),
            "verification": "clean-local-snapshot; upstream-origin-is-declared"}
