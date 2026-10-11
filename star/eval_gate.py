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
_LEGACY = {"baseline-v2.json", "baseline-creation-v1.json"}
_VALID_STATUS = {"pass", "fail", "error", "skipped"}
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
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not an evaluation result file")
    data = {**data, "_legacy": Path(path).name in _LEGACY
            and Path(path).parent.name == "results"
            and Path(path).parent.parent.name == "evals"}
    return data


def _trial_summary(result: dict) -> bool:
    """The frontier lab passes paired in-memory statuses, not persisted runner files."""
    return (isinstance(result, dict) and set(result) == {"suite", "tasks"}
            and isinstance(result["suite"], dict) and set(result["suite"]) == {"sha256"}
            and isinstance(result["suite"]["sha256"], str)
            and bool(result["suite"]["sha256"])
            and isinstance(result["tasks"], dict)
            and all(isinstance(tid, str) and bool(tid)
                    and isinstance(row, dict) and set(row) == {"status"}
                    and isinstance(row["status"], str) and row["status"] in _VALID_STATUS
                    for tid, row in result["tasks"].items()))


def _validate(result: dict, label: str) -> list[str]:
    if not isinstance(result, dict):
        return [f"{label}: expected a result object"]
    suite, run, tasks = result.get("suite"), result.get("run"), result.get("tasks")
    if not isinstance(suite, dict) or not isinstance(run, dict) or not isinstance(tasks, dict):
        return [f"{label}: suite, run and tasks must be objects"]
    problems = []
    if result.get("schema") != 1:
        problems.append(f"{label}: unsupported result schema")
    for key in ("sha256", "file"):
        if not isinstance(suite.get(key), str) or not suite[key].strip():
            problems.append(f"{label}: missing suite.{key}")
    if not isinstance(suite.get("tasks_total"), int) or suite["tasks_total"] < 1:
        problems.append(f"{label}: invalid suite.tasks_total")
    if not isinstance(suite.get("automated"), int) or suite["automated"] < 0:
        problems.append(f"{label}: invalid suite.automated")
    selected = suite.get("selected")
    if not isinstance(selected, list) or any(not isinstance(t, str) or not t for t in selected) or len(set(selected)) != len(selected):
        problems.append(f"{label}: invalid suite.selected")
    for key in ("model", "mode", "app_commit"):
        if not isinstance(run.get(key), str) or not run[key].strip():
            problems.append(f"{label}: missing run.{key}")
    for key in ("identity_sha256",):
        if not isinstance(suite.get(key), str) or not suite[key].strip():
            if result.get("_legacy"):
                problems.append(f"{label}: legacy result missing suite.{key}; compatibility allowed")
            else:
                problems.append(f"{label}: missing suite.{key}")
    if not isinstance(run.get("grader_sha256"), str) or not run.get("grader_sha256"):
        if result.get("_legacy"):
            problems.append(f"{label}: legacy result missing run.grader_sha256; compatibility allowed")
        else:
            problems.append(f"{label}: missing run.grader_sha256")
    if not tasks:
        problems.append(f"{label}: empty tasks")
    for tid, record in tasks.items():
        if not isinstance(tid, str) or not tid or not isinstance(record, dict):
            problems.append(f"{label}: invalid task row {tid!r}")
            continue
        status = record.get("status")
        if not isinstance(status, str) or status not in _VALID_STATUS:
            problems.append(f"{label}: {tid}: invalid status {status!r}")
        if "passed" in record and (not isinstance(record["passed"], bool)
                                    or (status == "pass" and not record["passed"])
                                    or (status == "fail" and record["passed"])):
            problems.append(f"{label}: {tid}: inconsistent passed flag")
        if status in _SCORED and "passed" not in record and not result.get("_legacy"):
            problems.append(f"{label}: {tid}: missing passed flag")
        if "checks" in record and (not isinstance(record["checks"], list)
                                   or any(not isinstance(c, dict) or not isinstance(c.get("id"), str)
                                          or not isinstance(c.get("ok"), bool) for c in record["checks"])):
            problems.append(f"{label}: {tid}: malformed checks")
        if "reasons" in record and (not isinstance(record["reasons"], list)
                                    or any(not isinstance(x, str) for x in record["reasons"])):
            problems.append(f"{label}: {tid}: malformed reasons")
    return problems


