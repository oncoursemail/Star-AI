"""Offline Unity fixtures scored with STAR's existing pattern_checks, not Luau compilation."""
import json
from pathlib import Path
import re

from star import eval_checks, skill_packs

FILE = Path(__file__).resolve().parents[1] / "evals" / "unity" / "golden-tasks-v1.json"
C_SHARP_NONCODE = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:""|[^"])*"|"(?:(?:\\.)|[^"\\])*"|\x27(?:(?:\\.)|[^\x27\\])*\x27')


def strip_csharp(source: str) -> str:
    """Remove comments, character and string literals while preserving newlines."""
    return C_SHARP_NONCODE.sub(
        lambda match: "".join("\n" if ch == "\n" else " " for ch in match.group()), source
    )


def checks(task: dict, answer: str):
    code = strip_csharp(answer)
    return eval_checks.pattern_checks(task["auto"], [code], code)


def test_unity_golden_tasks_schema_and_reference_pairs():
    tasks = json.loads(FILE.read_text(encoding="utf-8"))
    assert len(tasks) == 20
    assert len({task["id"] for task in tasks}) == 20
    names = {pack.name for pack in skill_packs.available()}
    for task in tasks:
        assert task["category"] in names and task["category"].startswith("unity-")
        assert task["run_mode"] == "automated"
        assert task["auto"]["require"] and task["auto"]["forbid"]
        assert all(result.ok for result in checks(task, task["reference_answer"])), task["id"]
        assert any(not result.ok for result in checks(task, task["bad_answer"])), task["id"]


def test_comments_and_strings_cannot_spoof_required_api():
    task = json.loads(FILE.read_text(encoding="utf-8"))[0]
    fake = '// Awake() OnDisable()\nstring message = "Awake() OnDisable()";'
    assert any(not result.ok for result in checks(task, fake))


def test_block_comments_and_verbatim_strings_are_removed():
    stripped = strip_csharp('/* Awake() */ var x = @"OnDisable()"; Awake();')
    assert "OnDisable" not in stripped
    assert stripped.count("Awake") == 1
