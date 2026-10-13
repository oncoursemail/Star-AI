"""REA preparation is offline identity evidence, never arbitrary code execution."""
import hashlib
import struct

import pytest

from star.workspace import Workspace, TOOL_NAMES


def test_triage_pe_machine_and_sha256(tmp_path):
    doc = bytearray(512)
    doc[:2] = b"MZ"
    struct.pack_into("<I", doc, 0x3C, 128)
    doc[128:132] = b"PE\x00\x00"
    struct.pack_into("<HH", doc, 132, 0x8664, 5)
    struct.pack_into("<H", doc, 152, 0x20B)
    (tmp_path / "game.exe").write_bytes(doc)
    report = Workspace(tmp_path).call("workspace_binary_triage", {"path": "game.exe"})
    assert "workspace_binary_triage" in TOOL_NAMES
    assert report["format"] == "PE" and report["architecture"] == "x86_64"
    assert report["optional_header"] == "PE32+" and report["sections_declared"] == 5
    assert report["sha256"] == hashlib.sha256(doc).hexdigest()
    assert report["read_only"] and not report["executed"] and not report["disassembled"]


def test_elf_webassembly_and_macho_header_only(tmp_path):
    elf = bytearray(64)
    elf[:4] = b"\x7fELF"
    elf[4] = 2
    elf[5] = 1
    struct.pack_into("<H", elf, 18, 0x3E)
    (tmp_path / "lib.so").write_bytes(elf)
    out = Workspace(tmp_path).call("workspace_binary_triage", {"path": "lib.so"})
    assert (out["format"], out["word_size"], out["architecture"]) == ("ELF", 64, "x86_64")
    (tmp_path / "demo.wasm").write_bytes(b"\x00asm\x01\x00\x00\x00")
    assert Workspace(tmp_path).call("workspace_binary_triage", {"path": "demo.wasm"})["format"] == "WebAssembly"
    (tmp_path / "app.dylib").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 20)
    assert Workspace(tmp_path).call("workspace_binary_triage", {"path": "app.dylib"})["word_size"] == 64


def test_invalid_and_out_of_workspace_binaries_fail_closed(tmp_path):
    (tmp_path / "wrong.exe").write_bytes(b"MZ" + b"\x00" * 20)
    (tmp_path / "text.py").write_text("print('not a binary')")
    (tmp_path / "fake.bin").write_bytes(b"x" * 20)
    ws = Workspace(tmp_path)
    for path in ("wrong.exe", "fake.bin", "text.py", ".."):
        with pytest.raises((ValueError, PermissionError)):
            ws.call("workspace_binary_triage", {"path": path})
    with pytest.raises(ValueError):
        ws.call("workspace_binary_triage", {"path": "fake.bin", "shell": "ghidra"})
    with pytest.raises(ValueError):
        ws.call("workspace_binary_triage", {"path": "fake.bin", "execute": True})


def test_triage_cannot_run_unknown_or_oversized_binary_payloads(tmp_path, monkeypatch):
    import subprocess
    from star import binary_evidence as binary

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Read-only binary triage must never execute a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    (tmp_path / "unknown.bin").write_bytes(b"not-an-executable")
    with pytest.raises(ValueError, match="Unrecognized"):
        Workspace(tmp_path).call("workspace_binary_triage", {"path": "unknown.bin"})
    (tmp_path / "module.wasm").write_bytes(b"\x00asm\x01\x00\x00\x00")
    monkeypatch.setattr(binary, "MAX_BINARY_BYTES", 7)
    with pytest.raises(ValueError, match="size"):
        Workspace(tmp_path).call("workspace_binary_triage", {"path": "module.wasm"})
