"""Bound credential-shaped data before writing artifacts or exposing tool output."""
import re

_REDACTED = "[REDACTED]"
_PATTERNS = (
    re.compile(r'(?i)\bBearer\s+[^\s,;]+'),
    re.compile(r'''(?i)\b(?:key|api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret)\b[\"']?\s*[:=]\s*[\"']?[^\s,;\"'&}\]]+'''),
    re.compile(r'(?i)\b(?:https?|wss?)://[^\s/@]+:[^\s/@]+@'),
    re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),
)


def redact_text(value: str) -> str:
    """Replace likely credentials without recording their original values."""
    for pattern in _PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value
