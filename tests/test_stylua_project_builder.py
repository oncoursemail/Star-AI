"""StyLua opt-in tests drive the real project builder and CLI paths offline."""
from __future__ import annotations

import hashlib
import json
import subprocess
from types import SimpleNamespace

import pytest

from star import project_builder as builder
from star import stylua_format as stylua


MODULE = [{"name": "Library", "kind": "shared", "purpose": "Test",
           "interface": ["run"], "requires": []}]
CODE = "local M = {}\nfunction M.run() return true end\nreturn M\n"
FENCED = "```luau\n" + CODE + "```"
FORMATTED = "local M = {}\nfunction M.run()\n    return true\nend\nreturn M\n"


def plan_file(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(MODULE), encoding="utf-8")
    return path


def generated_file(root):
    return root / "src/ReplicatedStorage/Shared/Library.lua"


def fake_binary(monkeypatch, outcomes):
    monkeypatch.setattr(stylua.shutil, "which",
                        lambda binary: "/opt/stylua" if binary == "stylua" else None)
    received = []
    outcomes = iter(outcomes)

    def run(argv, **kwargs):
        received.append((argv, kwargs))
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(returncode=value[0], stdout=value[1], stderr=value[2])

    monkeypatch.setattr(stylua.subprocess, "run", run)
    return received


def test_default_cli_keeps_original_bytes_without_accessing_stylua(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(builder, "_configured_generator", lambda: lambda _: FENCED)
    monkeypatch.setattr(stylua, "installed_formatter",
                        lambda: (_ for _ in ()).throw(AssertionError("must remain off")))
    out = tmp_path / "output"
    assert builder.main(["--plan", str(plan_file(tmp_path)), "--out", str(out)]) == 0
    source = generated_file(out).read_text(encoding="utf-8")
    assert source == "--!strict\n\n" + CODE
    result = json.loads(capsys.readouterr().out)
    assert result["generated"][0]["sha256"] == hashlib.sha256(source.encode()).hexdigest()


def test_opt_in_cli_formats_model_code_and_revalidates_real_build(tmp_path, monkeypatch, capsys):
    calls = fake_binary(monkeypatch, [(0, FORMATTED, "")])
    monkeypatch.setattr(builder, "_configured_generator", lambda: lambda _: FENCED)
    out = tmp_path / "formatted"
    assert builder.main(["--plan", str(plan_file(tmp_path)),
                         "--out", str(out), "--stylua"]) == 0
    source = generated_file(out).read_text(encoding="utf-8")
    assert source == "--!strict\n\n" + FORMATTED
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "complete"
    assert result["generated"][0]["sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == ["/opt/stylua", "--syntax", "Luau", "--indent-type", "Spaces",
                    "--indent-width", "4", "--line-endings", "Unix", "--no-editorconfig", "-"]
    assert kwargs["input"] == CODE
    assert "--!strict" not in kwargs["input"]  # trusted prefix stays untouched
    assert kwargs["capture_output"] is True and kwargs["check"] is False
    assert kwargs["timeout"] == 10 and kwargs["text"] is True


def test_stylua_rejection_retries_syntax_the_static_validator_cannot_parse(tmp_path):
    malformed = "local M = {}\nfunction M.run() local x = * 1 return x end\nreturn M\n"
    assert builder.validate_code("```luau\n" + malformed + "```", ["run"])[1] is None
    called = []

    def formatter(code):
        called.append(code)
        if len(called) == 1:
            raise ValueError("parser rejected generated Luau")
        return FORMATTED

    responses = iter(["```luau\n" + malformed + "```", FENCED])
    result = builder.build_project(MODULE, tmp_path / "out", lambda _: next(responses),
                                   formatter=formatter)
    assert result["status"] == "complete"
    assert result["generated"][0]["attempts"] == 2
    assert result["generated"][0]["errors"] == ["StyLua could not format generated Luau"]
    assert generated_file(tmp_path / "out").read_text(encoding="utf-8").endswith(FORMATTED)
    assert len(called) == 2


def test_opt_in_cli_missing_binary_refuses_before_model_or_any_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stylua.shutil, "which", lambda _: None)
    monkeypatch.setattr(builder, "_configured_generator",
                        lambda: (_ for _ in ()).throw(AssertionError("no model call")))
    out = tmp_path / "must_not_exist"
    assert builder.main(["--plan", str(plan_file(tmp_path)),
                         "--out", str(out), "--stylua"]) == 2
    assert not out.exists()
    assert "could not start" in capsys.readouterr().err


def test_parser_failure_twice_is_not_a_generated_module(tmp_path):
    calls = []
    def reject(source):
        calls.append(source)
        raise ValueError("arbitrary external process output not for the model")

    result = builder.build_project(MODULE, tmp_path / "out", lambda _: FENCED,
                                   formatter=reject)
    assert result["status"] == "incomplete"
    assert not result["generated"] and len(calls) == 2
    assert result["failed"][0]["errors"] == [
        "StyLua could not format generated Luau", "StyLua could not format generated Luau",
    ]
    assert not generated_file(tmp_path / "out").exists()
    assert "arbitrary external" not in json.dumps(result)


def test_untrusted_formatter_cannot_inject_forbidden_call(tmp_path):
    altered = "local M = {}\nfunction M.run() loadstring('unsafe') end\nreturn M\n"
    result = builder.build_project(MODULE, tmp_path / "out", lambda _: FENCED,
                                   formatter=lambda _: altered)
    assert result["status"] == "incomplete"
    assert not generated_file(tmp_path / "out").exists()
    assert result["failed"][0]["error"] == "StyLua output rejected: Forbidden API detected"


def test_installed_adapter_rejects_process_timeout_without_leaking_error(tmp_path, monkeypatch):
    calls = fake_binary(monkeypatch, [
        subprocess.TimeoutExpired(cmd=["stylua"], timeout=10),
        subprocess.TimeoutExpired(cmd=["stylua"], timeout=10),
    ])
    formatter = stylua.installed_formatter()
    result = builder.build_project(MODULE, tmp_path / "out", lambda _: FENCED,
                                   formatter=formatter)
    assert len(calls) == 2
    assert result["status"] == "incomplete" and not result["generated"]
    assert result["failed"][0]["error"] == "StyLua could not format generated Luau"


def test_adapter_limits_nontext_and_oversized_data_before_process(monkeypatch):
    calls = fake_binary(monkeypatch, [])
    formatter = stylua.installed_formatter()
    with pytest.raises(ValueError, match="limit"):
        formatter("x" * (stylua.MAX_CODE_BYTES + 1))
    with pytest.raises(ValueError, match="limit"):
        formatter(None)
    assert calls == []


def test_formatter_must_be_callable_before_writes(tmp_path):
    with pytest.raises(TypeError, match="formatter"):
        builder.build_project(MODULE, tmp_path / "out", lambda _: FENCED, formatter=42)
    assert not (tmp_path / "out").exists()
