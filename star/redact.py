"""Replace credential-shaped text before it is written to an artifact or shown as a tool error.

Only shapes that are very likely a credential are replaced, and only the credential itself:
the name, the separator and the surrounding text stay, so ordinary prose and source code pass
through unchanged (`local key = "Player_" .. id`, `token = tokens[i]`, `password: string`,
"send the Bearer token"). A value assigned to a secret-looking name is replaced only when it is
one unbroken run of at least 20 key characters that is not the start of an expression.
"""
import re

_REDACTED = "[REDACTED]"
# What a key is written with: letters, digits and the base64 / URL-safe punctuation. No dot,
# bracket or parenthesis, so `token = session.manager.current()` is not one long "value".
_KEY_CHARS = r"A-Za-z0-9_\-+/~"
_VALUE = rf"[{_KEY_CHARS}]{{20,}}={{0,2}}"
# The run must end there: not inside a longer word, and not the head of a call, an attribute,
# an index or a method (`password = load_password_from_settings(path)`).
_NOT_AN_EXPRESSION = rf"(?![{_KEY_CHARS}=(.\[:])"
# Every pattern can start at most once per run of characters it consumes, so the work stays
# proportional to the length of the text (tests/test_redact.py times a hostile input).
_PATTERNS = (
    # Authorization: Bearer <token>
    (re.compile(rf"(?i)\b(Bearer\s+)[{_KEY_CHARS}.=]{{16,}}"), r"\1" + _REDACTED),
    # scheme://user:password@host
    (re.compile(r"(?i)\b((?:https?|wss?|ftp)://)[^\s/@:]+:[^\s/@]+@"), r"\1" + _REDACTED + "@"),
    # name = value, "name": "value", NAME=value for a secret-looking name (OPENAI_API_KEY, client_secret,
    # access_token, password, key). `key` counts only as a whole word: `monkey` and `cache_key` do not.
    (re.compile(
        r"""(?ix)
        ( (?: api[_-]?key | access[_-]?token | refresh[_-]?token | token | passw(?:or)?d | passwd | secret
            | (?<![A-Za-z0-9_]) key )
          [A-Za-z0-9]{0,24} (?: [_-] [A-Za-z0-9]{1,24} ){0,3}
          ["']? \s* (?: := | => | [:=] ) \s* ["']? )
        """ + _VALUE + _NOT_AN_EXPRESSION), r"\1" + _REDACTED),
    # Well-known key formats, wherever they appear.
    (re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"), _REDACTED),
    (re.compile(r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})"), _REDACTED),
    (re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), _REDACTED),
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)"), _REDACTED),
)


def redact_text(value: str) -> str:
    """Replace likely credentials without recording their original values."""
    if not isinstance(value, str) or not value:
        return value
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value
