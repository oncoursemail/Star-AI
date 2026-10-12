"""Security regression tests for legacy release archive extraction.

No network, installer, GPU or keyring is required.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from star.updates import _extract_update


def _zip(path, entries):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_legacy_update_rejects_parent_symlink_before_writing(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    try:
        (target / "bundle").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted by this platform")

    source = tmp_path / "release.zip"
    _zip(source, {"bundle/STAR.exe": b"payload"})
    with pytest.raises(ValueError, match="Unsafe release ZIP destination"):
        _extract_update(source, target)
    assert not (outside / "STAR.exe").exists()


def test_legacy_update_rejects_file_symlink_and_preserves_target(tmp_path):
    outside = tmp_path / "original.bin"
    outside.write_bytes(b"preserve")
    target = tmp_path / "target"
    target.mkdir()
    try:
        (target / "STAR.exe").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted by this platform")

    source = tmp_path / "release.zip"
    _zip(source, {"STAR.exe": b"overwrite"})
    with pytest.raises(ValueError, match="Unsafe release ZIP destination"):
        _extract_update(source, target)
    assert outside.read_bytes() == b"preserve"


def test_legacy_update_extracts_normal_archive_and_refuses_overwrite(tmp_path):
    source = tmp_path / "release.zip"
    _zip(source, {"STAR.exe": b"MZ-test"})
    target = tmp_path / "target"
    _extract_update(source, target)
    assert (target / "STAR.exe").read_bytes() == b"MZ-test"
    with pytest.raises(ValueError, match="overwrite"):
        _extract_update(source, target)
    assert (target / "STAR.exe").read_bytes() == b"MZ-test"
