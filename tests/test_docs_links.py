"""Every relative link (and #anchor) in the repo's Markdown docs must resolve."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Paths that are generated at build/run time and may not exist in a checkout.
GENERATED_ALLOWLIST: tuple[str, ...] = ("dist/", "build/", "evals/results/", "data/")

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^(```|~~~)")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:", "file:")


def _doc_files() -> list[Path]:
    files = set(ROOT.glob("*.md")) | set((ROOT / "docs").rglob("*.md"))
    return sorted(files)


def _strip_code(text: str, inline: bool = True) -> str:
    out, fenced = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line.strip()):
            fenced = not fenced
            continue
        if not fenced:
            out.append(re.sub(r"`[^`]*`", "", line) if inline else line)
    return "\n".join(out)


def _slug(heading: str) -> str:
    h = re.sub(r"`|\*|_(?=\S)|\[|\]\([^)]*\)", "", heading.strip().lower())
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    anchors: set[str] = set()
    for line in _strip_code(path.read_text(encoding="utf-8", errors="replace"), inline=False).splitlines():
        m = re.match(r"#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            slug = _slug(m.group(1))
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            anchors.add(slug if n == 0 else f"{slug}-{n}")
    return anchors


def _broken(path: Path) -> list[str]:
    problems = []
    text = _strip_code(path.read_text(encoding="utf-8", errors="replace"))
    for m in LINK_RE.finditer(text):
        target = m.group(1) or m.group(2)
        if target.startswith(SKIP_SCHEMES) or target.startswith("<"):
            continue
        raw, _, frag = target.partition("#")
        dest = path if not raw else (path.parent / unquote(raw)).resolve()
        if raw:
            try:
                rel = dest.relative_to(ROOT).as_posix()
            except ValueError:
                problems.append(f"{target} (escapes repo)")
                continue
            if rel.startswith(GENERATED_ALLOWLIST):
                continue
            if not dest.exists():
                problems.append(f"{target} (missing file)")
                continue
        if re.fullmatch(r"L\d+(-L\d+)?", frag):
            continue  # GitHub line-range reference, not a heading anchor
        if frag and dest.suffix == ".md" and dest.is_file():
            if unquote(frag).lower() not in _anchors(dest):
                problems.append(f"{target} (missing anchor)")
    return problems


@pytest.mark.parametrize("path", _doc_files(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_resolve(path: Path) -> None:
    assert _broken(path) == []
