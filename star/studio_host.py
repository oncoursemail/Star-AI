"""The STAR Studio server connection that the owner types into Settings (address and command).

Settings > Roblox Studio has two fields for the "STAR Studio server" choice: the server's SSH address and
the command that starts the Studio connector on that server. This module turns them into the stored
command that star/studio.py reads (`configured_command`: `<settings folder>/studio/remote.json`, key
`command`) and says whether one is stored. It does not connect to anything and it does not choose the
route: that stays `Settings.studio_target`, checked by star/studio_connections.py.

What the interface can make STAR run is deliberately narrow, because the result is a program that
STAR starts on this PC:

  * the program is always `ssh`, with `-o BatchMode=yes` (key login only: it never asks for a password);
  * the address is `user@host` or a host name, letters, digits, dot, dash and underscore only, and it
    cannot begin with a dash (so it cannot be read as an option);
  * the command is words of letters, digits and `_ . / : = @ % + , -`, joined by single spaces into ONE
    argument, and its first word cannot begin with a dash. No quotes, no `;`, `|`, `&`, `$`, backticks,
    brackets or redirections: nothing a shell on the server could read as a second command.

The stored command is never returned: `status` says only whether one exists and where it comes from.
Only the owner's own action in Settings calls `save` and `clear` (star/react_shell.py); no model tool
does, and the model never sees the address or the command.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import tempfile

from . import studio

STUDIO_HOST_ACTIONS = frozenset({'studioHostStatus', 'studioHostSave', 'studioHostClear'})

MAX_ADDRESS, MAX_COMMAND, MAX_WORDS = 255, 400, 32
_ADDRESS = re.compile(r'(?:[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}@)?[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?\Z')
_WORD = re.compile(r'[A-Za-z0-9_./:=@%+,-]+\Z')
_FIRST = re.compile(r'[A-Za-z0-9_./]')
_FILE_TARGETS = ('pc', 'server')        # star/studio_remote.py keeps its own target in the same file


def compose(address, command) -> tuple[str, ...]:
    """The program and its arguments for one address and one server command, or ValueError in plain words."""
    if not isinstance(address, str) or not isinstance(command, str):
        raise ValueError('Enter the server address and the command')
    address, words = address.strip(), command.split()
    if not address or len(address) > MAX_ADDRESS or not _ADDRESS.match(address):
        raise ValueError('The server address must look like user@host: letters, digits, dot, dash and '
                         'underscore only')
    if not words:
        raise ValueError('Enter the command that starts the Studio connector on the server')
    if len(words) > MAX_WORDS or len(' '.join(words)) > MAX_COMMAND:
        raise ValueError(f'The command is too long (at most {MAX_WORDS} words and {MAX_COMMAND} characters)')
    if not _FIRST.match(words[0]) or any(not _WORD.match(word) for word in words):
        raise ValueError('The command may use letters, digits and _ . / : = @ % + , - only, separated by '
                         'spaces, and must start with the program name. Quotes and shell symbols are refused')
    return tuple(studio.validate_command(['ssh', '-o', 'BatchMode=yes', address, ' '.join(words)]))


def _folder(home) -> Path:
    profile = Path(home)
    if not profile.is_absolute() or '..' in profile.parts:
        raise ValueError('The settings folder is not usable')
    return profile / 'studio'


def _plain_directory(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400


def _kept_target(path: Path, default: str) -> str:
    """The operator scripts' own choice in the same file is kept; a damaged file gives the default."""
    try:
        saved = json.loads(path.read_text(encoding='utf-8-sig'))
        target = saved.get('target') if isinstance(saved, dict) else None
    except (OSError, ValueError):
        target = None
    return target if target in _FILE_TARGETS else default


def _write(home, command: list[str], default_target: str) -> None:
    folder = _folder(home)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'remote.json'
    # A linked folder or file is refused: star/studio.py refuses to read one, and writing through a
    # link would put the command somewhere the owner did not choose.
    if not _plain_directory(folder) or (os.path.lexists(path) and not stat.S_ISREG(path.lstat().st_mode)):
        raise ValueError('The Studio settings folder is a link or not a normal folder; nothing was saved')
    text = json.dumps({'target': _kept_target(path, default_target), 'command': command}, indent=1)
    handle, temporary = tempfile.mkstemp(dir=folder, prefix='remote-', suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    if json.loads(path.read_text(encoding='utf-8')).get('command') != command:
        raise ValueError('The Studio server connection could not be confirmed after saving')


def status(home) -> dict:
    """What Settings may show. `source`: environment (set by the operator, wins), settings (stored
    here), none, or invalid (a damaged or linked file: nothing is used until it is saved again)."""
    try:
        if studio.custom_launcher() is not None:
            source = 'environment'
        else:
            source = 'settings' if studio.configured_command(home) is not None else 'none'
    except studio.StudioTransportError:
        source = 'invalid'
    return {'configured': source in ('environment', 'settings'), 'source': source}


def save(home, address, command) -> dict:
    """Store the connection. The stored text is not echoed back."""
    _write(home, list(compose(address, command)), 'server')
    return status(home)


def clear(home) -> dict:
    """Forget the stored connection (the file stays, with an empty command)."""
    _write(home, [], 'pc')
    return status(home)


def forget_selection(settings_file) -> bool:
    """Another server is another Studio: the chosen place and its edit permissions do not carry over.
    Only when the STAR Studio server is the selected connection; this PC's choice is left alone."""
    from .desktop_core import Settings
    current = Settings.load(Path(settings_file))
    if current.studio_target != 'host_launcher' or not (current.studio_id or current.studio_edit or current.studio_luau):
        return False
    current.studio_id, current.studio_edit, current.studio_luau = '', False, False
    current.save(Path(settings_file))
    return True


CHANGING_ACTIONS = frozenset({'studioHostSave', 'studioHostClear'})


def handle(action: str, body: dict, settings_file) -> dict:
    """One Settings action. The command lives beside the settings file, in its folder."""
    home = Path(settings_file).parent
    if action == 'studioHostStatus':
        return status(home)
    if action == 'studioHostSave':
        report = save(home, body.get('address'), body.get('command'))
    elif action == 'studioHostClear':
        report = clear(home)
    else:
        raise PermissionError('Action not permitted')
    forget_selection(settings_file)
    return report
