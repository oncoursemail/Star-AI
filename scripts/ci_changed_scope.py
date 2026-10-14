"""Decide whether a change is documentation only, so CI may skip the test jobs.

Usage: python scripts/ci_changed_scope.py --root . --files changed.txt
Prints `docs_only=true` or `docs_only=false` (for $GITHUB_OUTPUT) and the reason on stderr.

Fails towards running everything: an empty or unreadable list, any non-Markdown file, Markdown that
the app reads (star/, frontend/, tests/, evals/, examples/, docs/lessons/), or a Markdown file whose
path or file name appears in any test, script or source file all give `docs_only=false`. Tests in
this repository read real documents (README.md, release checklists, agent notes), and those must
keep running when such a document changes.
"""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import sys

# Code that may read a document by name. A Markdown file named anywhere in here is not "docs only".
READERS = ("tests", "frontend/src", "frontend/scripts", "frontend/index.html", "frontend/vite.config.ts",
           "scripts", "star", "server", "main.py", "star_desktop.py", "installer", ".github")
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".json", ".yml", ".yaml", ".toml", ".ps1",
                 ".cmd", ".iss", ".html", ".txt", ".cfg", ".ini", ".luau", ".lua", ".md"}
MAX_BYTES = 2_000_000


def is_plain_doc(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not path.endswith(".md") or ".." in parts or path.startswith("/"):
        return False
    if len(parts) == 1:  # README.md, AGENTS.md ... at the repository root
        return True
    return parts[0] == "docs" and parts[1] != "lessons"


def reader_texts(root: Path):
    for name in READERS:
        base = root / name
        files = [base] if base.is_file() else (sorted(base.rglob("*")) if base.is_dir() else [])
        for file in files:
            if (file.is_file() and file.suffix.lower() in TEXT_SUFFIXES and "node_modules" not in file.parts
                    and file.stat().st_size <= MAX_BYTES):
                yield file, file.read_text(encoding="utf-8", errors="ignore")


def decide(root: Path, changed: list[str]) -> tuple[bool, str]:
    changed = sorted({line.strip().replace("\\", "/") for line in changed if line.strip()})
    if not changed:
        return False, "no changed-file list: run everything"
    other = [path for path in changed if not is_plain_doc(path)]
    if other:
        return False, f"{len(other)} changed file(s) are not plain documentation, e.g. {other[0]}"
    needles = {path: (path, PurePosixPath(path).name) for path in changed}
    for file, text in reader_texts(root):
        for path, (full, name) in needles.items():
            if (full in text or name in text) and file.resolve() != (root / path).resolve():
                return False, f"{path} is named in {file.relative_to(root).as_posix()}: run everything"
    return True, f"{len(changed)} documentation file(s) only, not read by code or tests"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--files", required=True, help="file with one changed path per line")
    args = parser.parse_args(argv)
    try:
        changed = Path(args.files).read_text(encoding="utf-8").splitlines()
        docs_only, reason = decide(Path(args.root).resolve(), changed)
    except Exception as exc:  # never skip tests because this helper broke
        docs_only, reason = False, f"scope check failed ({type(exc).__name__}): run everything"
    print(f"docs_only={'true' if docs_only else 'false'}")
    print(reason, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
