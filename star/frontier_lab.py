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
import json
import re

COMMIT_SHA = re.compile(r"^[a-fA-F0-9]{40}$")
VALID_SPLITS = {"development", "holdout"}
VALID_VERDICTS = {"pass", "fail", "blocked"}
# The evaluation gate's floor for "better": the same unchanged build flips about one task in six
# between runs, so fewer net task wins than this is noise, not evidence. It can be raised, never lowered.
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


def candidate_report(trials: list[Trial], *, baseline: str, candidate: str,
                     minimum_holdout_tasks: int = 5, repeats: int = 2,
                     max_slowdown: float = 2.0, min_net_wins: int = MIN_NET_TASK_WINS) -> dict:
    """Produce an honest provisional decision, not a Studio QA certification.

    Acceptance requires identical holdout case/repeat keys, no hard-failure trials, no blocked
    trials, no large latency increase, and the evaluation gate's rule, applied per holdout task:

    * a task the baseline passed must not fail now, even if other tasks improved. A failure counts
      once its repeats confirm it (the gate's "re-run a regression once"): failing every repeat is a
      regression and vetoes; failing some repeats is reported as flaky and counts against the net;
    * a task counts as improved only when the baseline failed every repeat and the candidate passed
      every repeat;
    * improved tasks minus worse tasks must reach `min_net_wins` (5 or more). A higher pass rate
      alone is not enough: one flipped task used to pass this check.

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
    improved, regressed, flaky = [], [], []
    for task in sorted(by_task):
        keys = by_task[task]
        before = sum(a[k].verdict == "pass" for k in keys)
        after = sum(b[k].verdict == "pass" for k in keys)
        if before == 0 and after == len(keys):
            improved.append(task)
        elif after < before:
            (regressed if after == 0 else flaky).append(task)
    net_wins = len(improved) - len(regressed) - len(flaky)
    if regressed:
        problems.append(f"{len(regressed)} holdout task(s) the baseline passed now fail on every repeat; "
                        "a regression vetoes even when other tasks improved")
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
