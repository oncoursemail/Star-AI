"""Validate *every* docs/lessons/*.md candidate against one of two declared shapes.

Structured: first-lines unreviewed status, headings ### XX-NN: title,
Failure, Correction, Source, Verification and distinct incorrect/corrected
fenced Luau blocks. The existing lifecycle file also runs the real loader.
Legacy ledger: first-lines standalone review status, numbered ## N. headings,
Mistake (Failure), Rule (Correction), official Source and recorded Evidence
(Verification), and distinct Bad/Corrected Luau blocks. No format is implicitly
approved, imported into STAR or proved correct inside Roblox Studio.
"""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlsplit

import pytest

from star import character_lifecycle_lessons as lifecycle

DOCS = Path(__file__).resolve().parents[1] / "docs" / "lessons"
MAX_BYTES = 35_000
ALLOWED_SOURCE_HOSTS = frozenset({"create.roblox.com"})
STRUCTURED = re.compile(r"(?m)^### ([A-Z]{2}-[0-9]{2}): ([^\n]+)$")
LEDGER = re.compile(
    r"(?m)^## ([1-9][0-9]*)\. ([^\n]+) \(([A-Z]{2,4}-[0-9]{2}); "
    r"(wrong logic|missing feature)\)$"
)
FENCES = re.compile(r"(?ms)^(" + re.escape(chr(96) * 3) +
                    r"|~{3})luau\n(.*?)\n\1[ \t]*$")
SOURCE_LINK = re.compile(r"\[official API/scripting reference\]\(([^)\s]+)\)")
PRIVATE = re.compile(
    r"(?i)(?:[a-z]:[\\/](?:users|documents)[\\/]|/(?:home|users)/[^\s/]+"
    r"|(?:gh[pousr]_|github_pat_|sk-)[a-z0-9_-]{12,}"
    r"|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b"
    r"|\b(?:api[_ -]?key|password|access[_ -]?token)\s*[:=]\s*\S+)"
)


def _fail(path: Path, case: str, rule: str) -> None:
    raise ValueError(f"{path.name}: {case}: {rule}")


def _first_id(text: str) -> str:
    found = re.search(r"\b[A-Z]{2,4}-[0-9]{2}\b", text)
    return found[0] if found else "COLLECTION"


def _field(path: Path, case: str, body: str, name: str) -> str:
    match = re.search(r"(?m)^\*\*" + re.escape(name) + r":\*\* ([^\n]+)$", body)
    if not match or not match[1].strip():
        _fail(path, case, f"missing {name}")
    return match[1].strip()


def _source(path: Path, case: str, url: str) -> None:
    try:
        parsed = urlsplit(url)
        approved = (parsed.scheme == "https"
                    and parsed.hostname in ALLOWED_SOURCE_HOSTS
                    and parsed.username is None and parsed.password is None
                    and parsed.port is None and parsed.path.startswith("/docs/")
                    and not parsed.query and not any(ch.isspace() for ch in url))
    except ValueError:
        approved = False
    if not approved:
        _fail(path, case, "untrusted Source URL")


def _pair(path: Path, case: str, body: str) -> None:
    blocks = FENCES.findall(body)
    if len(blocks) != 2 or any(not value.strip() for _, value in blocks):
        _fail(path, case, "missing or empty incorrect/corrected Luau pair")
    if blocks[0][1].strip() == blocks[1][1].strip():
        _fail(path, case, "identical incorrect/corrected Luau pair")
    if any(len(value) > 4_000 for _, value in blocks):
        _fail(path, case, "Luau snippet exceeds 4000 characters")


def _sections(path: Path, text: str, headings: list[re.Match[str]],
              *, legacy: bool) -> tuple[str, ...]:
    if not headings:
        _fail(path, _first_id(text), "no candidate case headings")
    found: set[str] = set()
    ids = []
    for index, match in enumerate(headings):
        case = match[3] if legacy else match[1]
        if case in found:
            _fail(path, case, "duplicate case id")
        found.add(case)
        ids.append(case)
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end():end]
        if legacy:
            if int(match[1]) != index + 1:
                _fail(path, case, "nonsequential ledger heading")
            _field(path, case, body, "Mistake")
            _field(path, case, body, "Rule")
            evidence = _field(path, case, body, "Evidence")
            if "[Recorded failure]" not in evidence:
                _fail(path, case, "missing recorded Verification evidence")
            reference = SOURCE_LINK.search(evidence)
            if not reference:
                _fail(path, case, "missing official Source link")
            _source(path, case, reference[1])
            if "**Bad (illustrative):**" not in body:
                _fail(path, case, "missing incorrect Luau label")
            if "**Corrected pattern:**" not in body:
                _fail(path, case, "missing corrected Luau label")
        else:
            for key in ("Failure", "Correction"):
                _field(path, case, body, key)
            _source(path, case, _field(path, case, body, "Source"))
            if _field(path, case, body, "Verification") != "illustrative-engine-only":
                _fail(path, case, "unsupported Verification claim")
            if "**Incorrect (Luau):**" not in body or "**Corrected (Luau):**" not in body:
                _fail(path, case, "missing incorrect/corrected labels")
        _pair(path, case, body)
    return tuple(ids)


