"""Read-only binary format triage as evidence preparation for REA/Ghidra.

This does NOT run, import, decrypt, decompile or disassemble the target. Only a
single owner-selected, workspace-scoped regular file is hashed and header-read.
Never pass user data to online analyzers or infer proprietary source licenses.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

MAX_BINARY_BYTES = 128_000_000
ALLOWED_SUFFIXES = frozenset({".exe", ".dll", ".sys", ".elf", ".so", ".dylib", ".wasm", ".bin"})
_MACHINE_PE = {
    0x014C: "x86", 0x8664: "x86_64", 0x01C4: "ARMv7", 0xAA64: "ARM64",
}
_MACHINE_ELF = {
    0x03: "x86", 0x3E: "x86_64", 0x28: "ARM", 0xB7: "ARM64", 0xF3: "RISC-V",
}


def _header(raw: bytes) -> dict:
    if raw.startswith(b"MZ"):
        if len(raw) < 64:
            raise ValueError("Truncated DOS executable header")
        offset = struct.unpack_from("<I", raw, 0x3C)[0]
        if offset > len(raw) - 24 or raw[offset:offset + 4] != b"PE\x00\x00":
            raise ValueError("Invalid or inaccessible PE signature")
        machine, sections = struct.unpack_from("<HH", raw, offset + 4)
        magic_at = offset + 24
        optional = struct.unpack_from("<H", raw, magic_at)[0] if magic_at + 2 <= len(raw) else 0
        return {
            "format": "PE", "architecture": _MACHINE_PE.get(machine, f"machine_0x{machine:04x}"),
            "sections_declared": sections,
            "optional_header": {0x10B: "PE32", 0x20B: "PE32+"}.get(optional, "unknown"),
        }
    if raw.startswith(b"\x7fELF"):
        if len(raw) < 20 or raw[4] not in (1, 2) or raw[5] not in (1, 2):
            raise ValueError("Invalid ELF identity or header")
        byteorder = "<" if raw[5] == 1 else ">"
        machine = struct.unpack_from(byteorder + "H", raw, 18)[0]
        return {
            "format": "ELF", "word_size": 32 if raw[4] == 1 else 64,
            "endianness": "little" if byteorder == "<" else "big",
            "architecture": _MACHINE_ELF.get(machine, f"machine_0x{machine:04x}"),
        }
    if raw.startswith(b"\x00asm"):
        if len(raw) < 8 or raw[4:8] != b"\x01\x00\x00\x00":
            raise ValueError("Unsupported WebAssembly version")
        return {"format": "WebAssembly", "version": 1}
    mach = {
        b"\xce\xfa\xed\xfe": ("Mach-O", "little", 32),
        b"\xcf\xfa\xed\xfe": ("Mach-O", "little", 64),
        b"\xfe\xed\xfa\xce": ("Mach-O", "big", 32),
        b"\xfe\xed\xfa\xcf": ("Mach-O", "big", 64),
        b"\xca\xfe\xba\xbe": ("Mach-O universal", "big", None),
        b"\xbe\xba\xfe\xca": ("Mach-O universal", "little", None),
    }
    if raw[:4] in mach:
        kind, endian, bits = mach[raw[:4]]
        return {"format": kind, "endianness": endian, "word_size": bits}
    raise ValueError("Unrecognized executable/library header; no analysis was attempted")


def triage(workspace, path: str) -> dict:
    file = workspace.resolve(path)
    if file.is_symlink() or not file.is_file() or file.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Select one regular binary file in the chosen workspace")
    size = file.stat().st_size
    if not 8 <= size <= MAX_BINARY_BYTES:
        raise ValueError("Binary size is outside the 8-byte to 128 MB triage limit")
    sha = hashlib.sha256()
    with file.open("rb") as reader:
        header = reader.read(min(size, 65_536))
        sha.update(header)
        read_size = len(header)
        while read_size < size:
            chunk = reader.read(min(262_144, size - read_size))
            if not chunk:
                raise ValueError("Binary changed while hashing")
            sha.update(chunk)
            read_size += len(chunk)
    if file.stat().st_size != size:
        raise ValueError("Binary size changed during triage")
    identity = _header(header)
    return {
        "path": file.relative_to(workspace.root).as_posix(), "bytes": size,
        "sha256": sha.hexdigest(), **identity,
        "read_only": True, "executed": False, "disassembled": False,
        "next_step": ("For authorized analysis, review and configure REA from "
                      "https://github.com/morluto/rea with a trusted local provider "
                      "(such as Ghidra). Obtain explicit scope approval before running it."),
        "notice": ("A header and digest establish format/identity only. They do not prove "
                   "code behavior, source recovery, ownership, copyright permissions, "
                   "malware safety, or a reproducible reconstruction."),
    }
