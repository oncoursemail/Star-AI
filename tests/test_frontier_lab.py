"""Policy/regression tests; no Roblox Studio sessions are simulated as real evidence."""
import json
import pytest
from star.frontier_lab import Trial, load_trials, candidate_report

SHA = "a" * 40


def entry(c, task, n, result="pass", hard=False, seconds=1, split="holdout"):
    return dict(candidate=c, task_id=task, trial_index=n, split=split,
                verdict=result, hard_failure=hard, seconds=seconds,
                evaluator="trusted-runner@commit", artifact_commit=SHA)


def sample():
    rows=[]
    for i in range(6):
        for j in range(2):
            rows.append(entry("base",f"task-{i}",j,"fail" if i in (0,1,2) else "pass"))
            rows.append(entry("new",f"task-{i}",j,"fail" if i==0 else "pass"))
    return rows


def test_eligible_provisional():
    r = candidate_report([Trial.parse(x) for x in sample()],baseline="base",candidate="new")
    assert r["decision"] == "candidate_for_independent_review"
    assert r["candidate_pass_rate"] > r["baseline_pass_rate"]
    assert "independent" in r["limitations"]


def test_hard_failure_vetoes_even_with_better_average():
    rows=sample()
    row=next(x for x in rows if x["candidate"]=="new" and x["task_id"]=="task-0" and x["trial_index"]==0)
    row["hard_failure"]=True
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"] == "do_not_promote"


def test_holdout_coverage_required():
    rows=sample()[8:]
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"] == "do_not_promote"


def test_blocked_veto():
    rows=sample()
    row=next(x for x in rows if x["candidate"]=="new")
    row["verdict"]="blocked"
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"] == "do_not_promote"


def test_slow_veto():
    rows=sample()
    for x in rows:
        if x["candidate"] == "new": x["seconds"] = 3.0
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"] == "do_not_promote"


def test_development_trials_excluded():
    rows=sample()
    rows += [entry("new","training-task",0,"pass",split="development")]
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["paired_holdout_trials"]==12


def test_bad_sha_rejected():
    row=entry("base","t",0);row["artifact_commit"]="not-a-commit"
    with pytest.raises(ValueError): Trial.parse(row)


def test_bad_type_rejected():
    row=entry("base","t",0);row["trial_index"]=True
    with pytest.raises(ValueError): Trial.parse(row)


def test_synthetic_demo_file_can_be_loaded(tmp_path):
    path=tmp_path / "results.json"
    path.write_text(json.dumps(sample()), encoding="utf8")
    assert len(load_trials(path))==24


def test_duplicate_rejected(tmp_path):
    rows=sample(); rows.append(rows[0])
    path=tmp_path / "results.json"; path.write_text(json.dumps(rows),encoding="utf8")
    with pytest.raises(ValueError):load_trials(path)


def test_unmatched_trial_rejected():
    rows=sample(); rows.pop()
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"]=="do_not_promote"


def test_no_improvement_rejected():
    rows=sample()
    for x in rows:
        if x["candidate"]=="new":x["verdict"]="fail"
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"]=="do_not_promote"
