"""Benchmark: how long importing STAR's entry modules takes, in fresh interpreters.

Each sample is a new `python -c "import <module>"` process (so nothing is cached in memory),
timed from inside the child with perf_counter around the import itself. The interpreter start
is excluded. Reports min and median over --runs samples; use the median for before/after.

    python benchmarks/bench_import.py [--runs 9] [modules ...]
    python benchmarks/bench_import.py --heavy star.react_shell   # which heavy libraries got loaded
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODULES = ("star.react_shell", "star.desktop_core", "star.agent", "star.cli")
HEAVY = ("jsonschema", "httpx", "PIL.Image", "anyio", "openai", "mcp", "numpy", "pydantic")

CHILD = r"""
import sys, time, json
t = time.perf_counter()
import {module}
elapsed = (time.perf_counter() - t) * 1000
print(json.dumps({{"ms": elapsed, "heavy": [m for m in {heavy!r} if m in sys.modules]}}))
"""


def sample(module: str, env: dict) -> dict:
    out = subprocess.run([sys.executable, "-c", CHILD.format(module=module, heavy=HEAVY)], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("modules", nargs="*", default=list(DEFAULT_MODULES))
    parser.add_argument("--runs", type=int, default=9)
    parser.add_argument("--heavy", action="store_true", help="also list the heavy libraries each import loaded")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    env = {**os.environ, "APPDATA": tempfile.mkdtemp(prefix="star-bench-"), "PYTHONDONTWRITEBYTECODE": ""}
    env.pop("PYTHONDONTWRITEBYTECODE")
    results = {}
    for module in args.modules:
        sample(module, env)  # writes .pyc files and warms the OS file cache
        runs = [sample(module, env) for _ in range(max(1, args.runs))]
        times = [r["ms"] for r in runs]
        results[module] = {"median_ms": round(statistics.median(times), 1), "min_ms": round(min(times), 1),
                           **({"heavy_loaded": runs[-1]["heavy"]} if args.heavy else {})}
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for module, r in results.items():
            extra = f"  heavy: {', '.join(r['heavy_loaded']) or '-'}" if args.heavy else ""
            print(f"{module:24s} median {r['median_ms']:8.1f} ms   min {r['min_ms']:8.1f} ms{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
