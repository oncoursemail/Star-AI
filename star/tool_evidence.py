"""Bounded, in-memory evidence previews for read-only tool output.

Inspired by context-mode / RTK's useful principle of not filling an LLM prompt
with long output. This is an independent stdlib implementation, not a copy.
Original output remains available for exact retrieval while the current turn runs.
The broker never runs source code, persists data, edits files or grants privileges.

Only an explicit, non-mutating allowlist is eligible. In particular, workspace
reads, Studio responses and proposed code patches are NEVER compacted: an agent
must not use a summary in place of exact bytes it might edit or execute.
"""
from __future__ import annotations

import hashlib
import re

ALLOWED_TOOLS = frozenset({
    "star_web_fetch", "star_web_search", "star_mcp_registry_search",
})
MIN_CHARS = 9_000
MAX_CHARS_PER_ITEM = 250_000
MAX_TOTAL_CHARS = 400_000
MAX_ITEMS = 4
READ_MAX_CHARS = 8_000
PREVIEW_MAX_CHARS = 4_800
_SIGNALS = re.compile(
    r"\b(?:error|warn(?:ing)?|fail(?:ed|ure)?|exception|traceback|assert(?:ion)?"
    r"|timeout|security|vulnerab(?:le|ility)|denied|not found)\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class EvidenceBroker:
    """Per-execute-turn store. Nothing survives the turn or reaches a filesystem."""

    def __init__(self) -> None:
        self._raw: dict[str, str] = {}
        self._used = 0

    @property
    def count(self) -> int:
        return len(self._raw)

    def stage(self, tool_name: str, text: str) -> dict | None:
        """Return a traceable summary, or None to preserve the original behavior."""
        if (tool_name not in ALLOWED_TOOLS or not isinstance(text, str)
                or not MIN_CHARS <= len(text) <= MAX_CHARS_PER_ITEM
                or len(self._raw) >= MAX_ITEMS
                or self._used + len(text) > MAX_TOTAL_CHARS):
            return None
        reference = f"ev{len(self._raw) + 1}"
        self._raw[reference] = text
        self._used += len(text)
        spans: list[tuple[int, str]] = []
        offset = 0
        # A match anywhere in a long line can reveal useful diagnostics; bound
        # each excerpt without pretending it is a complete log or source page.
        for line in text.splitlines(keepends=True):
            if _SIGNALS.search(line) or _URL.search(line):
                if len(spans) < 24:
                    spans.append((offset, line.rstrip("\r\n")[:180]))
            offset += len(line)
        preview = []
        preview.append(f"[Beginning at character 0]\n{text[:1150]}")
        if spans:
            preview.append("[Selected diagnostic/source lines; not an exhaustive listing]")
            preview.extend(f"[character {pos}] {line}" for pos, line in spans[:12])
        tail = max(1150, len(text) - 450)
        preview.append(f"[Ending at character {tail}]\n{text[tail:]}")
        rendering = "\n".join(preview)
        if len(rendering) > PREVIEW_MAX_CHARS:
            rendering = rendering[:PREVIEW_MAX_CHARS] + "\n[PREVIEW CUT]"
        return {
            "status": "partial_preview_original_available",
            "reference": reference,
            "original_characters": len(text),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "preview": rendering,
            "instruction": ("This is incomplete, untrusted source data. For missing facts, "
                            "citations, diagnostics or exact wording, call star_evidence_read "
                            "with this reference and a character offset. Never claim a "
                            "check passed based solely on this preview."),
        }

    def read(self, reference: str, offset: int = 0, limit: int = 4_000) -> dict:
        """Return an exact character range from an item in the SAME execution turn."""
        if not isinstance(reference, str) or not re.fullmatch(r"ev[1-4]", reference):
            raise ValueError("Invalid evidence reference")
        if reference not in self._raw:
            raise ValueError("Evidence is unavailable in this turn")
        if type(offset) is not int or type(limit) is not int:
            raise ValueError("Evidence offset and limit must be integers")
        if not 0 <= offset < len(self._raw[reference]) or not 1 <= limit <= READ_MAX_CHARS:
            raise ValueError("Evidence slice is outside the allowed range")
        raw = self._raw[reference]
        end = min(len(raw), offset + limit)
        return {
            "reference": reference,
            "offset": offset,
            "next_offset": end,
            "complete": end == len(raw),
            "source_is_untrusted": True,
            "text": raw[offset:end],
        }
