"""STAR Frontier Lab: compare *externally measured* agent candidates.

This module deliberately does NOT execute untrusted code or pretend to evaluate
Roblox Studio. It enforces holdout separation, paired comparisons, repeated
trials, evidence provenance and hard-failure vetoes on supplied run records.
The independent task runner (future work) must produce trustworthy evidence.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import re

from . import eval_gate

COMMIT_SHA = re.compile(r"^[a-fA-F0-9]{40}$")
VALID_SPLITS = {"development", "holdout"}
VALID_VERDICTS = {"pass", "fail", "blocked"}
# Promotion needs more than the evaluation gate's "no worse" (star/eval_gate.py has no number): the same
# unchanged build flips about one task in six between runs, so fewer net task wins than this is noise,
# not evidence. This floor is this module's own, on top of the gate. It can be raised, never lowered.
MIN_NET_TASK_WINS = 5


@dataclass(frozen=True)
class Trial:
    candidate: str
    task_id: str
    trial_index: int
    split: str
    verdict: str
    hard_failure: bool
    seconds: float
    evaluator: str
    artifact_commit: str

    @classmethod
    def parse(cls, value: Any) -> "Trial":
        if not isinstance(value, dict):
            raise ValueError("Trial must be an object")
        required = set(cls.__dataclass_fields__)
        if set(value) != required:
            raise ValueError(f"Invalid fields in trial: {sorted(required ^ set(value))}")
        c = cls(**value)
        if (not all(isinstance(getattr(c, f), str) and getattr(c, f)
                    for f in ("candidate", "task_id", "evaluator", "artifact_commit"))
                or len(c.candidate) > 60 or len(c.task_id) > 100 or len(c.evaluator) > 100):
            raise ValueError("Invalid candidate/task/evaluator names")
        if not isinstance(c.trial_index, int) or isinstance(c.trial_index, bool) or c.trial_index < 0:
            raise ValueError("trial_index must be nonnegative integer")
        if c.split not in VALID_SPLITS or c.verdict not in VALID_VERDICTS:
            raise ValueError("Unknown split or verdict")
        if not isinstance(c.hard_failure, bool):
            raise ValueError("hard_failure must be boolean")
        if not isinstance(c.seconds, (int, float)) or isinstance(c.seconds, bool) or not 0 <= c.seconds < 1e7:
            raise ValueError("Invalid elapsed seconds")
        if not COMMIT_SHA.fullmatch(c.artifact_commit):
            raise ValueError("artifact_commit must be a full Git SHA-1 (40 hex) in this prototype")
        if c.verdict == "pass" and c.hard_failure:
            raise ValueError("A passed trial cannot contain a hard failure")
        return c


def load_trials(path: Path) -> list[Trial]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Expected a JSON array of trials")
    trials = [Trial.parse(row) for row in raw]
    keys = [(t.candidate, t.task_id, t.trial_index, t.split) for t in trials]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate candidate/task/trial/split records")
    return trials


def gate_verdict(baseline_trials: dict, candidate_trials: dict, by_task: dict) -> eval_gate.Verdict:
    """The evaluation gate's own verdict (`star.eval_gate.gate_change`) on the paired holdout trials.

    The gate compares one status per task and confirms a regression with one re-run. The recorded
    repeats are that re-run, so the trials are handed to it as three result sets:

    * the baseline passed a task when any of its repeats passed;
    * the candidate's run passed a task only when every repeat passed;
    * the confirming re-run of a task the gate reports as a regression passed when any repeat passed.

    So the gate itself decides: failing every repeat of a task the baseline passed is a regression
    (blocked), failing only some repeats is flaky, and an improvement is a task the baseline failed on
    every repeat and the candidate passed on every repeat. A task with a blocked trial has no score.
    """
    def results(trials: dict, passed) -> dict:
        tasks = {}
        for task in sorted(by_task):
            verdicts = [trials[key].verdict for key in by_task[task]]
            status = "error" if "blocked" in verdicts else "pass" if passed(v == "pass" for v in verdicts) else "fail"
            tasks[task] = {"status": status}
        return {"suite": suite, "tasks": tasks}

    # Both arms are the same paired holdout trials by construction, which is what the gate's suite check asks.
    paired = sorted([task, index] for task, keys in by_task.items() for _task, index in keys)
    suite = {"sha256": hashlib.sha256(json.dumps(paired).encode("utf-8")).hexdigest()}
    confirming = results(candidate_trials, any)
    return eval_gate.gate_change(
        results(baseline_trials, any), lambda: results(candidate_trials, all),
        rerun=lambda task_ids: {"suite": suite, "tasks": {task: confirming["tasks"][task] for task in task_ids}})


def candidate_report(trials: list[Trial], *, baseline: str, candidate: str,
                     minimum_holdout_tasks: int = 5, repeats: int = 2,
                     max_slowdown: float = 2.0, min_net_wins: int = MIN_NET_TASK_WINS) -> dict:
    """Produce an honest provisional decision, not a Studio QA certification.

    Acceptance requires identical holdout case/repeat keys, no hard-failure trials, no blocked
    trials, no large latency increase, and the evaluation gate's rule. The rule is not copied here:
    `gate_verdict` hands the holdout trials to `star.eval_gate`, and its verdict decides

    * regressions: a task the baseline passed must not fail now, even if other tasks improved. A
      failure counts once its repeats confirm it (the gate's "re-run a regression once"): failing
      every repeat is a regression and vetoes; failing some repeats is flaky;
    * improvements: the baseline failed every repeat and the candidate passed every repeat.

    On top of the gate, this module's own promotion floor: improved tasks minus worse tasks must reach
    `min_net_wins` (5 or more), where worse is a regression or a flaky task on which the candidate
    passed fewer repeats than the baseline. A higher pass rate alone is not enough: one flipped task
    used to pass this check.

    Development-split results are ignored for promotion.
    """
    if baseline == candidate:
        raise ValueError("Candidate and baseline must differ")
    if minimum_holdout_tasks < 1 or repeats < 1 or max_slowdown <= 0:
        raise ValueError("Invalid policy")
    if not isinstance(min_net_wins, int) or isinstance(min_net_wins, bool) or min_net_wins < MIN_NET_TASK_WINS:
        raise ValueError(f"min_net_wins cannot be lower than the evaluation gate's floor of {MIN_NET_TASK_WINS}")
    by_candidate = defaultdict(dict)
    for t in trials:
        if t.split == "holdout" and t.candidate in {baseline, candidate}:
            key = (t.task_id, t.trial_index)
            if key in by_candidate[t.candidate]:
                raise ValueError("Duplicate result")
            by_candidate[t.candidate][key] = t
    a, b = by_candidate[baseline], by_candidate[candidate]
    base_keys, proposed_keys = set(a), set(b)
    required_tasks = {k[0] for k in base_keys | proposed_keys}
    missing = sorted(base_keys ^ proposed_keys)
    problems = []
    if missing:
        problems.append(f"Mismatched holdout coverage: {len(missing)} paired trials missing")
    if len(required_tasks) < minimum_holdout_tasks:
        problems.append(f"Only {len(required_tasks)} holdout tasks; require {minimum_holdout_tasks}")
    if any(any((task, i) not in a or (task, i) not in b for i in range(repeats)) for task in required_tasks):
        problems.append(f"Each holdout task needs first {repeats} paired repeat trials")
    if any(t.verdict == "blocked" for t in list(a.values()) + list(b.values())):
        problems.append("Blocked trial is present; resolve the infrastructure issue")
    if any(t.hard_failure for t in b.values()):
        problems.append("Candidate has a hard safety/correctness failure")
    common_keys = base_keys & proposed_keys
    if not common_keys:
        problems.append("No paired holdout results")
    denom = len(common_keys) or 1
    a_rate = sum(a[k].verdict == "pass" for k in common_keys) / denom
    b_rate = sum(b[k].verdict == "pass" for k in common_keys) / denom
    a_time = sum(a[k].seconds for k in common_keys)
    b_time = sum(b[k].seconds for k in common_keys)
    if b_rate <= a_rate:
        problems.append("No measured improvement in holdout pass rate")
    by_task = defaultdict(list)
    for key in common_keys:
        by_task[key[0]].append(key)
    verdict = gate_verdict(a, b, by_task)
    improved, regressed = sorted(verdict.improvements), sorted(verdict.regressions)

    def fewer_passes(task: str) -> bool:
        keys = by_task[task]
        return sum(b[k].verdict == "pass" for k in keys) < sum(a[k].verdict == "pass" for k in keys)
    # A task that is noisy in both arms is flaky for the gate too, but the candidate did not make it worse.
    flaky = sorted(task for task in verdict.flaky if fewer_passes(task))
    net_wins = len(improved) - len(regressed) - len(flaky)
    if regressed:
        problems.append(f"{len(regressed)} holdout task(s) the baseline passed now fail on every repeat; "
                        "a regression vetoes even when other tasks improved")
    elif not verdict.allowed:
        # Fail closed: blocked for another reason, or no verdict at all (nothing scored, a blocked trial).
        state = {eval_gate.BLOCKED: "blocked", eval_gate.UNUSABLE: "nothing to compare",
                 eval_gate.INCOMPLETE: "incomplete"}.get(verdict.code, f"code {verdict.code}")
        problems.append("The evaluation gate did not allow the change (" + "; ".join([state] + verdict.notes) + ")")
    if net_wins < min_net_wins:
        problems.append(f"Net task wins {net_wins} ({len(improved)} improved on every repeat, "
                        f"{len(regressed) + len(flaky)} worse); the evaluation gate requires at least {min_net_wins}")
    if b_time > max(a_time, 0.001) * max_slowdown:
        problems.append(f"Candidate elapsed time exceeds {max_slowdown}x baseline")
    return {
        "baseline": baseline,
        "candidate": candidate,
        "paired_holdout_trials": len(common_keys),
        "holdout_tasks": len(required_tasks),
        "baseline_pass_rate": round(a_rate, 4),
        "candidate_pass_rate": round(b_rate, 4),
        "baseline_total_seconds": round(a_time, 2),
        "candidate_total_seconds": round(b_time, 2),
        "improved_tasks": improved,
        "regressed_tasks": regressed,
        "flaky_tasks": flaky,
        "net_task_wins": net_wins,
        "required_net_task_wins": min_net_wins,
        "gate": verdict.to_dict(),
        "decision": "candidate_for_independent_review" if not problems else "do_not_promote",
        "reasons": problems,
        "limitations": "Compares supplied results only. Does not verify that the evaluator ran, that artifacts correspond to commits, or that trial fixtures stayed hidden. An independent trusted runner must attest to these before any promotion."
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Compare externally evaluated STAR variants. NO actual tests are run.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--min-tasks", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--min-net-wins", type=int, default=MIN_NET_TASK_WINS,
                        help=f"improved tasks minus worse tasks needed (default and floor {MIN_NET_TASK_WINS})")
    args = parser.parse_args()
    result = candidate_report(load_trials(args.file), baseline=args.baseline, candidate=args.candidate,
                              minimum_holdout_tasks=args.min_tasks, repeats=args.repeats,
                              min_net_wins=args.min_net_wins)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
