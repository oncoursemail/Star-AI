"""Import a locally provisioned STAR Server key without exposing its contents to the UI."""
from pathlib import Path
import re

from .providers import STAR_SERVER, save_api_key

MAX_LINE_CHARS = 4096
# `NAME=value` (optionally `export NAME=value`) with an environment-style name. Anything else is
# the key itself, so a key that contains '=' (base64 padding, for example) is stored whole.
_ASSIGNMENT = re.compile(r'^(?:export\s+)?[A-Z][A-Z0-9_]*\s*=\s*(.*)$')


def _key_file(home: Path | None) -> Path:
    return (home or Path.home()) / '.star' / 'server_api_key'


def key_file_status(home: Path | None = None) -> dict:
    path = _key_file(home)
    return {'found': path.is_file() and not path.is_symlink()}


def read_key_file(home: Path | None = None, *, path: Path | None = None) -> str:
    """The key in the key file (or in `path`), for the caller's memory only. Never print or log the result."""
    path = path or _key_file(home)
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError('not a regular file')
        with path.open('r', encoding='utf-8-sig') as handle:
            first = handle.readline(MAX_LINE_CHARS + 1)
    except (OSError, UnicodeError):
        raise ValueError('Server key file is unreadable.') from None
    # A first line longer than the limit was cut off: part of a key must never be stored as the key.
    if len(first) > MAX_LINE_CHARS and not first.endswith('\n'):
        raise ValueError('Server key file is invalid.')
    first = first.strip()
    assigned = _ASSIGNMENT.match(first)
    value = assigned.group(1).strip() if assigned else ''
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        value = value[1:-1]
    # `ABCD==` is a key with padding, not a name with an empty value.
    token = value if value.strip('=') else first
    if not token or len(token) > 2048:
        raise ValueError('Server key file is invalid.')
    return token


def import_key_file(home: Path | None = None) -> dict:
    token = read_key_file(home)
    try:
        save_api_key(STAR_SERVER, token)
    except ValueError:
        raise ValueError('Server key file is invalid.') from None
    return {'connected': True}
