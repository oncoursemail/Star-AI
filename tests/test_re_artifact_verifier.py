"""Offline acceptance checks for STAR's independent RE byte-comparison oracle.

No external analysis engines, file writes by the tool, process execution or
network are needed. These tests do not claim real game/ROM equivalence.
"""
from __future__ import annotations

import hashlib
import subprocess

import pytest
from jsonschema import ValidationError

from star.reverse_engineering import ReverseEngineering


@pytest.fixture
def gateway(tmp_path):
    (tmp_path / "reference.bin").write_bytes(b"HEADER-abcdefgh-PAYLOAD")
    (tmp_path / "rebuilt.bin").write_bytes(b"HEADER-abcdefgh-PAYLOAD")
    return ReverseEngineering(workspace=tmp_path)


def _compare(gateway, **extra):
    return gateway.call("re_compare_artifacts", {
        "reference_path": "reference.bin",
        "candidate_path": "rebuilt.bin",
        **extra,
    })


def test_compare_is_available_only_with_the_opt_in_re_gateway(gateway):
    tools = {tool["name"] for tool in gateway.definitions("Compare my own binary build")}
    assert "re_compare_artifacts" in tools
    assert not gateway.definitions("What's the weather?")
    assert not gateway.definitions("Help bypass Byfron anti-cheat")
    assert "re_compare_artifacts" in gateway.status()["verification_tools"]
    with pytest.raises(PermissionError, match="not enabled"):
        gateway.call("re_compare_artifacts", {
            "reference_path": "reference.bin", "candidate_path": "rebuilt.bin",
        }, enabled={"re_identify"})


def test_whole_file_pass_is_only_byte_equality(gateway, monkeypatch):
    def reject(*_args, **_kwargs):
        raise AssertionError("Byte comparison must not execute any program")
    monkeypatch.setattr(subprocess, "run", reject)
    monkeypatch.setattr(subprocess, "Popen", reject)
    raw = b"HEADER-abcdefgh-PAYLOAD"
    out = _compare(gateway, expected_reference_sha256=hashlib.sha256(raw).hexdigest())
    assert out["verdict"] == "PASS" and out["bytes_equal"]
    assert out["reference_sha256"] == out["candidate_sha256"]
    assert out["reference_pin_matches"] is True
    assert out["first_difference_at"] is None
    assert out["matching_prefix_bytes"] == len(raw)
    assert out["read_only"] and not out["executed"] and not out["runtime_verified"]
    assert out["reference_provenance"] == "not_authenticated"
    assert "program safety" in out["notice"]


def test_mismatching_pin_fails_even_when_bytes_match(gateway):
    out = _compare(gateway, expected_reference_sha256="0" * 64)
    assert out["verdict"] == "FAIL"
    assert out["bytes_equal"] and out["reference_pin_matches"] is False


def test_rebuild_first_mismatch_and_size_difference(gateway, tmp_path):
    (tmp_path / "rebuilt.bin").write_bytes(b"HEADER-abXdefgh-PAYLOAD")
    out = _compare(gateway)
    assert out["verdict"] == "FAIL" and not out["bytes_equal"]
    assert out["first_difference_at"] == 9 and out["matching_prefix_bytes"] == 9
    (tmp_path / "rebuilt.bin").write_bytes(b"HEADER-abcdefgh-PAYLOAD!")
    longer = _compare(gateway)
    assert longer["verdict"] == "FAIL"
    assert longer["first_difference_at"] == len(b"HEADER-abcdefgh-PAYLOAD")


def test_range_compare_can_check_functions_at_different_offsets(gateway, tmp_path):
    (tmp_path / "rebuilt.bin").write_bytes(b"___abcdefgh___")
    out = _compare(gateway, scope="byte_range", reference_offset=7, candidate_offset=3, length=8,
                   expected_reference_sha256=hashlib.sha256(b"abcdefgh").hexdigest())
    assert out["verdict"] == "PASS"
    assert out["reference_bytes_compared"] == 8
    assert out["reference_sha256"] == hashlib.sha256(b"abcdefgh").hexdigest()
    assert out["candidate_sha256"] == out["reference_sha256"]
    assert out["reference_offset"] == 7 and out["candidate_offset"] == 3


@pytest.mark.parametrize("extra,reason", [
    ({"scope": "byte_range"}, "Byte range"),
    ({"scope": "byte_range", "length": 0}, "not a"),  # blocked by JSON schema
    ({"scope": "byte_range", "length": 1048577}, "not a"),  # schema
    ({"scope": "byte_range", "length": 30}, "extends beyond"),
    ({"scope": "whole_file", "length": 2}, "Whole-file"),
    ({"scope": "whole_file", "reference_offset": 1}, "Whole-file"),
])
def test_rejects_invalid_scopes(gateway, extra, reason):
    if reason == "not a":
        with pytest.raises(ValidationError):
            _compare(gateway, **extra)
    else:
        with pytest.raises(ValueError, match=reason):
            _compare(gateway, **extra)


def test_rejects_same_file_and_empty_inputs(gateway, tmp_path):
    with pytest.raises(ValueError, match="different files"):
        gateway.call("re_compare_artifacts", {
            "reference_path": "reference.bin", "candidate_path": "reference.bin",
        })
    (tmp_path / "rebuilt.bin").write_bytes(b"")
    with pytest.raises(ValueError, match="nonempty"):
        _compare(gateway)


def test_does_not_read_outside_workspace_or_secrets(gateway, tmp_path):
    (tmp_path / ".env").write_text("SECRET=notread")
    for path in ("../elsewhere.bin", "/tmp/elsewhere.bin", ".env"):
        with pytest.raises((ValueError, PermissionError)):
            gateway.call("re_compare_artifacts", {
                "reference_path": path, "candidate_path": "rebuilt.bin",
            })


def test_extra_arguments_and_bad_sha256_rejected(gateway):
    for extra in ({"shell": "true"}, {"expected_reference_sha256": "not-a-hash"},
                  {"scope": "whatever"}):
        with pytest.raises(ValidationError):
            _compare(gateway, **extra)


def test_chunk_boundary_and_reference_shorter(gateway, tmp_path):
    # Tests that only the earliest mismatch is reported across chunk boundaries.
    (tmp_path / "reference.bin").write_bytes(b"a" * 65536 + b"b")
    (tmp_path / "rebuilt.bin").write_bytes(b"a" * 65536 + b"c")
    out = _compare(gateway)
    assert out["first_difference_at"] == 65536 and not out["bytes_equal"]
    (tmp_path / "rebuilt.bin").write_bytes(b"a" * 65536)
    out = _compare(gateway)
    assert out["first_difference_at"] == 65536 and out["verdict"] == "FAIL"
