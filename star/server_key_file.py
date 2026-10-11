"""Import a locally provisioned STAR Server key without exposing its contents to the UI."""
from pathlib import Path

from .providers import STAR_SERVER, save_api_key


def key_file_status(home: Path | None = None) -> dict:
    path = (home or Path.home()) / '.star' / 'server_api_key'
    return {'found': path.exists()}


def import_key_file(home: Path | None = None) -> dict:
    path = (home or Path.home()) / '.star' / 'server_api_key'
    try:
        with path.open('r', encoding='utf-8') as handle:
            first = handle.readline(4097).strip()
    except (OSError, UnicodeError):
        raise ValueError('Server key file is unreadable.') from None
    token = first.partition('=')[2].strip() if '=' in first else first
    if not token or len(token) > 2048:
        raise ValueError('Server key file is invalid.')
    try:
        save_api_key(STAR_SERVER, token)
    except ValueError:
        raise ValueError('Server key file is invalid.') from None
    return {'connected': True}
