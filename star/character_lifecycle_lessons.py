"""Read-only candidate Roblox character lifecycle lessons; no automatic promotion."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

LESSONS_FILE = Path(__file__).resolve().parents[1] / "docs" / "lessons" / "roblox-character-lifecycle.md"
HEADER = re.compile(r"(?m)^### (CL-[0-9]{2}): ([^\n]+)\n")
FENCE = chr(96) * 3
SNIPPETS = re.compile(r"(?ms)^" + re.escape(FENCE) + r"luau\n(.*?)\n" + re.escape(FENCE) + r"$")


@dataclass(frozen=True)
class CharacterLifecycleCase:
    id: str
    title: str
    failure: str
    correction: str
    source_url: str
    verification: str
    incorrect: str
    corrected: str


def load_cases(path: Path = LESSONS_FILE) -> tuple[CharacterLifecycleCase, ...]:
    """Parse the bounded Markdown schema; reject unsupported provenance claims."""
    text = Path(path).read_text(encoding="utf-8")
    if len(text) > 35_000 or "Status: unreviewed candidate reference" not in text:
        raise ValueError("Lifecycle collection is malformed or promoted")
    sections = HEADER.split(text)
    if len(sections) < 4 or (len(sections) - 1) % 3 != 0:
        raise ValueError("No structured lifecycle cases")
    found = []
    for i in range(1, len(sections), 3):
        identifier, title, body = sections[i:i + 3]
        fields = {}
        for name in ("Failure", "Correction", "Source", "Verification"):
            match = re.search(r"(?m)^\*\*" + name + r":\*\* ([^\n]+)$", body)
            if not match:
                raise ValueError(f"{identifier}: missing {name}")
            fields[name] = match.group(1)
        blocks = SNIPPETS.findall(body)
        if len(blocks) != 2 or not blocks[0].strip() or blocks[0] == blocks[1]:
            raise ValueError(f"{identifier}: invalid Luau pairs")
        url = fields["Source"]
        if not re.fullmatch(
            r"https://create\.roblox\.com/docs/reference/engine/classes/"
            r"[A-Za-z][A-Za-z0-9]*(?:#[A-Za-z][A-Za-z0-9]*)?", url
        ):
            raise ValueError(f"{identifier}: untrusted reference")
        if fields["Verification"] != "illustrative-engine-only":
            raise ValueError(f"{identifier}: unsubstantiated verification claim")
        found.append(CharacterLifecycleCase(
            identifier, title, fields["Failure"], fields["Correction"], url,
            fields["Verification"], blocks[0], blocks[1]))
    if len({case.id for case in found}) != len(found):
        raise ValueError("Duplicate lifecycle case")
    return tuple(found)
