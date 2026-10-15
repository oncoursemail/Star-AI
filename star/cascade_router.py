"""Offline cascade and routing simulator over STAR evaluation result files.

Idea 1 of docs/research/multi-model-20261014.md. Before any runtime routing code changes, this answers from real
result files: if STAR answered with the quick model first and escalated to the strong model only when the
runtime Luau check did not pass ("cascade"), or sent whole task categories to one model ("table"), how many golden
tasks would still pass, and how much time would it save?

Inputs are ordinary `python -m star.evals run` result files: k runs of the strong model (e.g. star-fast) and k runs
of the quick model (e.g. star-quick, run with `--pin-model` so that Roblox/code tasks are not re-routed to the
strong model), same suite and grader. Sample j of one arm is paired with sample j of the other (by start time).

Policies per task category:
  strong   the strong model answers (today's behaviour, the baseline)
  quick    the quick model answers
  cascade  the quick model answers; its answer is kept only if the runtime Luau check (the `luau_check_finished`
           event the app itself emits, state "passed" by default) accepted it; otherwise the strong model answers.
           Time = quick time + strong time on escalation (conservative: no prompt cache is shared across models).

Quality is never traded silently: every policy is compared with `strong` by star/eval_stats.paired_decision, and a
policy is called SAFE only when, on these files, it lost no sample pair that the strong model won and the paired
verdict is not REJECT. A table fitted on some runs is in-sample; check it with `--table` on fresh runs before use.

Nothing here runs a model or changes a setting. The output table is a file; no app code reads it yet.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import statistics

from . import eval_stats
from .eval_gate import _errors, load_result

POLICIES = ("strong", "quick", "cascade")
DEFAULT_ACCEPT = ("passed",)
_SCORED: dict[object, bool] = {"pass": True, "fail": False}
_ROUTE_EVENTS = ("route_selected", "route_busy_quick", "route_fallback")
_BLIND = re.compile(r"holdout", re.I)      # the blind exam: never used to fit anything (night school pool rule)


@dataclass(frozen=True)
class Pair:
    """Sample j of one task: the strong model's and the quick model's outcome (None = errored, not scored)."""
    strong: bool | None
    quick: bool | None
    strong_s: float
    quick_s: float
    accepted: bool          # the runtime Luau check accepted the quick answer


def category_of(task_id: str, categories: dict | None = None) -> str:
    """The suite's own category when known, else the id up to its first numeric part (LUA-01 -> LUA)."""
    if categories and categories.get(task_id):
        return str(categories[task_id])
    head = []
    for part in re.split(r"[-_]", task_id):
        if part[:1].isdigit():
            break
        head.append(part)
    return "-".join(head) or task_id


def answered_by(row: dict) -> str | None:
    """The model the app says answered this task (last route event), or None when the run did not record it."""
    model = None
    for event in row.get("events") or []:
        if isinstance(event, dict) and event.get("event") in _ROUTE_EVENTS and isinstance(event.get("model"), str):
            model = event["model"]
    return model


def runtime_accept(row: dict, accept=DEFAULT_ACCEPT) -> bool:
    """True when the app's own Luau check finished in an accepted state. No check event (no Luau code, check not
    run) is never an acceptance: the cascade escalates."""
    state = None
    for event in row.get("events") or []:
        if isinstance(event, dict) and event.get("event") == "luau_check_finished":
            state = event.get("state")
    return state in set(accept)


def _ordered(runs: list[dict]) -> list[dict]:
    return sorted(runs, key=lambda r: str(r["run"].get("started_at") or ""))


