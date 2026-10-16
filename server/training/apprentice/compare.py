"""Compare arms on the measuring slice: pass rate (Wilson 95 %), paired sign test, speed.

    python compare.py --scores scored-*.jsonl --answers answers-*.jsonl [--pair apprentice base]

Scores come from score_answers.py (night school's checks), answers from gen_answers.py (llama-server timings).
Only tasks every arm answered are compared, so the numbers are paired.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from star.eval_stats import sign_test, wilson_interval  # noqa: E402


def rows(paths):
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", nargs="+", required=True)
    ap.add_argument("--answers", nargs="+", required=True)
    ap.add_argument("--pair", nargs=2, action="append", default=[], metavar=("CANDIDATE", "BASELINE"))
    args = ap.parse_args()
    passed: dict[str, dict[str, bool]] = {}
    for r in rows(args.scores):
        if not r.get("infra"):
            passed.setdefault(r["arm"], {})[r["id"]] = bool(r["passed"])
    speed: dict[str, list[dict]] = {}
    for r in rows(args.answers):
        speed.setdefault(r["arm"], []).append(r)
    common = set.intersection(*(set(v) for v in passed.values()))
    out = {"tasks": len(common), "arms": {}, "pairs": []}
    for arm, by_id in sorted(passed.items()):
        k = sum(by_id[t] for t in common)
        lo, hi = wilson_interval(k, len(common))
        ans = [a for a in speed.get(arm, []) if a["id"] in common and a.get("gen_tps")]
        out["arms"][arm] = {"passed": k, "of": len(common), "rate": round(k / max(len(common), 1), 3),
                            "ci95": [round(lo, 3), round(hi, 3)],
                            "all_tasks_passed": f"{sum(by_id.values())}/{len(by_id)}",
                            "gen_tps_median": round(statistics.median(a["gen_tps"] for a in ans), 1) if ans else None,
                            "seconds_median": round(statistics.median(a["seconds"] for a in ans), 1) if ans else None,
                            "gen_tokens_median": statistics.median(a["gen_tokens"] or 0 for a in ans) if ans else None}
    for cand, base in args.pair:
        both = set(passed[cand]) & set(passed[base])
        wins = sum(passed[cand][t] and not passed[base][t] for t in both)
        losses = sum(passed[base][t] and not passed[cand][t] for t in both)
        test = sign_test(wins, losses)
        out["pairs"].append({"candidate": cand, "baseline": base, "tasks": len(both),
                             "candidate_passed": sum(passed[cand][t] for t in both),
                             "baseline_passed": sum(passed[base][t] for t in both), "wins": wins, "losses": losses,
                             "p_better": round(test["p_better"], 4), "p_two_sided": round(test["p_two_sided"], 4)})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