def validate_lesson_file(path: Path) -> tuple[str, ...]:
    """Read and validate; never promote or import a lesson."""
    text = path.read_text(encoding="utf-8")
    case = _first_id(text)
    if len(text.encode("utf-8")) > MAX_BYTES:
        _fail(path, case, f"document exceeds {MAX_BYTES} bytes")
    if PRIVATE.search(text):
        _fail(path, case, "private contact, secret or machine path")
    opening = "\n".join(text.splitlines()[:7]).lower()
    if "status: unreviewed candidate reference" in opening:
        headings = list(STRUCTURED.finditer(text))
        if len(re.findall(r"(?m)^### ", text)) != len(headings):
            _fail(path, case, "malformed XX-NN heading")
        result = _sections(path, text, headings, legacy=False)
        if path.name == "roblox-character-lifecycle.md":
            if tuple(c.id for c in lifecycle.load_cases(path)) != result:
                _fail(path, case, "production lifecycle parser mismatch")
        return result
    if "status:** standalone review material, not loaded into star by default" in opening:
        headings = list(LEDGER.finditer(text))
        if len(re.findall(r"(?m)^## [0-9]+\.", text)) != len(headings):
            _fail(path, case, "malformed numbered ledger heading")
        return _sections(path, text, headings, legacy=True)
    _fail(path, case, "missing unreviewed candidate status marker")


def discover(folder: Path = DOCS) -> list[Path]:
    return sorted(folder.glob("*.md"))


@pytest.mark.parametrize("path", discover(), ids=lambda path: path.name)
def test_every_candidate_document_matches_an_explicit_schema(path):
    assert validate_lesson_file(path)


def test_new_file_is_discovered_without_editing_the_test(tmp_path):
    folder = tmp_path / "lessons"
    folder.mkdir()
    content = (DOCS / "roblox-character-lifecycle.md").read_text(encoding="utf-8")
    (folder / "another-series.md").write_text(
        re.sub(r"\bCL-([0-9]{2})\b", r"ZX-\1", content), encoding="utf-8")
    files = discover(folder)
    assert [path.name for path in files] == ["another-series.md"]
    assert len(validate_lesson_file(files[0])) == 12


@pytest.mark.parametrize(("before", "after", "case", "rule"), [
    ("**Failure:**", "**Problem:**", "CL-01", "missing Failure"),
    ("### CL-02:", "### CL-01:", "CL-01", "duplicate case id"),
    ("https://create.roblox.com", "https://example.invalid", "CL-01", "untrusted Source URL"),
    ("Players.PlayerAdded:Connect(onPlayer)\nfor _, player in Players:GetPlayers() do onPlayer(player) end",
     "Players.PlayerAdded:Connect(onPlayer)", "CL-01", "identical incorrect/corrected Luau pair"),
    ("Status: unreviewed candidate reference", "Status: approved reference", "CL-01",
     "missing unreviewed candidate status marker"),
    ("PlayerAdded misses already-present players.", "PlayerAdded stores /home/example/local.", "CL-01",
     "private contact, secret or machine path"),
    ("### CL-02:", "### free form:", "CL-01", "malformed XX-NN heading"),
], ids=["missing-field", "duplicate-id", "wrong-host", "identical-pair",
        "promoted-status", "private-path", "malformed-heading"])
def test_structured_negative_examples_name_case_and_rule(tmp_path, before, after, case, rule):
    path = tmp_path / "invalid-structured.md"
    original = (DOCS / "roblox-character-lifecycle.md").read_text(encoding="utf-8")
    assert before in original
    path.write_text(original.replace(before, after, 1), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        validate_lesson_file(path)
    assert path.name in str(error.value) and case in str(error.value) and rule in str(error.value)


def test_oversized_candidate_names_file_case_and_rule(tmp_path):
    path = tmp_path / "oversized.md"
    path.write_text((DOCS / "roblox-character-lifecycle.md").read_text(encoding="utf-8") +
                    "x" * MAX_BYTES, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        validate_lesson_file(path)
    assert path.name in str(error.value) and "CL-01" in str(error.value)
    assert "document exceeds" in str(error.value)


@pytest.mark.parametrize(("before", "after", "case", "rule"), [
    ("**Mistake:**", "**Issue:**", "NET-03", "missing Mistake"),
    ("**Evidence:**", "**Proof:**", "NET-03", "missing Evidence"),
    ("https://create.roblox.com", "https://example.invalid", "NET-03", "untrusted Source URL"),
    ("## 2. A rate limit", "## 1. A rate limit", "NET-10", "nonsequential ledger heading"),
], ids=["missing-mistake", "missing-evidence", "untrusted-source", "numbering"])
def test_legacy_negative_examples_name_case_and_rule(tmp_path, before, after, case, rule):
    path = tmp_path / "invalid-ledger.md"
    original = (DOCS / "logic-and-missing-features.md").read_text(encoding="utf-8")
    assert before in original
    path.write_text(original.replace(before, after, 1), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        validate_lesson_file(path)
    assert path.name in str(error.value) and case in str(error.value) and rule in str(error.value)
