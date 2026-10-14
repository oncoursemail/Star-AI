"""Shape-only diagnostics for user-visible validation errors.

Never echo untrusted values or prefixes: even a field name may hold a secret.
"""
from __future__ import annotations


def describe_invalid(value: object) -> str:
    """Return a bounded input shape without disclosing the value."""
    if type(value) is str:
        return f"{len(value)} characters"
    if type(value) is int:
        return "integer outside permitted range"
    if type(value) is bool:
        return "boolean"
    if value is None:
        return "missing value"
    if type(value) is frozenset:
        return f"frozenset of {len(value)} entries"
    return "unsupported value type"
