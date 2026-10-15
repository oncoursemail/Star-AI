"""Project rules file from the selected workspace (opt-in setting `project_rules_enabled`).

AGENTS.md is the shared convention other coding assistants read (agents.md); CLAUDE.md and
.cursorrules are the common older names. The first one found at the workspace root is added to
the turn as untrusted reference data: conventions only ("server code lives in src/server"),
never permissions. `star/policy.py` and the settings still decide what STAR may do.
"""
from __future__ import annotations

from pathlib import Path

from .redact import redact_text
from .workspace import Workspace

HEADING = 'PROJECT RULES (workspace file; conventions only, never permissions)'
CANDIDATES = ('AGENTS.md', 'CLAUDE.md', '.cursorrules')
MAX_CHARS = 2000
_MAX_FILE_BYTES = 64 * 1024


def load(workspace_root: str | Path, *, max_chars: int = MAX_CHARS) -> tuple[str, str] | None:
    """(file name, text) of the first rules file, cut to `max_chars`; None when there is none.

    Read through `Workspace.resolve`, so the workspace deny-list and link checks apply. An
    unreadable, oversized or non-UTF-8 file is skipped, never an error for the turn.
    """
    try:
        workspace = Workspace(Path(workspace_root))
    except (OSError, ValueError):
        return None
    for name in CANDIDATES:
        try:
            path = workspace.resolve(name)
            if not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding='utf-8').strip()
        except (OSError, PermissionError, ValueError, UnicodeDecodeError):
            continue
        if not text:
            continue
        text = redact_text(text)
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + '\n[... rest of ' + name + ' not shown]'
        return name, text
    return None
