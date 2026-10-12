"""Offline recorded-output tests exercising STAR's real Luau lint and craft paths."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from star import luau_analyze
from star.luau_lint import Finding, lint
from star.roblox_craft import audit
from star.intelligence import LocalIntelligence


CODE = '--!strict\nlocal points: number = "incorrect"\nreturn points\n'


@pytest.fixture(autouse=True)
def clear_once_notices(monkeypatch):
    monkeypatch.setattr(luau_analyze, "_notified", set())


def fake_analyzer(monkeypatch, *, stderr="", status=0, stdout="", exception=None):
    monkeypatch.setattr(luau_analyze.shutil, "which", lambda name: "/tools/luau-analyze")
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv == ["/tools/luau-analyze", "--mode=strict", "-"]
        assert kwargs["input"].startswith("--!strict")
        assert kwargs["capture_output"] and kwargs["check"] is False
        assert kwargs["timeout"] == 6
        assert kwargs["text"] is True
        assert kwargs["cwd"] and kwargs["env"]["HOME"] == kwargs["cwd"]
        assert "API_KEY" not in kwargs["env"]
        if exception is not None:
            raise exception
        return SimpleNamespace(returncode=status, stderr=stderr, stdout=stdout)

    monkeypatch.setattr(luau_analyze.subprocess, "run", run)
    return calls


def test_opt_out_is_byte_identical_and_no_binary_lookup(monkeypatch, tmp_path):
    monkeypatch.setenv(luau_analyze.ENV_VAR, "off")
    monkeypatch.setattr(luau_analyze.shutil, "which",
                        lambda _: (_ for _ in ()).throw(AssertionError("must remain off")))
    baseline = lint(CODE, external=False)
    assert lint(CODE) == baseline
    scripts = [{"path": "ServerScriptService.Test", "class": "Script", "source": CODE}]
    expected = audit([], scripts)
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False)
    names = {tool["name"] for tool in hub.definitions("Audit Roblox VFX")}
    actual = hub.call("star_roblox_craft_audit",
                      {"instances": [], "scripts": scripts}, enabled=names)
    assert actual == expected
    assert not any(f["rule"].startswith("luau-analyze") for f in actual["findings"])


def test_recorded_syntax_type_and_lint_diagnostics_extend_lint(monkeypatch):
    calls = fake_analyzer(monkeypatch, status=1, stderr=(
        "stdin(1,7): SyntaxError: Expected identifier when parsing expression\n"
        "stdin(2,8): TypeError: Type 'string' could not be converted into 'number'\n"
        "stdin(3,1): UnusedLocal: Unused local 'unused'\n"))
    actual = lint(CODE, external=True)
    assert [f.rule_id for f in actual] == [
        "luau-analyze-syntaxerror", "luau-analyze-typeerror", "luau-analyze-unusedlocal"]
    assert actual[0] == Finding("luau-analyze-syntaxerror", 1,
                                "SyntaxError: Expected identifier when parsing expression",
                                "Repair Luau syntax before running the script.", "error")
    assert actual[1].severity == "warning" and actual[2].severity == "review"
    assert len(calls) == 1


def test_missing_binary_warns_once_then_original_self_check(monkeypatch):
    monkeypatch.setattr(luau_analyze.shutil, "which", lambda _: None)
    monkeypatch.delenv(luau_analyze.TOOLS_DIR_VAR, raising=False)
    monkeypatch.setenv(luau_analyze.ENV_VAR, "on")
    original = lint(CODE, external=False)
    with pytest.warns(RuntimeWarning, match="missing") as notices:
        assert lint(CODE) == original
        assert lint(CODE) == original
        assert audit([], [{"path": "ServerScriptService.T", "class": "Script", "source": CODE}])
    assert len(notices) == 1


def test_unknown_roblox_globals_do_not_become_game_errors(monkeypatch):
    calls = fake_analyzer(monkeypatch, status=1,
                          stderr="stdin(2,10): TypeError: Unknown global 'game'\n")
    result = luau_analyze.analyze("--!strict\nreturn game:GetService('Players')")
    assert result == [] and len(calls) == 1


def test_unknown_nonroblox_global_is_still_reported(monkeypatch):
    fake_analyzer(monkeypatch, status=1,
                  stderr="stdin(2,2): TypeError: Unknown global 'pointss'\n")
    assert "pointss" in luau_analyze.analyze(CODE)[0].message


def test_pinned_tools_folder_takes_precedence(monkeypatch, tmp_path):
    suffix = "luau-analyze.exe" if luau_analyze.os.name == "nt" else "luau-analyze"
    target = tmp_path / "luau-0.691" / suffix
    target.parent.mkdir()
    target.write_text("fake")
    monkeypatch.setattr(luau_analyze.shutil, "which",
                        lambda _: (_ for _ in ()).throw(AssertionError("must choose pinned")))
    assert luau_analyze.locate_analyzer(tools_root=tmp_path) == str(target)


@pytest.mark.parametrize("failure", [
    subprocess.TimeoutExpired(cmd=["luau-analyze"], timeout=6),
    OSError("opaque secret-like diagnostic"),
], ids=["timeout", "os-error"])
def test_tool_failures_fallback_without_leaking(monkeypatch, failure):
    fake_analyzer(monkeypatch, exception=failure)
    with pytest.warns(RuntimeWarning, match="could not run"):
        assert lint(CODE, external=True) == lint(CODE, external=False)


def test_unrecognized_binary_result_reports_only_generic_warning(monkeypatch):
    fake_analyzer(monkeypatch, status=2,
                  stderr="a local folder containing confidential tokens")
    with pytest.warns(RuntimeWarning, match="invalid result") as notices:
        assert luau_analyze.analyze(CODE) == []
    assert "confidential" not in str(notices[0].message)


def test_recorded_parser_enforces_stdin_origin_and_skips_engine_types():
    parsed = luau_analyze.parse_diagnostics(
        "private.lua(1,1): SyntaxError: not from stdin\n"
        "stdin(7,2): SyntaxError: bad Luau\n"
        "stdin(8,1): TypeError: Unknown type 'Instance'\n")
    assert len(parsed) == 1
    assert parsed[0].line == 7 and parsed[0].rule_id == "luau-analyze-syntaxerror"


def test_real_craft_audit_tool_dispatch_adds_analyzer_finding(monkeypatch, tmp_path):
    monkeypatch.setenv(luau_analyze.ENV_VAR, "on")
    calls = fake_analyzer(monkeypatch, stderr=(
        "stdin(2,1): SyntaxError: Malformed function definition\n"), status=1)
    hub = LocalIntelligence(home=tmp_path, skills_enabled=False, graphify_enabled=False)
    available = {t["name"] for t in hub.definitions("Audit Roblox UI and VFX")}
    result = hub.call("star_roblox_craft_audit", {
        "instances": [],
        "scripts": [{"path": "ServerScriptService.Module", "class": "Script",
                     "source": "--!strict\nlocal = 2"}]}, enabled=available)
    errors = [f for f in result["findings"] if f["rule"] == "luau-analyze-syntaxerror"]
    assert len(errors) == 1
    assert errors[0]["path"] == "ServerScriptService.Module"
    assert errors[0]["severity"] == "error"
    assert errors[0]["certainty"] == "analyzer"
    assert errors[0]["documentation"] == "https://create.roblox.com/docs/luau/type-checking"
    assert len(calls) == 1 and result["read_only"] and result["executed"] is False


def test_craft_bounds_calls_to_three_and_discloses_limit(monkeypatch):
    monkeypatch.setenv(luau_analyze.ENV_VAR, "on")
    calls = fake_analyzer(monkeypatch)
    scripts = [{"path": f"ServerScriptService.Mod{i}", "class": "Script", "source": CODE}
               for i in range(4)]
    report = audit([], scripts)
    assert len(calls) == 3
    assert any("three" in note for note in report["limitations"])


def test_large_source_rejected_without_tool_lookup(monkeypatch):
    monkeypatch.setattr(luau_analyze.shutil, "which",
                        lambda _: (_ for _ in ()).throw(AssertionError("too large")))
    with pytest.warns(RuntimeWarning, match="oversized"):
        assert luau_analyze.analyze("x" * 20_001) == []
