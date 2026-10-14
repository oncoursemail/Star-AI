#!/usr/bin/env python3
"""Pinned Luau CLI real invocation: actual STAR example and two seeded defects."""
from __future__ import annotations

from pathlib import Path
from statistics import median
from time import perf_counter

from star.luau_lint import lint
from star.luau_analyze import analyze
from star.luau_record_type_lessons import load_cases


SOURCE = Path("examples/roblox-templates/simulator/ReplicatedStorage/Shared/CostCurve.luau")


def verify_pure_record_candidates() -> int:
    """Typecheck actual pure-language lesson witnesses with the pinned analyzer.

    Multi-file ModuleScript cases cannot be checked by this single-file CLI;
    they require a project-aware Roblox Studio type checker.
    """
    pure = [case for case in load_cases()
            if case.verification == "pure-luau-illustrative"]
    if len(pure) != 8:
        raise AssertionError("Expected eight pure-Luau type witnesses")
    for case in pure:
        broken = analyze(case.incorrect)
        repaired = analyze(case.corrected)
        if not any(item.rule_id == "luau-analyze-typeerror" for item in broken):
            raise AssertionError(f"{case.id}: analyzer did not detect broken typing")
        if any(item.rule_id in ("luau-analyze-typeerror", "luau-analyze-syntaxerror")
               for item in repaired):
            raise AssertionError(f"{case.id}: analyzer rejected corrected Luau")
    return len(pure)


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
    verified = verify_pure_record_candidates()
    print(f"Real pinned analyzer: {verified}/{verified} pure candidate witness pairs"
          " rejected broken types and accepted corrected snippets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
