"""Runtime-graded Roblox practice: real schema/loader, guarded pool, optional local Luau."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from star import eval_checks
from star.eval_runner import load_suite, validate_tasks
from star.evals import load_catalog

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evals" / "roblox" / "practice-tasks-run-v1.json"
DEFINITIONS = ROOT / "tests" / "fixtures" / "practice_run_definitions.json"
SPEC = ROOT / "examples" / "roblox-templates" / "practice-run" / "ServerScriptService" / "Tests" / "PracticeRun.spec.luau"
LUAU = shutil.which("luau")
sys.path.insert(0, str(ROOT / "server" / "night_school"))
from nightschool.pool import load_pool, prompt_hash  # noqa: E402


def test_thirty_valid_tasks_with_six_executable_assertions():
    suite = load_suite(SUITE)
    rows = json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    assert len(suite.tasks) == len(suite.runnable()) == len(rows) == 30
    assert [t["id"] for t in suite.tasks] == [f"practice-run-{n:03d}" for n in range(1, 31)]
    assert {t["category"] for t in suite.tasks} == {
        "roblox-practice-run-data-saving", "roblox-practice-run-round-state",
        "roblox-practice-run-inventory-economy",
    }
    spec = SPEC.read_text(encoding="utf-8")
    for i, (task, row) in enumerate(zip(suite.tasks, rows), 1):
        assert task["run_mode"] == "automated" and task["split"] == "development"
        assert task["teaches"] and task["expected_sources"] and task["prompt"]
        assert task["grader"]["type"] == "unit_test"
        assert task["auto"]["compile"] is False
        assert "require" not in task["auto"] and "forbid" not in task["auto"]
        assert task["auto"]["unit_test"]["checks"] == 6
        assert len(row["cases"]) == 6 and row["reference"] != row["wrong"]
        assert row["reference"].startswith("--!strict") and row["wrong"].startswith("--!strict")
        assert len(re.findall(r"^check\(", suite.test_body(task), re.M)) == 6
        assert f'tests["{task["id"]}"] = function()' in spec
        assert f"local function __good_{i:03d}" in spec
        assert f"local function __bad_{i:03d}" in spec


def test_real_night_school_pool_guard_and_validation_split(tmp_path):
    suite = load_suite(SUITE)
    folder = tmp_path / "practice"
    (folder / "tests").mkdir(parents=True)
    (folder / SUITE.name).write_text(SUITE.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "prelude.luau").write_text(suite.prelude, encoding="utf-8")
    for task in suite.tasks:
        (folder / task["auto"]["unit_test"]["file"]).write_text(suite.test_body(task), encoding="utf-8")
    pool = load_pool(folder)
    assert len(pool.tasks) == 30 and not pool.dropped
    assert all(t["_test_body"] for t in pool.tasks)
    (folder / "forbidden-prompts.json").write_text(json.dumps({
        "prompt_sha256": [prompt_hash(suite.tasks[0]["prompt"])], "ids": []
    }), encoding="utf-8")
    guarded = load_pool(folder)
    assert len(guarded.tasks) == 29
    assert guarded.dropped.get("copy of an evaluation task") == 1
    assert suite.tasks[0]["id"] not in {t["id"] for t in guarded.tasks}


def test_real_catalog_rejects_duplicate_ids(tmp_path):
    task = load_suite(SUITE).tasks[0]
    path = tmp_path / "dupe.json"
    path.write_text(json.dumps([task, task]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique ID"):
        load_catalog(path)
    assert not validate_tasks(load_suite(SUITE).tasks, SUITE.parent)


@pytest.mark.skipif(LUAU is None, reason="Luau CLI unavailable in pytest; pinned Luau template specs workflow runs the 30 cases")
def test_all_reference_and_wrong_witnesses_execute_in_real_luau_vm(tmp_path):
    suite = load_suite(SUITE)
    rows = json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    for task, witness in zip(suite.tasks, rows):
        body = suite.test_body(task)
        for label, code, expected in (
            ("reference", witness["reference"], True),
            ("wrong", witness["wrong"], False),
        ):
            path = tmp_path / "trial.luau"
            path.write_text(eval_checks.build_test_script(suite.prelude, code, body), encoding="utf-8")
            result = subprocess.run(
                [LUAU, str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=10, check=False,
            )
            outcome = eval_checks.parse_test_output(result.stdout)
            scored = eval_checks.unit_checks(outcome, SimpleNamespace(timed_out=False), 6)[0]
            assert scored.ok is expected, (
                task["id"], label, result.returncode, scored.detail, result.stdout[-300:],
            )
