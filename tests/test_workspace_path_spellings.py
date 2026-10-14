"""Workspace tools: Windows path spellings must not slip past the protected-name checks.

Windows drops trailing dots and spaces when it opens a path, so before this fix
`workspace_write` with `.git./config` created `.git/config` (and `.env.` created `.env`)
although `.git` and `.env` are protected. These run on every platform: the refusal
happens before the file system is touched.
"""
from __future__ import annotations

import os

import pytest

from star.workspace import Workspace


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=fake", encoding="utf-8")
    return Workspace(tmp_path)


@pytest.mark.parametrize("path", [
    ".git./config",
    ".git /config",
    ".github./workflows/ci.yml",
    ".env.",
    ".env ",
    ".ssh./authorized_keys",
    "deploy.key.",
    "server.pem ",
    ".env::$DATA",
    "notes.txt:hidden",
    "nul",
    "CON.txt",
    "sub/com1.log",
    "C:evil.txt",
    ".env.local",
    ".ENV.Production",
    ".git-credentials",
    ".netrc",
])
def test_write_refuses_protected_or_ambiguous_spellings(ws, path):
    with pytest.raises(PermissionError):
        ws.call("workspace_write", {"path": path, "content": "x"}, allow_write=True)
    names = {p.name for p in ws.root.rglob("*")}
    assert names <= {"notes.txt", ".env"}, names


@pytest.mark.parametrize("path", [".env.", ".env::$DATA", ".ENV ", ".env.local"])
def test_read_refuses_protected_spellings(ws, path):
    with pytest.raises(PermissionError):
        ws.call("workspace_read", {"path": path})


def test_ordinary_paths_still_work(ws):
    out = ws.call("workspace_write", {"path": "src/game.lua", "content": "print(1)"}, allow_write=True)
    assert out["path"] == "src/game.lua"
    assert ws.call("workspace_read", {"path": "src/game.lua"})["content"] == "print(1)"
    assert ws.call("workspace_write", {"path": ".env.example", "content": "TOKEN="}, allow_write=True)
    assert ws.call("workspace_read", {"path": "notes.txt"})["content"] == "hello"
    assert ws.call("workspace_read", {"path": "./notes.txt"})["content"] == "hello"
    listed = {item["name"] for item in ws.call("workspace_list", {"path": "."})["items"]}
    assert "notes.txt" in listed and ".env" not in listed


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_link_to_protected_file_is_refused(ws):
    try:
        os.symlink(ws.root / ".env", ws.root / "innocent.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    with pytest.raises(PermissionError):
        ws.call("workspace_read", {"path": "innocent.txt"})
