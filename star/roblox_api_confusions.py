"""Advisory corpus of confusable Roblox engine method names.

Not a Luau compiler or receiver-type checker. A hit requests verification
against the official class reference; it is never automatic code replacement.
The source is a reviewed static JSON file. This module makes no network calls.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from urllib.parse import urlparse

DATA = Path(__file__).resolve().parents[1] / "data" / "roblox_api_confusions.json"
_METHOD = re.compile(r"^:[A-Za-z][A-Za-z0-9]*\($", re.ASCII)
# Do not raise false positives for a method mentioned as data in comments or
# Luau quoted strings. Preserve newlines so line numbers remain exact.
_INERT = re.compile(
    r"""--\[(=*)\[.*?\]\1\]|--[^\n]*|\[(=*)\[.*?\]\2\]|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`""",
    re.DOTALL,
)


@lru_cache(maxsize=1)
def load_confusions() -> tuple[dict[str, str], ...]:
    """Validate the reviewed corpus at load time. No external lookup or writes."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("invalid Roblox API confusion corpus")
    seen: set[str] = set()
    result = []
    for entry in data:
        if not isinstance(entry, dict) or set(entry) != {"wrong", "right", "kind", "source_url"}:
            raise ValueError("invalid confusion entry shape")
        wrong, right = entry["wrong"], entry["right"]
        url = entry["source_url"]
        if (not isinstance(wrong, str) or not isinstance(right, str)
                or not _METHOD.fullmatch(wrong) or not _METHOD.fullmatch(right)
                or wrong == right or wrong in seen or entry["kind"] != "method"
                or not isinstance(url, str)):
            raise ValueError("invalid or duplicate API method mapping")
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname != "create.roblox.com"
                or not parsed.path.startswith("/docs/reference/engine/classes/")
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
            raise ValueError("API reference must be an official class page")
        seen.add(wrong)
        result.append(entry)
    return tuple(result)


def _blank_inert(match: re.Match[str]) -> str:
    return "".join("\n" if char == "\n" else " " for char in match.group())


def scan_luau(source: str) -> list[dict[str, str | int]]:
    """Find colon-called suspicious method spellings and 1-based source lines.

    A match does NOT prove the receiver is a Roblox class or that the code is
    invalid; user modules may define methods with identical names. Manual or
    type-aware verification remains necessary.
    """
    if not isinstance(source, str):
        raise TypeError("source must be Luau text")
    clean = _INERT.sub(_blank_inert, source)
    hits = []
    for entry in load_confusions():
        token = entry["wrong"]
        start = 0
        while True:
            at = clean.find(token, start)
            if at < 0:
                break
            hits.append({"line": clean.count("\n", 0, at) + 1,
                         "column": at - clean.rfind("\n", 0, at),
                         **entry})
            start = at + len(token)
    return sorted(hits, key=lambda hit: (hit["line"], hit["column"], hit["wrong"]))
