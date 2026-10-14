"""Compare existing and shared retrieval on independently authored fixed cases.

Both arms read the SAME Graphify export. This measures source/symbol retrieval,
serialized context and local latency, not answer quality or model intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from star.graphify_bridge import GraphifyGraph
from star.shared_brain.store import SharedBrain, serialize


def symbol(value):
    return str(value).strip().lstrip(".").removesuffix("()").lower()


def measure(workspace: Path, fixtures: Path, *, split="development", repeats=3) -> dict:
    raw = fixtures.read_bytes()
    suite = json.loads(raw)
    cases = [c for c in suite["cases"] if c["split"] == split]
    if not cases or not 1 <= repeats <= 10:
        raise ValueError("Select a nonempty fixture split and 1..10 repeats")
    root = workspace.resolve(strict=True)
    for case in cases:
        source = root / case["expected_source_file"]
        if (not source.resolve().is_relative_to(root) or source.is_symlink()
                or hashlib.sha256(source.read_bytes()).hexdigest() != case["grounding_sha256"]):
            raise ValueError("Fixture source changed: re-ground independently before comparison")
    baseline, candidate = GraphifyGraph(root), SharedBrain(root)
    candidate.sync()
    # Warm lazy graph loading and SQLite reads outside measured samples.
    baseline.query(cases[0]["question"], limit=8)
    candidate.query(cases[0]["question"], limit=8, budget_chars=3000)
    rows = []
    for case in cases:
        runs = {"baseline": lambda: baseline.query(case["question"], limit=8),
                "shared": lambda: candidate.query(case["question"], limit=8, budget_chars=3000)}
        samples = {name: {"elapsed": [], "chars": [], "passes": []} for name in runs}
        for iteration in range(repeats):
            order = ("baseline", "shared") if iteration % 2 == 0 else ("shared", "baseline")
            for name in order:
                start = time.perf_counter()
                result = runs[name]()
                samples[name]["elapsed"].append((time.perf_counter()-start)*1000)
                samples[name]["chars"].append(len(serialize(result)))
                found = any(
                    match["node"].get("source_file") == case["expected_source_file"]
                    and symbol(match["node"].get("label")) == symbol(case["expected_graph_label"])
                    for match in result["matches"])
                samples[name]["passes"].append(found)
        arms = {name: {"correct": all(s["passes"]), "latency_ms": s["elapsed"], "context_chars": s["chars"]}
                for name, s in samples.items()}
        rows.append({"id": case["id"], **arms})
    summary = {}
    for name in ("baseline", "shared"):
        elapsed = sorted(value for row in rows for value in row[name]["latency_ms"])
        contexts = [value for row in rows for value in row[name]["context_chars"]]
        summary[name] = {"correct": sum(row[name]["correct"] for row in rows), "cases": len(rows),
                         "median_latency_ms": round(statistics.median(elapsed), 3),
                         "p95_latency_ms": round(elapsed[max(0, math.ceil(len(elapsed)*.95)-1)], 3),
                         "median_context_chars": statistics.median(contexts),
                         "max_context_chars": max(contexts),
                         "median_estimated_tokens": math.ceil(statistics.median(contexts)/4)}
    candidate.close()
    return {"suite_sha256": hashlib.sha256(raw).hexdigest(), "split": split, "repeats": repeats,
            "graph_sha256": hashlib.sha256((root/"graphify-out/graph.json").read_bytes()).hexdigest(),
            "summary": summary, "tasks": rows,
            "method": "Same graph and top8 count limit; shared envelope capped at 3000 Unicode characters, baseline has no character cap. Both arms prewarmed; execution order alternates across repeats. Shared includes freshness checks and query audit persistence; baseline has neither. Token estimate is characters/4, not a tokenizer measurement.",
            "limitations": "Local source/symbol retrieval only. No model, server, generated Python execution, end-to-end answer accuracy or weights training measured."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/shared_brain_retrieval.json"))
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = measure(args.workspace, args.fixtures, split=args.split, repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(serialize(result["summary"]))


if __name__ == "__main__":
    main()
