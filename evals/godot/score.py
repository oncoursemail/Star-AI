"""Deterministic static checks for Godot 4 GDScript examples (not engine execution)."""
from __future__ import annotations
import json
from pathlib import Path
import re

TASKS = Path(__file__).with_name("tasks.json")


def load_tasks():
    return json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]


def score(task: dict, answer: str) -> float:
    """Fraction of independently specified required textual patterns present."""
    if not isinstance(answer, str):
        return 0.0
    patterns = task["required_patterns"]
    if not patterns:
        raise ValueError("A task needs at least one criterion")
    return sum(bool(re.search(pattern, answer)) for pattern in patterns) / len(patterns)
