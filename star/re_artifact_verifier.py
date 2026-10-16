"""Independent, read-only byte verification for permitted local RE projects.

This is a comparison oracle, not a decompiler, code executor, or proof of
functional/semantic equivalence. The trusted gateway in reverse_engineering.py
must resolve workspace paths *before* calling this module.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_RANGE_BYTES = 1024 * 1024
_CHUNK = 64 * 1024


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    """Detect ordinary file substitution/mutation during the read."""
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _check_unchanged(file, path: Path, before: os.stat_result) -> None:
    if _identity(os.fstat(file.fileno())) != _identity(before):
        raise ValueError("An artifact changed while it was being verified")
    if _identity(path.stat()) != _identity(before):
        raise ValueError("An artifact path changed while it was being verified")


def compare_artifacts(
    reference: Path,
    candidate: Path,
    *,
    reference_label: str,
    candidate_label: str,
    scope: str = "whole_file",
    reference_offset: int = 0,
    candidate_offset: int = 0,
    length: int | None = None,
    expected_reference_sha256: str | None = None,
) -> dict:
    """Compare two distinct local regular files or equal-length bounded ranges.

    SHA-256 pins are caller supplied, NOT authenticated by this function.
    Reference integrity, authorization and runtime correctness need separate
    evidence. The result never calls a byte mismatch a match, and never writes
    either file or executes target code.
    """
    if scope not in {"whole_file", "byte_range"}:
        raise ValueError("scope must be whole_file or byte_range")
    if reference.samefile(candidate):
        raise ValueError("Reference and candidate must be different files")
    original = reference.stat()
    rebuilt = candidate.stat()
    if not stat.S_ISREG(original.st_mode) or not stat.S_ISREG(rebuilt.st_mode):
        raise ValueError("Both artifacts must be regular files")
    if not (0 < original.st_size <= MAX_ARTIFACT_BYTES and 0 < rebuilt.st_size <= MAX_ARTIFACT_BYTES):
        raise ValueError("Artifacts must be nonempty and no larger than 128 MiB")
    if expected_reference_sha256 is not None:
        if not isinstance(expected_reference_sha256, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", expected_reference_sha256
        ):
            raise ValueError("Expected reference SHA-256 must be 64 hex characters")

    if scope == "whole_file":
        if length is not None or reference_offset != 0 or candidate_offset != 0:
            raise ValueError("Whole-file comparison cannot specify offsets or length")
        a_total, b_total = original.st_size, rebuilt.st_size
    else:
        if any(type(x) is not int or x < 0 for x in (reference_offset, candidate_offset)):
            raise ValueError("Byte-range offsets must be nonnegative integers")
        if type(length) is not int or not (1 <= length <= MAX_RANGE_BYTES):
            raise ValueError("Byte range must have a length between 1 and 1048576 bytes")
        if reference_offset + length > original.st_size or candidate_offset + length > rebuilt.st_size:
            raise ValueError("Byte range extends beyond one of the selected files")
        a_total = b_total = length

    a_hash, b_hash = hashlib.sha256(), hashlib.sha256()
    first_difference = None
    position = 0

    with reference.open("rb") as a, candidate.open("rb") as b:
        _check_unchanged(a, reference, original)
        _check_unchanged(b, candidate, rebuilt)
        a.seek(reference_offset)
        b.seek(candidate_offset)
        a_left, b_left = a_total, b_total
        while a_left or b_left:
            a_bytes = a.read(min(a_left, _CHUNK)) if a_left else b""
            b_bytes = b.read(min(b_left, _CHUNK)) if b_left else b""
            if (a_left and not a_bytes) or (b_left and not b_bytes):
                raise ValueError("An artifact ended unexpectedly during verification")
            a_left -= len(a_bytes)
            b_left -= len(b_bytes)
            a_hash.update(a_bytes)
            b_hash.update(b_bytes)
            if first_difference is None and a_bytes != b_bytes:
                # Relative to the selected regions, not an RVA/virtual address.
                mismatch = next(
                    (i for i, (left, right) in enumerate(zip(a_bytes, b_bytes)) if left != right),
                    min(len(a_bytes), len(b_bytes)),
                )
                first_difference = position + mismatch
            position += max(len(a_bytes), len(b_bytes))
        _check_unchanged(a, reference, original)
        _check_unchanged(b, candidate, rebuilt)

    reference_hash = a_hash.hexdigest()
    candidate_hash = b_hash.hexdigest()
    pinned = None if expected_reference_sha256 is None else (
        reference_hash == expected_reference_sha256.lower()
    )
    equal = first_difference is None and a_total == b_total
    passed = equal and pinned is not False
    return {
        "verdict": "PASS" if passed else "FAIL",
        "bytes_equal": equal,
        "scope": scope,
        "reference_path": reference_label,
        "candidate_path": candidate_label,
        "reference_offset": reference_offset,
        "candidate_offset": candidate_offset,
        "reference_bytes_compared": a_total,
        "candidate_bytes_compared": b_total,
        "first_difference_at": first_difference,
        "matching_prefix_bytes": min(a_total, b_total) if equal else first_difference,
        "reference_sha256": reference_hash,
        "candidate_sha256": candidate_hash,
        "reference_pin_matches": pinned,
        "read_only": True,
        "executed": False,
        "runtime_verified": False,
        "reference_provenance": "not_authenticated",
        "notice": (
            "PASS means only that the specified bytes matched locally"
            + (" and the caller-supplied reference SHA-256 matched." if pinned is not None else ".")
            + " It does not establish a trusted baseline, function semantics, gameplay,"
            " program safety, copyright permission, or a working native port."
        ),
    }
