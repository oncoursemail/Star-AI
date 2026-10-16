"""Apprentice dataset builder: no golden/holdout task, no measuring task in training, footer cut, dedupe."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("apprentice_build", ROOT / "server/training/apprentice/build_dataset.py")
bd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bd)


def _task(tid, prompt):
    return {"id": tid, "prompt": prompt, "category": "c", "run_mode": "automated"}


def _example(tid, prompt, answer, ts="2026-10-15T00:00:00Z"):
    return {"task": tid, "prompt": prompt, "answer": answer, "category": "c", "kind": "first", "lessons": [],
            "verified": True, "ts": ts}


@pytest.fixture()
def world(tmp_path):
    pool, golden, ex = tmp_path / "pool", tmp_path / "evals", tmp_path / "s1"
    for d in (pool, golden, ex):
        d.mkdir()
    ids = [f"T-{i:03d}" for i in range(60)]
    (pool / "tasks.json").write_text(json.dumps([_task(t, "write code for " + t) for t in ids]), encoding="utf-8")
    (golden / "golden-tasks-v1.json").write_text(json.dumps([_task("G-1", "Golden prompt here")]), encoding="utf-8")
    (golden / "holdout-v1.json").write_text("not json: must never be opened", encoding="utf-8")
    rows = [_example(t, "write code for " + t, f"```lua\nprint('{t}')\n```" + "\n\n---\n**Sources retrieved by STAR**\n1. x")
            for t in ids]
    rows.append(_example("G-1", "golden   PROMPT here", "```lua\nprint(1)\n```"))            # golden by prompt hash
    rows.append(_example("T-000", "write code for T-000", "```lua\nprint('new')\n```", ts="2026-10-16T00:00:00Z"))
    rows.append(_example("T-900", "another prompt", "```lua\nprint('T-001')\n```"))          # duplicate answer of T-001
    (ex / "examples.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return ex / "examples.jsonl", pool, golden


def test_build_excludes_golden_and_measure_and_cuts_footer(world):
    examples, pool, golden = world
    out = bd.build([examples], pool, golden)
    trained = {r["id"] for r in out["train"] + out["val"]}
    assert "G-1" not in trained
    assert not trained & {t["id"] for t in out["measure"]}
    assert out["measure"] and all(bd.is_measure(t["id"]) for t in out["measure"])
    for row in out["train"] + out["val"]:
        assert "Sources retrieved" not in row["messages"][-1]["content"]
        assert row["messages"][0]["content"] == bd.SYSTEM
    assert out["counts"]["golden_or_holdout"] == 1
    assert out["counts"]["dup_task"] == 1 and out["counts"]["dup_answer"] == 1
    if "T-000" in trained:                                                                   # newest answer kept
        row = next(r for r in out["train"] + out["val"] if r["id"] == "T-000")
        assert "new" in row["messages"][-1]["content"]


def test_holdout_path_refused(world, tmp_path):
    examples, pool, golden = world
    with pytest.raises(SystemExit):
        bd.build([golden / "holdout-v1.json"], pool, golden)