def build_pairs(strong_runs: list[dict], quick_runs: list[dict], *, accept=DEFAULT_ACCEPT,
                allow_mixed: bool = False) -> tuple[dict[str, list[Pair]], list[str]]:
    """task id -> paired samples, and notes. Raises ValueError on input that cannot be compared honestly."""
    if not strong_runs or not quick_runs:
        raise ValueError("need at least one result file per arm")
    problems = []
    for arm, runs in (("strong", strong_runs), ("quick", quick_runs)):
        for i, run in enumerate(runs):
            problems.extend(_errors(run, f"{arm} run {i + 1}")[0])
    if problems:
        raise ValueError("; ".join(problems))
    first = strong_runs[0]
    for arm, runs in (("strong", strong_runs), ("quick", quick_runs)):
        for i, run in enumerate(runs):
            for key in ("sha256", "identity_sha256"):
                if run["suite"].get(key) != first["suite"].get(key):
                    raise ValueError(f"{arm} run {i + 1}: suite {key} differs: not a like-for-like comparison")
            for key in ("grader_sha256", "mode"):
                if run["run"].get(key) != first["run"].get(key):
                    raise ValueError(f"{arm} run {i + 1}: run {key} differs: not a like-for-like comparison")
    strong_runs, quick_runs = _ordered(strong_runs), _ordered(quick_runs)
    notes = []
    k = min(len(strong_runs), len(quick_runs))
    if len(strong_runs) != len(quick_runs):
        notes.append(f"{len(strong_runs)} strong vs {len(quick_runs)} quick runs: the first {k} of each are paired")
    strong_models = {m for run in strong_runs for row in run["tasks"].values() if (m := answered_by(row))}
    quick_models = {m for run in quick_runs for row in run["tasks"].values() if (m := answered_by(row))}
    if strong_models & quick_models:
        message = (f"both arms were answered by {', '.join(sorted(strong_models & quick_models))}: the quick arm was "
                   "probably re-routed to the strong model (run it with `python -m star.evals run --pin-model`)")
        if not allow_mixed:
            raise ValueError(message)
        notes.append("allowed: " + message)
    pairs: dict[str, list[Pair]] = {}
    ids = sorted({tid for run in strong_runs + quick_runs for tid in run["tasks"]})
    for tid in ids:
        samples = []
        for j in range(k):
            s_row = strong_runs[j]["tasks"].get(tid) or {}
            q_row = quick_runs[j]["tasks"].get(tid) or {}
            strong, quick = _SCORED.get(s_row.get("status")), _SCORED.get(q_row.get("status"))
            if strong is None and quick is None:
                continue
            samples.append(Pair(strong, quick, float(s_row.get("seconds") or 0.0), float(q_row.get("seconds") or 0.0),
                                runtime_accept(q_row, accept)))
        if samples:
            pairs[tid] = samples
    if not pairs:
        raise ValueError("no task was scored in either arm")
    return pairs, notes


def outcome(pair: Pair, policy: str) -> tuple[bool | None, float]:
    """(pass, seconds) of one sample under one policy."""
    if policy == "strong":
        return pair.strong, pair.strong_s
    if policy == "quick":
        return pair.quick, pair.quick_s
    if policy == "cascade":
        if pair.accepted:
            return pair.quick, pair.quick_s
        return pair.strong, pair.quick_s + pair.strong_s
    raise ValueError(f"unknown policy {policy!r}")


def evaluate(pairs: dict[str, list[Pair]], routes: dict[str, str] | str, *, categories: dict | None = None,
             alpha: float = eval_stats.DEFAULT_ALPHA) -> dict:
    """Pass counts, time and the paired verdict of a policy (one name for every task, or category -> name)
    against `strong`."""
    base, cand, base_s, cand_s = {}, {}, [], []
    escalated = quick_used = 0
    for tid, samples in pairs.items():
        policy = routes if isinstance(routes, str) else routes.get(category_of(tid, categories), "strong")
        base[tid], cand[tid] = [], []
        for pair in samples:
            b, bs = outcome(pair, "strong")
            c, cs = outcome(pair, policy)
            base[tid].append(b)
            cand[tid].append(c)
            if b is not None and c is not None:     # time is compared on samples both arms scored
                base_s.append(bs)
                cand_s.append(cs)
            if policy == "cascade":
                escalated += 0 if pair.accepted else 1
                quick_used += 1 if pair.accepted else 0
            elif policy == "quick":
                quick_used += 1
    report = eval_stats.paired_decision(base, cand, alpha=alpha)
    total_base, total_cand = sum(base_s), sum(cand_s)
    safe = report.losses == 0 and not report.regressions and report.decision != eval_stats.REJECT
    return {
        "routes": routes, "decision": report.decision, "safe": safe,
        "strong_pass": report.baseline_pass, "policy_pass": report.candidate_pass, "samples": report.samples,
        "tasks": report.n_tasks, "wins": report.wins, "losses": report.losses,
        "p_worse": round(report.p_worse, 4), "regressions": list(report.regressions),
        "incomplete": list(report.incomplete),
        "strong_seconds": round(total_base, 1), "policy_seconds": round(total_cand, 1),
        "median_strong_s": round(statistics.median(base_s), 1) if base_s else None,
        "median_policy_s": round(statistics.median(cand_s), 1) if cand_s else None,
        "time_saved_share": round(1 - total_cand / total_base, 3) if total_base else None,
        "quick_answers": quick_used, "escalations": escalated,
        "mde_tasks": report.mde.get("effect_tasks") if report.mde else None,
    }


def fit_table(pairs: dict[str, list[Pair]], *, categories: dict | None = None, min_tasks: int = 3,
              accept=DEFAULT_ACCEPT) -> dict:
    """Per category, the fastest policy that lost no sample pair to `strong` on these runs (strict); `strong` when
    the category has fewer than `min_tasks` tasks or nothing else is loss-free. In-sample: verify on fresh runs."""
    by_cat: dict[str, dict[str, list[Pair]]] = {}
    for tid, samples in pairs.items():
        by_cat.setdefault(category_of(tid, categories), {})[tid] = samples
    routes, evidence = {}, {}
    for cat, subset in sorted(by_cat.items()):
        choice = "strong"
        rows = {p: evaluate(subset, p) for p in POLICIES}
        if len(subset) >= min_tasks:
            ok = [p for p in ("quick", "cascade") if rows[p]["losses"] == 0 and not rows[p]["incomplete"]
                  and rows[p]["policy_seconds"] < rows["strong"]["policy_seconds"]]
            if ok:
                choice = min(ok, key=lambda p: rows[p]["policy_seconds"])
        routes[cat] = choice
        evidence[cat] = {"tasks": len(subset), "choice": choice,
                         **{p: {"pass": rows[p]["policy_pass"], "losses": rows[p]["losses"],
                                "seconds": rows[p]["policy_seconds"]} for p in POLICIES}}
    return {"schema": 1, "kind": "star-cascade-table", "accept": list(accept), "min_tasks": min_tasks,
            "routes": routes, "evidence": evidence,
            "note": "fitted in-sample on the given runs; check it with --table on fresh paired runs before any use"}


