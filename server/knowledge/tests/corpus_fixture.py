"""Authored local snapshots with declared origins; never fetched upstream documentation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

FIXTURES = Path(__file__).parent / "fixtures" / "corpora"


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return done.stdout.strip()


def snapshot(tmp_path, *, name="luau-site", files=None):
    repo = tmp_path / "sources" / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "STAR authored fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "core.autocrlf", "false")
    upstream = "https://github.com/luau-lang/site.git"
    git(repo, "remote", "add", "origin", upstream)
    raw = (FIXTURES / "MIT.txt").read_bytes()
    (repo / "LICENSE.md").write_bytes(raw)
    files = files or {"src/content/docs/guide.md": (FIXTURES / "guide.md").read_text()}
    for relative, text in files.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "authored local fixture")
    source = {"name": name, "repo": upstream, "checkout": name, "branch": "master",
              "revision": git(repo, "rev-parse", "HEAD"), "permission": "reviewed-copy",
              "prose_licence": "MIT", "code_licence": "MIT", "attribution": "STAR authored fixture; not fetched upstream",
              "compatibility": "synthetic fixture only", "licence_files": [{"path": "LICENSE.md", "id": "MIT",
                  "sha256": hashlib.sha256(raw).hexdigest()}], "paths": list(files),
              "public_base": "https://luau.org", "limits": {"files": 100, "file_bytes": 2097152,
                  "total_bytes": 10485760, "chunks": 5000}}
    manifest = tmp_path / "manifest.json"
    save(manifest, [source])
    return repo, manifest, source


def save(manifest, sources):
    manifest.write_text(json.dumps({"schema_version": 1, "sources": deepcopy(sources)}), encoding="utf-8")


def tree_bytes(path):
    return {p.relative_to(path).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in path.rglob("*") if p.is_file()}
