"""Settings > Roblox Studio: whether a STAR Studio server connection exists on this PC (read-only).

The connection itself (the command star/studio.py starts for the "STAR Studio server" choice) is
operator configuration: the `STAR_STUDIO_MCP_COMMAND` environment variable, or the file
`<settings folder>/studio/remote.json` written by the operator's own scripts
(docs/STUDIO_HOST_CONFIGURATION.md). In v0.9.0 the desktop does not write that file: Settings shows
whether a connection exists and offers "Test connection", nothing else. A way to type the address
and command into Settings was built and is kept on its own branch for review after the release.

`status` never returns the stored command: only whether one exists and where it comes from. No
model tool reads it, and the model never sees the address or the command.
"""
from __future__ import annotations

from pathlib import Path

from . import studio

STUDIO_HOST_ACTIONS = frozenset({'studioHostStatus'})


def status(home) -> dict:
    """What Settings may show. `source`: environment (set by the operator, wins), settings (the
    operator's file in the settings folder), none, or invalid (a damaged or linked file: nothing is
    used until the operator repairs it)."""
    try:
        if studio.custom_launcher() is not None:
            source = 'environment'
        else:
            source = 'settings' if studio.configured_command(home) is not None else 'none'
    except studio.StudioTransportError:
        source = 'invalid'
    return {'configured': source in ('environment', 'settings'), 'source': source}


def handle(action: str, body: dict, settings_file) -> dict:
    """The one Settings action: read the state. The file lives beside the settings file, in its folder."""
    if action != 'studioHostStatus':
        raise PermissionError('Action not permitted')
    return status(Path(settings_file).parent)
