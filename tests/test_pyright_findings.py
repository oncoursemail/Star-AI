"""Regressions for bugs pyright found, and the pyright baseline gate itself."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from star import cli, learned_week, studio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pyright_baseline as gate  # noqa: E402


def test_doctor_reports_a_custom_studio_launcher_without_crashing(monkeypatch, capsys):
    # A host-defined launcher has no local mcp.bat, so launcher() returns None for the path.
    monkeypatch.setattr(studio, "launcher", lambda *args, **kwargs: ("ssh", ["studio-host", "mcp"], None))
    cli.doctor()
    out = capsys.readouterr().out
    assert "Roblox MCP: custom launcher configured" in out
    assert "AttributeError" not in out and "studio-host" not in out


def test_doctor_still_checks_the_local_launcher_file(monkeypatch, capsys, tmp_path):
    missing = tmp_path / "mcp.bat"
    monkeypatch.setattr(studio, "launcher", lambda *args, **kwargs: ("cmd.exe", [], missing))
    cli.doctor()
    assert f"Roblox MCP: NOT FOUND {missing}" in capsys.readouterr().out


def test_learned_week_help_works_without_docstrings(monkeypatch, capsys):
    # `python -OO` (or an optimised frozen build) strips module docstrings.
    monkeypatch.setattr(learned_week, "__doc__", None)
    with pytest.raises(SystemExit) as stopped:
        learned_week.main(["--help"])
    assert stopped.value.code == 0
    assert "python -m star.learned_week" in capsys.readouterr().out


def _report(tmp_path: Path, errors: list[tuple[str, str]]) -> Path:
    diagnostics = [{"file": str(gate.ROOT / name), "severity": "error", "rule": rule, "message": "m",
                    "range": {"start": {"line": 0, "character": 0}}} for name, rule in errors]
    diagnostics.append({"file": str(gate.ROOT / "star/a.py"), "severity": "warning", "rule": "x", "message": "w",
                        "range": {"start": {"line": 0, "character": 0}}})
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"generalDiagnostics": diagnostics, "summary": {}}), encoding="utf-8")
    return path


def test_baseline_gate_blocks_new_errors_and_allows_fixes(tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    start = _report(tmp_path, [("star/a.py", "reportCallIssue"), ("star/a.py", "reportCallIssue"),
                               ("star/b.py", "reportArgumentType")])
    assert gate.main(["update", str(start), "--baseline", str(baseline)]) == 0
    assert json.loads(baseline.read_text()) == {"star/a.py::reportCallIssue": 2, "star/b.py::reportArgumentType": 1}
    assert gate.main(["check", str(start), "--baseline", str(baseline)]) == 0

    fewer = _report(tmp_path, [("star/a.py", "reportCallIssue")])
    assert gate.main(["check", str(fewer), "--baseline", str(baseline)]) == 0
    assert "2 fixed since the baseline" in capsys.readouterr().out

    worse = _report(tmp_path, [("star/a.py", "reportCallIssue")] * 2 + [("star/c.py", "reportCallIssue")])
    assert gate.main(["check", str(worse), "--baseline", str(baseline)]) == 1
    out = capsys.readouterr().out
    assert "star/c.py::reportCallIssue: 1 errors, baseline allows 0" in out
    assert "star/a.py" not in out.split("New pyright errors")[1].split("star/c.py")[0]


def test_baseline_keys_are_repo_relative_on_any_os():
    assert gate._relative(str(gate.ROOT / "star" / "voice" / "call.py")) == "star/voice/call.py"
    assert gate._relative("/home/runner/work/Star-AI/Star-AI/star/cli.py") == "star/cli.py"
