"""Read-only, bounded candidate lessons for named Luau types and ModuleScript contracts.

The explicit witness is a substring discriminator, NOT evidence of typechecking.
No runtime STAR lesson-store, model, or skill-pack enrolment happens here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

LESSONS_FILE = Path(__file__).resolve().parents[1] / "docs" / "lessons" / "luau-record-types.md"
MAX_BYTES = 45_000
MAX_CASES = 12
OFFICIAL_SOURCES = frozenset({
    "https://create.roblox.com/docs/luau/type-checking",
    "https://luau.org/syntax/",
    "https://create.roblox.com/docs/reference/engine/classes/ModuleScript",
})
VERIFICATION_LEVELS = frozenset({"pure-luau-illustrative", "multi-file-illustrative"})
HEADER = re.compile(r"(?m)^### (RT-[0-9]{2}): ([^\n]+)\n")
CODE = re.compile(r"(?ms)^\x60\x60\x60luau\n(.*?)\n\x60\x60\x60$")


@dataclass(frozen=True)
class RecordTypeCase:
    id: str
    title: str
    context: str
    failure: str
    correction: str
    source_url: str
    verification: str
    witness: str
    incorrect: str
    corrected: str


def witness_matches(case: RecordTypeCase, sample: str) -> bool:
    """Static inclusion check only; cannot certify Luau type correctness."""
    return case.witness in sample


def load_cases(path: Path = LESSONS_FILE) -> tuple[RecordTypeCase, ...]:
    """Reject promoted, missing, oversized, duplicated or untrusted candidate records."""
    with Path(path).open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Record-type candidate collection too large")
    try:
        body = raw.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        raise ValueError("Record-type candidates are not UTF-8") from exc
    if not re.search(r"(?m)^Status: unreviewed candidate reference$", body):
        raise ValueError("Record-type collection must remain unreviewed")
    pieces = HEADER.split(body)
    if len(pieces) < 4 or (len(pieces) - 1) % 3 or (len(pieces) - 1) // 3 > MAX_CASES:
        raise ValueError("Record-type collection has invalid case sections")

    result: list[RecordTypeCase] = []
    for index in range(1, len(pieces), 3):
        identifier, title, section = pieces[index:index + 3]
        if not title.strip() or len(title) > 110:
            raise ValueError(f"{identifier}: invalid title")
        fields: dict[str, str] = {}
        for label in ("Context", "Failure", "Correction", "Source", "Verification", "Witness"):
            matches = re.findall(r"(?m)^\*\*" + label + r":\*\* ([^\n]+)$", section)
            if len(matches) != 1 or not matches[0].strip() or len(matches[0]) > 450:
                raise ValueError(f"{identifier}: missing or invalid {label}")
            fields[label] = matches[0]
        examples = CODE.findall(section)
        if (len(examples) != 2 or any(not code.strip() or len(code) > 1_700 for code in examples)
                or examples[0] == examples[1]):
            raise ValueError(f"{identifier}: incorrect and corrected Luau are required")
        if fields["Source"] not in OFFICIAL_SOURCES:
            raise ValueError(f"{identifier}: unsupported official reference")
        verification = fields["Verification"]
        if verification not in VERIFICATION_LEVELS:
            raise ValueError(f"{identifier}: unsupported verification assertion")
        multi_file = verification == "multi-file-illustrative"
        if any(("-- File:" in code) != multi_file for code in examples):
            raise ValueError(f"{identifier}: context does not match source layout")
        witness = fields["Witness"]
        if len(witness) > 120 or witness in examples[0] or witness not in examples[1]:
            raise ValueError(f"{identifier}: correction witness is not discriminating")
        result.append(RecordTypeCase(
            identifier, title, fields["Context"], fields["Failure"], fields["Correction"],
            fields["Source"], verification, witness, examples[0], examples[1],
        ))
    if len({case.id for case in result}) != len(result):
        raise ValueError("Duplicate record-type case ID")
    return tuple(result)
