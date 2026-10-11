"""Policy/regression tests; no Roblox Studio sessions are simulated as real evidence."""
import json
import pytest
from star.frontier_lab import MIN_NET_TASK_WINS, Trial, load_trials, candidate_report

SHA = "a" * 40


def entry(c, task, n, result="pass", hard=False, seconds=1, split="holdout"):
    return dict(candidate=c, task_id=task, trial_index=n, split=split,
                verdict=result, hard_failure=hard, seconds=seconds,
                evaluator="trusted-runner@commit", artifact_commit=SHA)


def sample():
    """8 holdout tasks x 2 repeats. The baseline fails tasks 0-5, the candidate only task 0: 5 net task wins."""
    rows=[]
    for i in range(8):
        for j in range(2):
            rows.append(entry("base",f"task-{i}",j,"fail" if i < 6 else "pass"))
            rows.append(entry("new",f"task-{i}",j,"fail" if i==0 else "pass"))
    return rows


def weak_sample():
    """What used to be enough: 6 tasks x 2 repeats with 2 tasks better (the sample before the gate rule)."""
    rows=[]
    for i in range(6):
        for j in range(2):
            rows.append(entry("base",f"task-{i}",j,"fail" if i in (0,1,2) else "pass"))
            rows.append(entry("new",f"task-{i}",j,"fail" if i==0 else "pass"))
    return rows


def report(rows, **policy):
    return candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new",**policy)


def set_verdict(rows, who, task, verdicts):
    for x in rows:
        if x["candidate"]==who and x["task_id"]==task:
            x["verdict"]=verdicts[x["trial_index"]]


def test_eligible_provisional():
    r = candidate_report([Trial.parse(x) for x in sample()],baseline="base",candidate="new")
    assert r["decision"] == "candidate_for_independent_review"
    assert r["candidate_pass_rate"] > r["baseline_pass_rate"]
    assert "independent" in r["limitations"]
    assert r["reasons"] == []
    assert r["improved_tasks"] == [f"task-{i}" for i in range(1,6)]
    assert (r["net_task_wins"], r["required_net_task_wins"]) == (5, MIN_NET_TASK_WINS)
    assert r["regressed_tasks"] == [] and r["flaky_tasks"] == []


def test_hard_failure_vetoes_even_with_better_average():
    rows=sample()
    row=next(x for x in rows if x["candidate"]=="new" and x["task_id"]=="task-0" and x["trial_index"]==0)
    row["hard_failure"]=True
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"] == "do_not_promote"


def test_holdout_coverage_required():
    rows=sample()[16:]
    r=candidate_report([Trial.parse(x) for x in rows],baseline="base",candidate="new")
    assert r["decision"] == "do_not_promote"
    assert any("Only 4 holdout tasks" in reason for reason in r["reasons"])


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
    assert r["paired_holdout_trials"]==16


def test_bad_sha_rejected():
    row=entry("base","t",0);row["artifact_commit"]="not-a-commit"
    with pytest.raises(ValueError): Trial.parse(row)


def test_bad_type_rejected():
    row=entry("base","t",0);row["trial_index"]=True
    with pytest.raises(ValueError): Trial.parse(row)


def test_synthetic_demo_file_can_be_loaded(tmp_path):
    path=tmp_path / "results.json"
    path.write_text(json.dumps(sample()), encoding="utf8")
    assert len(load_trials(path))==32


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


# ---- the evaluation gate's rule: no regression, and at least five net task wins ----

def test_a_higher_pass_rate_alone_is_not_enough():
    r=report(weak_sample())
    assert r["candidate_pass_rate"] > r["baseline_pass_rate"]
    assert r["decision"]=="do_not_promote"
    assert r["net_task_wins"]==2
    assert r["reasons"]==["Net task wins 2 (2 improved on every repeat, 0 worse); the evaluation gate requires at least 5"]


def test_one_flipped_trial_over_five_tasks_is_not_promoted():
    rows=[]
    for i in range(5):
        for j in range(2):
            rows.append(entry("base",f"task-{i}",j,"fail" if (i,j)==(0,0) else "pass"))
            rows.append(entry("new",f"task-{i}",j,"pass"))
    r=report(rows)
    assert r["candidate_pass_rate"] > r["baseline_pass_rate"]
    assert r["decision"]=="do_not_promote" and r["net_task_wins"]==0 and r["improved_tasks"]==[]


