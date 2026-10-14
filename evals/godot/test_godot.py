"""Validate the benchmark fixtures, scorer, and good/bad separation offline."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("godot_static_score", HERE / "score.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_twelve_unique_tasks_and_engine_metadata():
    data = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
    tasks = data["tasks"]
    assert data["engine"] == "Godot 4"
    assert len(tasks) == len({task["id"] for task in tasks}) == 12
    assert all(task["prompt"] and task["reference"].startswith("extends ") and task["bad"] for task in tasks)
    assert all(task["required_patterns"] for task in tasks)


def test_reference_passes_and_bad_answer_fails_every_task():
    for task in module.load_tasks():
        assert module.score(task, task["reference"]) == 1.0, task["id"]
        assert module.score(task, task["bad"]) < 1.0, task["id"]
        assert module.score(task, "") == 0.0, task["id"]
        assert module.score(task, None) == 0.0, task["id"]


def test_partial_credit_is_bounded():
    task = module.load_tasks()[0]
    assert 0 < module.score(task, "PackedScene") < 1