def _errors(result: dict, label: str) -> tuple[list[str], list[str]]:
    problems = _validate(result, label)
    return ([p for p in problems if "legacy result" not in p],
            [p for p in problems if "legacy result" in p])


def _status(result: dict, task_id: str) -> str:
    record = result["tasks"].get(task_id)
    return record.get("status", "missing") if isinstance(record, dict) else "missing"


def compare(baseline: dict, candidate: dict, *, allow_partial: bool = False) -> Verdict:
    """Pure comparison of two result dicts."""
    summary = _trial_summary(baseline) and _trial_summary(candidate)
    if summary:
        if baseline["suite"]["sha256"] != candidate["suite"]["sha256"]:
            return Verdict(UNUSABLE, notes=["the paired trial suite differs"])
        base_errors, base_legacy, cand_errors, cand_legacy = [], [], [], []
    else:
        base_errors, base_legacy = _errors(baseline, "baseline")
        cand_errors, cand_legacy = _errors(candidate, "candidate")
    if base_errors or cand_errors:
        return Verdict(UNUSABLE, notes=base_errors + cand_errors)
    for key in (() if summary else ("sha256", "file", "tasks_total", "automated")):
        if baseline["suite"].get(key) != candidate["suite"].get(key):
            return Verdict(UNUSABLE, notes=[f"suite {key} differs: not a like-for-like comparison"])
    if not summary and not base_legacy and not cand_legacy and baseline["suite"]["identity_sha256"] != candidate["suite"]["identity_sha256"]:
        return Verdict(UNUSABLE, notes=["suite identity differs (including grader materials)"])
    for key in (() if summary else ("model", "mode")):
        if baseline["run"][key] != candidate["run"][key]:
            return Verdict(UNUSABLE, notes=[f"{key} differs: not a like-for-like comparison"])
    if not summary and not base_legacy and not cand_legacy and baseline["run"]["grader_sha256"] != candidate["run"]["grader_sha256"]:
        return Verdict(UNUSABLE, notes=["grader revision differs: re-score with matching graders first"])
    scored = [tid for tid in baseline["tasks"] if _status(baseline, tid) in _SCORED]
    if not scored:
        return Verdict(UNUSABLE, notes=["the baseline has no scored tasks"])
    verdict = Verdict(ALLOWED, notes=base_legacy + cand_legacy)
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
    except (OSError, ValueError, TypeError) as exc:
        return Verdict(UNUSABLE, notes=[f"cannot read results: {exc}"])
    return compare(base, cand, allow_partial=allow_partial)


def gate_change(baseline, run_candidate, *, rerun=None, allow_partial: bool = False) -> Verdict:
    """Run a proposed change through the gate end to end.

    `run_candidate()` returns the candidate result dict (the suite run with the change enabled).
    `rerun(task_ids)` optionally returns a result dict for just those tasks; a regression that passes
    on the re-run is reported as flaky and does not block. Without it every regression blocks.
    """
    try:
        base = baseline if isinstance(baseline, dict) else load_result(baseline)
        candidate = run_candidate()
    except (OSError, ValueError, TypeError) as exc:
        return Verdict(UNUSABLE, notes=[f"unusable input: {exc}"])
    verdict = compare(base, candidate, allow_partial=allow_partial)
    if verdict.regressions and rerun is not None:
        try:
            again = rerun(list(verdict.regressions))
        except (OSError, ValueError, TypeError) as exc:
            return Verdict(UNUSABLE, notes=[f"cannot read rerun: {exc}"])
        summary = _trial_summary(candidate) and _trial_summary(again)
        errors, legacy = ([], []) if summary else _errors(again, "rerun")
        if errors or legacy:
            return Verdict(UNUSABLE, notes=errors + legacy)
        for key in (("sha256",) if summary else ("sha256", "file", "tasks_total", "automated", "identity_sha256")):
            if again["suite"].get(key) != candidate["suite"].get(key):
                return Verdict(UNUSABLE, notes=[f"rerun suite {key} differs"])
        for key in (() if summary else ("model", "mode", "app_commit", "grader_sha256")):
            if again["run"].get(key) != candidate["run"].get(key):
                return Verdict(UNUSABLE, notes=[f"rerun {key} differs"])
        if any(t not in again["tasks"] for t in verdict.regressions):
            return Verdict(UNUSABLE, notes=["rerun omitted a regression task"])
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
