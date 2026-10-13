"""The "Look at my screen" action: one screenshot, taken only when the owner asks for it.

The composer's + menu offers "Look at my screen". The interface first shows what will
happen and asks; only a press of "Take screenshot" sends ``captureScreen`` with
``consent: true``. Nothing here runs on a timer, on a model's request or in the background:
the React shell calls :func:`require_consent` before it grabs anything, and the model has
no tool that reaches this module.

The picture is saved under the STAR data folder (``screen-captures/``), added to the files
this session may attach, and shown in the composer as an ordinary attachment the owner can
remove before sending. It reaches a model only if the owner then sends the message, and
only the model that message goes to (the same path as any attached picture).

The Qt grab itself lives in react_shell (it needs the window); everything that can be
checked without a display lives here and is unit tested.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

CAPTURE_DIR = 'screen-captures'
#: Old captures beyond this count are removed, oldest first, so the folder cannot grow forever.
KEEP_CAPTURES = 40
#: A 4K screen as PNG is a few megabytes; anything far larger is not a screenshot we made.
MAX_CAPTURE_BYTES = 60_000_000
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
PREVIEW_PREFIXES = ('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,')


class ConsentRequired(PermissionError):
    """The request did not carry the owner's explicit, per-use yes."""


def require_consent(body: object) -> None:
    """Refuse unless this one request says ``consent: true`` (the boolean, not a truthy value)."""
    if not isinstance(body, dict) or body.get('consent') is not True:
        raise ConsentRequired(
            'STAR only looks at your screen after you choose "Take screenshot". Nothing was captured.')


def capture_folder(home: Path) -> Path:
    return Path(home) / CAPTURE_DIR


def capture_path(home: Path, now: datetime | None = None) -> Path:
    """A new, unused file name such as screen-20261013-142501.png (a suffix is added on a clash)."""
    stamp = (now or datetime.now(timezone.utc)).strftime('%Y%m%d-%H%M%S')
    folder = capture_folder(home)
    candidate = folder / f'screen-{stamp}.png'
    counter = 2
    while candidate.exists():
        candidate = folder / f'screen-{stamp}-{counter}.png'
        counter += 1
    return candidate


def prune(home: Path, keep: int = KEEP_CAPTURES) -> list[Path]:
    """Delete the oldest captures beyond ``keep``. Only files this module named are touched."""
    folder = capture_folder(home)
    if not folder.is_dir():
        return []
    ours = sorted((p for p in folder.glob('screen-*.png') if p.is_file()), key=lambda p: p.name)
    removed = ours[:-keep] if keep > 0 and len(ours) > keep else []
    for path in removed:
        try:
            path.unlink()
        except OSError:
            pass
    return removed


def store_capture(png: bytes, home: Path, now: datetime | None = None) -> Path:
    """Write one PNG screenshot under the data folder and return its resolved path."""
    if not isinstance(png, (bytes, bytearray)) or not png.startswith(PNG_SIGNATURE):
        raise ValueError('The screenshot could not be read as a picture. Nothing was saved.')
    if len(png) > MAX_CAPTURE_BYTES:
        raise ValueError('The screenshot is unexpectedly large. Nothing was saved.')
    path = capture_path(home, now)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(png))
    prune(home)
    return path.resolve()


def preview_url(data: bytes, mime: str = 'image/jpeg') -> str:
    """A small inline thumbnail for the composer chip (never the full screenshot)."""
    prefix = f'data:{mime};base64,'
    if prefix not in PREVIEW_PREFIXES:
        raise ValueError('Unsupported preview type')
    return prefix + base64.b64encode(bytes(data)).decode('ascii')


def describe(path: Path, width: int, height: int, preview: str) -> dict:
    """What the interface receives: where the file is and a thumbnail, nothing else."""
    if preview and not preview.startswith(PREVIEW_PREFIXES):
        preview = ''
    return {'path': str(path), 'name': Path(path).name, 'width': int(width), 'height': int(height),
            'preview': preview}
