"""Audited file tools confined to a user-selected workspace. Never a shell escape hatch."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

MAX_READ_BYTES = 250_000
MAX_WRITE_BYTES = 250_000
DENIED_NAMES = {'.env', '.git', '.github', '.ssh', '.aws', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519'}
DENIED_SUFFIXES = {'.pem', '.p12', '.pfx', '.key'}

TOOLS = [
    {"name": "workspace_list", "description": "List files and folders relative to the selected workspace. Does not read outside it.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}, "additionalProperties": False}},
    {"name": "workspace_read", "description": "Read a UTF-8 text file in the selected workspace (not secrets or binary files).",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}},
    {"name": "workspace_search", "description": "Search local source/text files by substring, or find code declarations with mode=symbols (read-only, bounded).",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                                                "mode": {"type": "string", "enum": ["text", "symbols"], "default": "text"}},
                     "required": ["query"], "additionalProperties": False}},
    {"name": "workspace_write", "description": "Create or update a UTF-8 text file inside the selected workspace. Requires workspace edit mode.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                     "required": ["path", "content"], "additionalProperties": False}},
]
TOOL_NAMES = {t['name'] for t in TOOLS}


class Workspace:
    def __init__(self, root: Path):
        root = root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Workspace must be an existing directory')
        self.root = root

    def resolve(self, relative: str, *, allow_missing: bool = False) -> Path:
        if not relative or len(relative) > 500:
            raise ValueError('Invalid file path')
        value = Path(relative)
        if value.is_absolute():
            raise PermissionError('Absolute paths are blocked')
        candidate = (self.root / value).resolve(strict=not allow_missing)
        if not candidate.is_relative_to(self.root):
            raise PermissionError('Path escapes the selected workspace')
        if any(part.lower() in DENIED_NAMES for part in candidate.relative_to(self.root).parts):
            raise PermissionError('Private/credential directories and files are protected')
        if candidate.suffix.lower() in DENIED_SUFFIXES:
            raise PermissionError('Sensitive file type blocked')
        return candidate

    def call(self, name: str, args: dict[str, Any], *, allow_write: bool = False) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            raise ValueError('Unknown workspace tool')
        if not isinstance(args, dict):
            raise ValueError('Arguments must be an object')
        from jsonschema import validate
        schema = next(t['inputSchema'] for t in TOOLS if t['name'] == name)
        validate(args, schema)
        if name == 'workspace_list':
            path = self.resolve(args.get('path', '.'))
            if not path.is_dir():
                raise ValueError('Not a directory')
            items = []
            for p in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                try:
                    self.resolve(p.relative_to(self.root).as_posix())
                except (PermissionError, OSError, ValueError):
                    continue
                items.append({'name': p.name, 'type': 'directory' if p.is_dir() else 'file'})
                if len(items) >= 150:
                    break
            return {'path': path.relative_to(self.root).as_posix(), 'items': items}
        if name == 'workspace_read':
            path = self.resolve(args['path'])
            if not path.is_file() or path.stat().st_size > MAX_READ_BYTES:
                raise ValueError('Not a small text file')
            return {'path': args['path'], 'content': path.read_text(encoding='utf-8')}
        if name == 'workspace_search':
            from .code_navigation import search_workspace
            return search_workspace(self, args['query'], mode=args.get('mode', 'text'))
        if not allow_write:
            raise PermissionError('Workspace editing is switched off')
        path = self.resolve(args['path'], allow_missing=True)
        data = args['content'].encode('utf-8')
        if len(data) > MAX_WRITE_BYTES:
            raise ValueError('File exceeds write limit')
        if path.exists() and not path.is_file():
            raise ValueError('Target is not a regular file')
        path.parent.mkdir(parents=True, exist_ok=True)
        # Unique temp file in the same directory avoids symlink replacement attacks
        # against a predictable .star-tmp filename.
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.star-write-', dir=path.parent,
                                             delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(data)
            os.replace(tmp_path, path)
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        return {'path': path.relative_to(self.root).as_posix(), 'bytes_written': len(data)}
