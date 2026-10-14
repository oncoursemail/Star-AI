"""Split the suite into N CI shards by test file (STAR_TEST_SHARD="i/N", 1-based).

Whole files stay together, so module fixtures and file-local order are unchanged. Files are
placed largest first (by collected test count) on the least-loaded shard; ties go to the lowest
shard number and files are ordered by path, so every machine computes the same split from the same
collection. Every file lands on exactly one shard: the union of the shards is the full suite.
"""
from __future__ import annotations

import re

_SPEC = re.compile(r"^\s*([1-9][0-9]*)\s*/\s*([1-9][0-9]*)\s*$")


def parse_shard(spec: str) -> tuple[int, int]:
    match = _SPEC.match(spec or "")
    if not match:
        raise ValueError(f"STAR_TEST_SHARD must look like 1/3, not {spec!r}")
    index, total = int(match.group(1)), int(match.group(2))
    if index > total:
        raise ValueError(f"STAR_TEST_SHARD {spec!r}: shard number is larger than the shard count")
    return index, total


def assign_files(counts: dict[str, int], total: int) -> dict[str, int]:
    """Map each file to a shard number in 1..total (longest-processing-time-first)."""
    loads = [0] * total
    placed: dict[str, int] = {}
    for path in sorted(counts, key=lambda name: (-counts[name], name)):
        shard = min(range(total), key=lambda i: (loads[i], i))
        loads[shard] += counts[path]
        placed[path] = shard + 1
    return placed


def file_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def split_items(items: list, spec: str) -> tuple[list, list]:
    """Return (kept, deselected) for the shard named by spec, keeping collection order."""
    index, total = parse_shard(spec)
    counts: dict[str, int] = {}
    for item in items:
        counts[file_of(item.nodeid)] = counts.get(file_of(item.nodeid), 0) + 1
    placed = assign_files(counts, total)
    kept = [item for item in items if placed[file_of(item.nodeid)] == index]
    dropped = [item for item in items if placed[file_of(item.nodeid)] != index]
    return kept, dropped