def test_four_net_wins_are_refused_and_five_accepted():
    rows=sample()
    set_verdict(rows,"new","task-5",["fail","fail"])
    assert report(rows)["net_task_wins"]==4 and report(rows)["decision"]=="do_not_promote"
    assert report(sample())["net_task_wins"]==5 and report(sample())["decision"]=="candidate_for_independent_review"


def test_improvement_counts_only_when_every_repeat_agrees():
    rows=sample()
    set_verdict(rows,"new","task-5",["pass","fail"])           # passed once, failed on the repeat
    r=report(rows)
    assert "task-5" not in r["improved_tasks"] and r["net_task_wins"]==4 and r["decision"]=="do_not_promote"
    rows=sample()
    set_verdict(rows,"base","task-5",["fail","pass"])          # the baseline already passed it once
    r=report(rows)
    assert "task-5" not in r["improved_tasks"] and r["net_task_wins"]==4 and r["decision"]=="do_not_promote"


def strong_rows(tasks=11, baseline_fails=8):
    rows=[]
    for i in range(tasks):
        for j in range(2):
            rows.append(entry("base",f"task-{i:02d}",j,"fail" if i < baseline_fails else "pass"))
            rows.append(entry("new",f"task-{i:02d}",j,"pass"))
    return rows


def test_regression_vetoes_even_when_many_other_tasks_improve():
    rows=strong_rows()
    assert report(rows)["decision"]=="candidate_for_independent_review" and report(rows)["net_task_wins"]==8
    set_verdict(rows,"new","task-10",["fail","fail"])          # the baseline passed it; now it fails on both repeats
    r=report(rows)
    assert r["candidate_pass_rate"] > r["baseline_pass_rate"] and r["net_task_wins"]==7
    assert r["regressed_tasks"]==["task-10"] and r["decision"]=="do_not_promote"
    assert r["reasons"]==["1 holdout task(s) the baseline passed now fail on every repeat; "
                          "a regression vetoes even when other tasks improved"]


def test_failure_that_passes_on_its_repeat_is_flaky_and_counts_against_the_net():
    rows=strong_rows()
    set_verdict(rows,"new","task-10",["fail","pass"])
    r=report(rows)
    assert r["flaky_tasks"]==["task-10"] and r["regressed_tasks"]==[]
    assert r["net_task_wins"]==7 and r["decision"]=="candidate_for_independent_review"
    rows=sample()                                               # exactly 5 wins, then one flaky task: 4 net
    set_verdict(rows,"new","task-7",["pass","fail"])
    r=report(rows)
    assert r["flaky_tasks"]==["task-7"] and r["net_task_wins"]==4 and r["decision"]=="do_not_promote"


def test_task_the_baseline_passed_only_once_still_regresses_when_the_candidate_never_passes_it():
    rows=strong_rows()
    set_verdict(rows,"base","task-10",["pass","fail"])
    set_verdict(rows,"new","task-10",["fail","fail"])
    r=report(rows)
    assert r["regressed_tasks"]==["task-10"] and r["decision"]=="do_not_promote"


@pytest.mark.parametrize("value", [0, 1, 4, -1, True, 4.9, "5", None])
def test_the_net_win_floor_cannot_be_lowered(value):
    with pytest.raises(ValueError):
        report(sample(), min_net_wins=value)


def test_the_net_win_floor_can_be_raised():
    assert report(sample(), min_net_wins=5)["decision"]=="candidate_for_independent_review"
    r=report(sample(), min_net_wins=6)
    assert r["decision"]=="do_not_promote" and r["required_net_task_wins"]==6


def test_command_line_uses_the_floor_and_refuses_a_lower_one(tmp_path, monkeypatch, capsys):
    import sys
    from star import frontier_lab
    path=tmp_path / "results.json"
    path.write_text(json.dumps(weak_sample()), encoding="utf8")
    monkeypatch.setattr(sys,"argv",["frontier_lab",str(path),"--baseline","base","--candidate","new"])
    frontier_lab.main()
    assert json.loads(capsys.readouterr().out)["decision"]=="do_not_promote"
    monkeypatch.setattr(sys,"argv",["frontier_lab",str(path),"--baseline","base","--candidate","new","--min-net-wins","1"])
    with pytest.raises(ValueError):
        frontier_lab.main()
