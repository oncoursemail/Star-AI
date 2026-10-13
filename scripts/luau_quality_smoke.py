#!/usr/bin/env python3
"""Pinned Luau CLI real invocation: actual STAR example and two seeded defects."""
from __future__ import annotations

from pathlib import Path
from statistics import median
from time import perf_counter

from star.luau_lint import lint


SOURCE = Path("examples/roblox-templates/simulator/ReplicatedStorage/Shared/CostCurve.luau")


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    marker = "local CostCurve = {}"
    if original.count(marker) != 1:
        raise AssertionError("STAR source changed; update the reviewed smoke fixture")
    cases = [
        ("unaltered", original),
        ("syntax", original.replace(marker, "local CostCurve = {", 1)),
        ("type", original.replace(marker, 'local forced: number = "bad"\n' + marker, 1)),
    ]
    samples = []
    for name, code in cases:
        started = perf_counter()
        old = lint(code, external=False)
        new = lint(code, external=True)
        elapsed = round(1000 * (perf_counter() - started), 2)
        samples.append(elapsed)
        additional = [f for f in new if f not in old]
        categories = [f.rule_id for f in additional]
        print(f"{name}: static={len(old)} external={len(additional)} "
              f"rules={categories} elapsed_ms={elapsed}", flush=True)
        if name == "syntax" and "luau-analyze-syntaxerror" not in categories:
            raise AssertionError("Pinned Luau analyzer did not catch seeded syntax error")
        if name == "type" and "luau-analyze-typeerror" not in categories:
            raise AssertionError("Pinned Luau analyzer did not catch seeded type error")
    print(f"Real pinned analyzer invoked on 3 STAR-derived cases; median_ms={median(samples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
