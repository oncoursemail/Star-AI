"""The gate: does a proposed change make STAR better, or at least no worse, on the golden tasks?

A change (a new skill pack, a routing rule, a prompt edit, a tool recipe) is first run through the
suite with `python -m star.evals run`; the gate then compares that result with the stored baseline:

    python -m star.evals gate --baseline evals/results/baseline-v2.json --candidate evals/results/change.json

Exit status:
    0  allowed: no previously passing task fails and the pass count did not drop
    1  blocked: the pass count dropped, or a previously passing task now fails
    2  unusable input: different suite, unreadable file, nothing to compare
    3  incomplete: tasks are missing or errored in the candidate run, so no verdict can be given

Only tasks scored (`pass` or `fail`) in the baseline take part. Tasks that errored (server down) are
never counted as failures, but they also never count as passes: the gate says "incomplete" instead.

Self-improvement code calls `evaluate_change(...)` or `gate_change(...)` and must refuse to enable a
change whose `Verdict.allowed` is False. Nothing here runs a model; it only reads result files.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path

ALLOWED, BLOCKED, UNUSABLE, INCOMPLETE = 0, 1, 2, 3
_SCORED = ("pass", "fail")


@dataclass
class Verdict:
    code: int
    baseline_pass: int = 0
    candidate_pass: int = 0
    compared: int = 0
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)       # errored in the candidate run: no verdict possible
    not_covered: list[str] = field(default_factory=list)      # not run at all (allowed for a targeted run)
    flaky: list[str] = field(default_factory=list)            # failed once, passed on the confirming re-run
    notes: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.code == ALLOWED

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "exit_code": self.code, "baseline_pass": self.baseline_pass,
                "candidate_pass": self.candidate_pass, "compared": self.compared,
                "regressions": self.regressions, "improvements": self.improvements,
                "incomplete": self.incomplete, "not_covered": self.not_covered, "flaky": self.flaky,
                "notes": self.notes}

    def text(self) -> str:
        head = {ALLOWED: "ALLOWED", BLOCKED: "BLOCKED", UNUSABLE: "UNUSABLE INPUT", INCOMPLETE: "INCOMPLETE"}[self.code]
        lines = [f"gate: {head} - {self.candidate_pass}/{self.compared} pass vs baseline {self.baseline_pass}/{self.compared} "
                 f"on the {self.compared} tasks scored in both"]
        for label, ids in (("regressions (passed before, fail now)", self.regressions),
                           ("improvements", self.improvements),
                           ("errored in the candidate run", self.incomplete),
                           ("not covered by the candidate run", self.not_covered),
                           ("failed once but passed on re-run (flaky)", self.flaky)):
            if ids:
                lines.append(f"  {label}: {', '.join(sorted(ids))}")
        lines.extend("  note: " + n for n in self.notes)
        return "\n".join(lines)


def load_result(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), dict) or not isinstance(data.get("suite"), dict):
        raise ValueError(f"{path} is not an evaluation result file")
    return data


def _status(result: dict, task_id: str) -> str:
    record = result["tasks"].get(task_id)
    return record.get("status", "missing") if isinstance(record, dict) else "missing"


def compare(baseline: dict, candidate: dict, *, allow_partial: bool = False) -> Verdict:
    """Pure comparison of two result dicts."""
    if baseline.get("suite", {}).get("sha256") != candidate.get("suite", {}).get("sha256"):
        return Verdict(UNUSABLE, notes=["the suite file differs from the baseline's: run a new baseline first"])
    scored = [tid for tid in baseline["tasks"] if _status(baseline, tid) in _SCORED]
    if not scored:
        return Verdict(UNUSABLE, notes=["the baseline has no scored tasks"])
    verdict = Verdict(ALLOWED)
    for tid in scored:
        before, after = _status(baseline, tid), _status(candidate, tid)
        if after in _SCORED:
            verdict.compared += 1
            verdict.baseline_pass += before == "pass"
            verdict.candidate_pass += after == "pass"
            if before == "pass" and after == "fail":
                verdict.regressions.append(tid)
            elif before == "fail" and after == "pass":
                verdict.improvements.append(tid)
        elif after == "missing":
            verdict.not_covered.append(tid)
        else:
            verdict.incomplete.append(tid)
    if not verdict.compared:
        return Verdict(UNUSABLE, incomplete=verdict.incomplete, not_covered=verdict.not_covered,
                       notes=["the candidate run scored none of the baseline's tasks"])
    for key in ("model", "mode"):
        a, b = baseline.get("run", {}).get(key), candidate.get("run", {}).get(key)
        if a != b:
            verdict.notes.append(f"{key} differs (baseline {a!r}, candidate {b!r}): the comparison is not like for like")
    if verdict.not_covered and allow_partial:
        verdict.notes.append(f"targeted run: {len(verdict.not_covered)} baseline tasks were not run by the candidate")
    if verdict.regressions or verdict.candidate_pass < verdict.baseline_pass:
        verdict.code = BLOCKED
        if verdict.candidate_pass < verdict.baseline_pass:
            verdict.notes.append("the pass count dropped")
    elif verdict.incomplete or (verdict.not_covered and not allow_partial):
        verdict.code = INCOMPLETE
    return verdict


def evaluate_change(baseline, candidate, *, allow_partial: bool = False) -> Verdict:
    """Compare result files (paths) or dicts. Unreadable input gives code 2 instead of raising."""
    try:
        base = baseline if isinstance(baseline, dict) else load_result(baseline)
        cand = candidate if isinstance(candidate, dict) else load_result(candidate)
    except (OSError, ValueError) as exc:
        return Verdict(UNUSABLE, notes=[f"cannot read results: {type(exc).__name__}"])
    return compare(base, cand, allow_partial=allow_partial)


def gate_change(baseline, run_candidate, *, rerun=None, allow_partial: bool = False) -> Verdict:
    """Run a proposed change through the gate end to end.

    `run_candidate()` returns the candidate result dict (the suite run with the change enabled).
    `rerun(task_ids)` optionally returns a result dict for just those tasks; a regression that passes
    on the re-run is reported as flaky and does not block. Without it every regression blocks.
    """
    base = baseline if isinstance(baseline, dict) else load_result(baseline)
    candidate = run_candidate()
    verdict = compare(base, candidate, allow_partial=allow_partial)
    if verdict.regressions and rerun is not None:
        again = rerun(list(verdict.regressions))
        confirmed = [t for t in verdict.regressions if _status(again, t) != "pass"]
        flaky = [t for t in verdict.regressions if t not in confirmed]
        merged = {**candidate, "tasks": {**candidate["tasks"], **{t: again["tasks"][t] for t in flaky}}}
        verdict = compare(base, merged, allow_partial=allow_partial)
        verdict.flaky = flaky
        if flaky:
            verdict.notes.append("regressions that passed on the confirming re-run are treated as noise")
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.evals gate")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path, help="result file of the run with the change enabled")
    parser.add_argument("--allow-partial", action="store_true",
                        help="the candidate run covered only the tasks the change can affect")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    args = parser.parse_args(argv)
    verdict = evaluate_change(args.baseline, args.candidate, allow_partial=args.allow_partial)
    print(json.dumps(verdict.to_dict()) if args.json else verdict.text())
    return verdict.code


if __name__ == "__main__":
    raise SystemExit(main())