def suite_categories(path: Path) -> dict:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(r["id"]): str(r.get("category") or "") for r in rows if isinstance(r, dict) and r.get("id")}


def _line(name: str, row: dict) -> str:
    saved = row["time_saved_share"]
    return (f"{name:<22} pass {row['policy_pass']:>3}/{row['samples']:<3} (strong {row['strong_pass']}) "
            f"losses {row['losses']:>2} wins {row['wins']:>2}  time {row['policy_seconds']:>8.0f}s vs "
            f"{row['strong_seconds']:.0f}s ({'n/a' if saved is None else f'{saved:+.0%} saved'})  "
            f"quick kept {row['quick_answers']}, escalated {row['escalations']}  "
            f"{row['decision']}{'  SAFE' if row['safe'] else '  NOT SAFE'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.cascade_router",
                                     description="Simulate quick-first cascades and model routing from eval results.")
    parser.add_argument("--strong", required=True, type=Path, nargs="+", help="result files of the strong model")
    parser.add_argument("--quick", required=True, type=Path, nargs="+", help="result files of the quick model")
    parser.add_argument("--suite", type=Path, help="suite file, for its task categories (default: id prefix)")
    parser.add_argument("--accept", default=",".join(DEFAULT_ACCEPT),
                        help="runtime Luau check states that keep a quick answer (passed, repaired)")
    parser.add_argument("--min-tasks", type=int, default=3, help="smallest category the fitted table may route")
    parser.add_argument("--table", type=Path, help="evaluate this previously fitted table (out-of-sample check)")
    parser.add_argument("--write-table", type=Path, help="write the table fitted on these runs")
    parser.add_argument("--allow-mixed", action="store_true",
                        help="accept arms answered by the same model (smoke tests only)")
    parser.add_argument("--alpha", type=float, default=eval_stats.DEFAULT_ALPHA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    accept = tuple(s.strip() for s in args.accept.split(",") if s.strip())
    try:
        strong = [load_result(p) for p in args.strong]
        quick = [load_result(p) for p in args.quick]
        categories = suite_categories(args.suite) if args.suite else None
        pairs, notes = build_pairs(strong, quick, accept=accept, allow_mixed=args.allow_mixed)
        table_in = json.loads(args.table.read_text(encoding="utf-8")) if args.table else None
        if table_in is not None and table_in.get("kind") != "star-cascade-table":
            raise ValueError(f"{args.table} is not a cascade table")
        blind = any(_BLIND.search(str(r["suite"].get("file") or "")) for r in strong + quick)
        if blind and (table_in is None or args.write_table):
            raise ValueError("holdout results may only check a table fitted on other runs (--table), never fit one")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"unusable input: {exc}")
        return 2
    rows = {p: evaluate(pairs, p, categories=categories, alpha=args.alpha) for p in POLICIES}
    fitted = None if blind else fit_table(pairs, categories=categories, min_tasks=args.min_tasks, accept=accept)
    if fitted is not None:
        rows["table (in-sample)"] = evaluate(pairs, fitted["routes"], categories=categories, alpha=args.alpha)
    if table_in is not None:
        rows["table (given)"] = evaluate(pairs, table_in.get("routes") or {}, categories=categories, alpha=args.alpha)
    if args.write_table:
        args.write_table.write_text(json.dumps(fitted, indent=1) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"notes": notes, "policies": rows, "fitted": fitted}, indent=1))
        return 0
    any_row = rows["strong"]
    print(f"{any_row['tasks']} tasks, {any_row['samples']} paired samples; quick answers kept when the runtime Luau "
          f"check said: {', '.join(accept)}")
    for name, row in rows.items():
        print(_line(name, row))
    if fitted is not None:
        print("fitted routes: " + ", ".join(f"{c}={r}" for c, r in fitted["routes"].items()))
    mde = any_row.get("mde_tasks")
    print(f"note: with {any_row['tasks']} tasks the paired test resolves only a change of about {mde} tasks; SAFE means "
          "no lost pair on THESE runs, not proven equal. The in-sample table is optimistic: check it with --table "
          "on fresh runs." if mde else "note: SAFE means no lost pair on these runs.")
    for note in notes:
        print("note: " + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
