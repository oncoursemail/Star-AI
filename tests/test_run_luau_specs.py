"""Offline tests for scripts/run_luau_specs.py and the pinned Luau CI workflow.

Most of these need no Luau interpreter: they check the translation of the real
templates under examples/ and the runner's failure accounting. The tests that
execute Luau are skipped when no ``luau`` binary is installed; the dedicated
"Luau template specs" workflow always runs the real specs.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from scripts import run_luau_specs as runner

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
WORKFLOW = ROOT / ".github/workflows/luau-specs.yml"


def _digest_tree(root: pathlib.Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _make_template(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "examples"
    shared = root / "roblox-templates/demo/ReplicatedStorage/Shared"
    server = root / "roblox-templates/demo/ServerScriptService"
    (server / "Tests").mkdir(parents=True)
    shared.mkdir(parents=True)
    (shared / "Math.luau").write_text("return {}\n", encoding="utf-8")
    (server / "Svc.luau").write_text("return {}\n", encoding="utf-8")
    return root


def test_translate_rewrites_roblox_requires_and_keeps_line_numbers(tmp_path):
    root = _make_template(tmp_path)
    template = root / "roblox-templates/demo"
    source = template / "ServerScriptService/Tests/Svc.spec.luau"
    text = (
        "--!strict\n"
        'local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")\n'
        'local Math = require(Shared:WaitForChild("Math"))\n'
        'local Svc = require(game:GetService("ServerScriptService"):WaitForChild("Svc"))\n'
        'local Parent = require(script.Parent.Parent:WaitForChild("Svc"))\n'
        'local Missing = require(game:GetService("Players"):WaitForChild("Nope"))\n'
        'local Literal = require("./already_relative")\n'
        "return {}\n"
    )
    out = runner.translate(source, template, text)
    lines = out.splitlines()
    assert len(lines) == len(text.splitlines())
    assert lines[1] == "-- CLI service alias"
    assert lines[2] == 'local Math = require("../../ReplicatedStorage/Shared/Math")'
    assert lines[3] == 'local Svc = require("../Svc")'
    assert lines[4] == 'local Parent = require("../Svc")'
    # Unresolvable engine requires and literal requires are left alone, so an
    # executed spec still fails loudly instead of silently passing.
    assert lines[5] == text.splitlines()[5]
    assert lines[6] == text.splitlines()[6]


def test_stage_sources_translates_every_real_file_without_touching_the_repo(tmp_path):
    before = _digest_tree(EXAMPLES)
    stage = tmp_path / "stage"
    stage.mkdir()
    runner.stage_sources(EXAMPLES, stage)
    assert _digest_tree(EXAMPLES) == before, "the repository sources must never change"

    originals = sorted(EXAMPLES.rglob("*.luau"))
    assert originals
    for source in originals:
        staged = stage / source.relative_to(EXAMPLES)
        assert staged.is_file()
        assert len(staged.read_text(encoding="utf-8").splitlines()) == \
            len(source.read_text(encoding="utf-8").splitlines()), source
    for staged in stage.rglob("*.spec.luau"):
        for line in staged.read_text(encoding="utf-8").splitlines():
            assert not re.search(r"require\(\s*(game|script)\b", line), (staged, line)

    engine_dir = stage / "roblox-templates/rounds/ServerScriptService"
    assert (engine_dir / "__headless_engine.luau").is_file()
    factory = (engine_dir / "ArenaFactory.luau").read_text(encoding="utf-8")
    spec = (engine_dir / "Tests/ArenaFactory.spec.luau").read_text(encoding="utf-8")
    assert factory.startswith('local __engine = require("./__headless_engine"); ')
    assert spec.startswith('local __engine = require("../__headless_engine"); ')
    engine = (engine_dir / "__headless_engine.luau").read_text(encoding="utf-8")
    assert 'Part = "FormFactorPart"' in engine
    assert 'SpawnLocation = "Part"' in engine
    assert 'Workspace = "WorldRoot"' in engine
    assert 'error("unsupported headless Instance.new class:' in engine


def test_every_spec_is_found_and_has_a_template_root():
    specs = sorted(EXAMPLES.rglob("*.spec.luau"))
    assert len(specs) >= 13
    for spec in specs:
        assert any(p.parent in (EXAMPLES / "roblox-templates", EXAMPLES / "roblox")
                   or p == EXAMPLES / "roblox-test-place" for p in spec.parents), spec


def _fake_evidence(*cases: tuple[str, bool]) -> str:
    rows = []
    for index, (name, ok) in enumerate(cases, 1):
        rows.append(f"  {'PASS' if ok else 'FAIL'} {name}\n")
        rows.append(f"@@STAR_LUAU_CASE_V1\t{index}\t"
                    f"{'PASS' if ok else 'FAIL'}\t{name.encode('utf-8').hex()}\n")
    rows.append(f"@@STAR_LUAU_SUMMARY_V1\t{len(cases)}\t"
                f"{sum(not ok for _, ok in cases)}\n")
    return "".join(rows)


def test_driver_runs_every_case_and_rejects_an_empty_spec():
    driver = runner.driver_source("Thing.spec")
    assert 'require("./Thing.spec")' in driver
    assert 'error("spec defines no cases")' in driver
    assert 'error("too many spec cases")' in driver
    assert "pcall(suite[name])" in driver
    assert "@@STAR_LUAU_CASE_V1" in driver
    assert "@@STAR_LUAU_SUMMARY_V1" in driver
    assert "failed += 1" in driver


@pytest.mark.parametrize("stdout,exit_status", [
    ("", 0),
    ("  PASS fake\n", 0),
    ("@@STAR_LUAU_CASE_V1\t1\tPASS\t6f6b\n", 0),
    ("@@STAR_LUAU_SUMMARY_V1\t0\t0\n", 0),
    (_fake_evidence(("ok", True)) +
     "@@STAR_LUAU_CASE_V1\t1\tPASS\t6f6b\n", 0),
    (_fake_evidence(("same", True), ("same", True)), 0),
    (_fake_evidence(("ok", True)).replace("SUMMARY_V1\t1\t0",
                                         "SUMMARY_V1\t2\t0"), 0),
    (_fake_evidence(("ok", True)).replace("SUMMARY_V1\t1\t0",
                                         "SUMMARY_V1\t1\t1"), 0),
    (_fake_evidence(("ok", True)).replace("CASE_V1\t1\tPASS\t6f6b",
                                         "CASE_V1\t1\tPASS\tzz"), 0),
    (_fake_evidence(("ok", True)) +
     "@@STAR_LUAU_BOGUS\t1\n", 0),
    (_fake_evidence(("ok", True)), 1),
    (_fake_evidence(("broken", False)), 0),
    ("a" * (runner.MAX_SPEC_OUTPUT_BYTES + 1), 0),
    (_fake_evidence(("ok", True)) +
     "@@STAR_LUAU_SUMMARY_V1\t1\t0\n", 0),
], ids=[f"false-success-{index:02d}" for index in range(14)])
def test_false_success_evidence_is_rejected(stdout, exit_status):
    verdict = runner.parse_case_evidence(stdout, exit_status)
    assert verdict.reason
    assert verdict.verified == 0


def test_multi_case_evidence_must_be_complete_and_counted():
    raw = _fake_evidence(("alpha", True), ("βeta", True), ("gamma", True))
    result = runner.parse_case_evidence(raw, 0)
    assert (result.attempted, result.verified, result.failed, result.reason) == (
        3, 3, 0, None)
    assert "@@STAR_LUAU_" not in runner._visible_output(raw)
    assert "PASS alpha" in runner._visible_output(raw)
    mixed = runner.parse_case_evidence(_fake_evidence(("good", True), ("bad", False)), 1)
    assert (mixed.attempted, mixed.verified, mixed.failed) == (2, 1, 1)
    assert mixed.reason == "1 case(s) failed"


def test_run_counts_failures_and_timeouts(tmp_path, monkeypatch, capsys):
    root = _make_template(tmp_path)
    tests = root / "roblox-templates/demo/ServerScriptService/Tests"
    for name in ("A", "B", "C"):
        (tests / f"{name}.spec.luau").write_text("return {}\n", encoding="utf-8")
    seen: list[str] = []

    def fake_run(command, **kwargs):
        driver = pathlib.Path(command[1])
        seen.append(driver.name)
        assert driver.is_file() and kwargs["timeout"] == runner.SPEC_TIMEOUT_SECONDS
        if driver.name.startswith("A."):
            return subprocess.CompletedProcess(command, 0,
                                               stdout=_fake_evidence(("ok", True)))
        if driver.name.startswith("B."):
            return subprocess.CompletedProcess(command, 1,
                                               stdout=_fake_evidence(("nope", False)))
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.run("luau", root) == 1
    out = capsys.readouterr().out
    assert seen == ["A.spec.luau.runner.luau", "B.spec.luau.runner.luau",
                    "C.spec.luau.runner.luau"]
    assert "1/3 spec files passed" in out
    assert "2 attempted, 1 verified cases" in out
    assert "no result after" in out

    monkeypatch.setattr(runner.subprocess, "run",
                        lambda command, **kw: subprocess.CompletedProcess(command, 0, stdout=""))
    assert runner.run("luau", root) == 1
    assert "0/3 spec files passed" in capsys.readouterr().out


def test_run_json_report_and_missing_executable(tmp_path, monkeypatch, capsys):
    root = _make_template(tmp_path)
    tests = root / "roblox-templates/demo/ServerScriptService/Tests"
    (tests / "A.spec.luau").write_text("return {}\n", encoding="utf-8")
    (tests / "B.spec.luau").write_text("return {}\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        if pathlib.Path(command[1]).name.startswith("A."):
            return subprocess.CompletedProcess(command, 0,
                 stdout=_fake_evidence(("first", True), ("second", True)))
        raise FileNotFoundError("fake Luau missing")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.run("luau", root, json_output=True) == 1
    report = json.loads(capsys.readouterr().out)
    assert (report["attempted"], report["verified"], report["spec_files_passed"]) == (2, 2, 1)
    assert report["specs"][0]["status"] == "pass"
    assert report["specs"][1]["reason"] == "Luau interpreter could not start"
    assert report["scope"].endswith("not Roblox Studio")


def test_run_marks_staged_arena_as_simulated(monkeypatch, capsys):
    """Use the real stage-and-run path, even when Luau is absent locally."""
    inspected: list[str] = []

    def fake_run(command, **kwargs):
        driver = pathlib.Path(command[1])
        if driver.name == "ArenaFactory.spec.luau.runner.luau":
            engine = driver.parent.parent / "__headless_engine.luau"
            text = engine.read_text(encoding="utf-8")
            assert "function Node:IsA(name)" in text
            assert "local PARENT_CLASS = {" in text
            assert 'SpawnLocation = "Part"' in text
            inspected.append(driver.name)
        return subprocess.CompletedProcess(command, 0, stdout=_fake_evidence(("fixture", True)))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.run("luau", EXAMPLES) == 0
    output = capsys.readouterr().out
    assert inspected == ["ArenaFactory.spec.luau.runner.luau"]
    assert output.count("SIMULATED ROBLOX INSTANCE:") == 1
    assert "not Roblox Studio" in output
    assert output.count("RUN ") == len(list(EXAMPLES.rglob("*.spec.luau")))


def test_run_fails_when_there_are_no_specs(tmp_path, capsys):
    root = tmp_path / "examples"
    root.mkdir()
    assert runner.run("luau", root) == 1
    assert "no Luau specs found" in capsys.readouterr().err


LUAU = shutil.which("luau")


@pytest.mark.skipif(LUAU is None, reason="needs the Luau CLI; the Luau template specs workflow runs it")
def test_runner_reports_pass_fail_and_empty_specs_with_a_real_interpreter(tmp_path):
    root = _make_template(tmp_path)
    tests = root / "roblox-templates/demo/ServerScriptService/Tests"
    (tests / "Good.spec.luau").write_text(
        'return { ["adds"] = function() assert(1 + 1 == 2) end }\n', encoding="utf-8")
    assert runner.run(LUAU, root) == 0
    (tests / "Bad.spec.luau").write_text(
        'return { ["breaks"] = function() error("boom") end }\n', encoding="utf-8")
    assert runner.run(LUAU, root) == 1
    (tests / "Bad.spec.luau").unlink()
    (tests / "Empty.spec.luau").write_text("return {}\n", encoding="utf-8")
    assert runner.run(LUAU, root) == 1


@pytest.mark.skipif(LUAU is None, reason="needs the Luau CLI; the Luau template specs workflow runs it")
def test_all_repository_specs_pass_with_a_real_interpreter(capsys):
    assert runner.run(LUAU, EXAMPLES) == 0
    output = capsys.readouterr().out
    for case in (
        "headless IsA recognizes Part ancestors",
        "headless IsA recognizes SpawnLocation and Model ancestors",
        "headless IsA recognizes Workspace ancestors",
        "headless IsA rejects unsupported and malformed queries",
        "headless Instance.new rejects unsupported classes",
    ):
        assert f"PASS {case}" in output
    assert "SIMULATED ROBLOX INSTANCE:" in output
    count = len(list(EXAMPLES.rglob("*.spec.luau")))
    assert f"{count}/{count} spec files passed" in output


def test_workflow_pins_luau_by_version_and_checksum_before_using_it():
    text = WORKFLOW.read_text(encoding="utf-8")
    version = re.search(r"^\s*LUAU_VERSION: '(\d+\.\d+)'$", text, re.M)
    digest = re.search(r"^\s*LUAU_ZIP_SHA256: '([0-9a-f]{64})'$", text, re.M)
    assert version and digest, "version and SHA-256 must both be pinned literally"
    assert "https://github.com/luau-lang/luau/releases/download/${LUAU_VERSION}/luau-ubuntu.zip" in text
    assert "/releases/latest" not in text
    assert text.index("sha256sum --check") < text.index("unzip "), "verify before unpacking"
    assert text.index("sha256sum --check") < text.index('>> "$GITHUB_PATH"'), "verify before use"
    assert "permissions:\n  contents: read" in text
    assert "persist-credentials: false" in text
    assert "secrets." not in text
