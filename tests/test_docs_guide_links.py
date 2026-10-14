"""Link check for the user guide in docs/guide/. Offline: only files in this repository are read.

Every relative link and image in a guide page must point at a file that exists, and every
``#anchor`` must match a heading in the target page. External links are only checked for form
(https, no private addresses). The index must list every page, and every page must say what
state each feature is in, using the three status words the guide promises.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "guide"
PAGES = sorted(GUIDE.glob("*.md"))

LINK = re.compile(r"!?\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)
PRIVATE = re.compile(r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b")
STATUS = re.compile(r"\b(Available|Opt-in|Coming soon)\b")


def _text(path: Path) -> str:
    return FENCE.sub("", path.read_text(encoding="utf-8"))


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, drop punctuation, spaces become hyphens."""
    heading = re.sub(r"`|\*\*|__", "", heading)
    heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    heading = heading.strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading)
    return heading.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    out = set()
    for heading in HEADING.findall(_text(path)):
        slug = _slug(heading)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        out.add(slug if count == 0 else f"{slug}-{count}")
    return out


def _links(path: Path) -> list[str]:
    return LINK.findall(_text(path))


def test_guide_exists_with_index():
    names = {p.name for p in PAGES}
    assert "README.md" in names, "docs/guide/README.md is the guide index"
    assert len(PAGES) >= 10


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_relative_links_and_anchors_resolve(page: Path):
    problems = []
    for target in _links(page):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            if target.lower().startswith("http://"):
                problems.append(f"{target}: use https")
            if PRIVATE.search(target):
                problems.append(f"{target}: private address")
            continue
        file_part, _, anchor = target.partition("#")
        dest = page if not file_part else (page.parent / unquote(file_part)).resolve()
        if not dest.exists():
            problems.append(f"{target}: no such file")
            continue
        if anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
            problems.append(f"{target}: no heading for #{anchor}")
    assert not problems, f"{page.name}:\n  " + "\n  ".join(problems)


def test_index_links_every_page():
    index = GUIDE / "README.md"
    linked = {Path(t.partition("#")[0]).name for t in _links(index) if not t.startswith(("http", "#"))}
    missing = [p.name for p in PAGES if p.name != "README.md" and p.name not in linked]
    assert not missing, f"pages missing from docs/guide/README.md: {missing}"


@pytest.mark.parametrize("page", [p for p in PAGES if p.name not in {"README.md", "glossary.md"}],
                         ids=lambda p: p.name)
def test_pages_state_feature_status(page: Path):
    assert STATUS.search(page.read_text(encoding="utf-8")), (
        f"{page.name} must give each feature a status: Available, Opt-in or Coming soon")


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_no_private_addresses(page: Path):
    found = PRIVATE.findall(page.read_text(encoding="utf-8"))
    assert not found, f"{page.name} contains a private network address"


def test_slug_matches_github_rules():
    assert _slug("Look at my screen") == "look-at-my-screen"
    assert _slug("Privacy & data: what leaves the PC?") == "privacy--data-what-leaves-the-pc"
    assert _slug("The `+` menu") == "the--menu"
