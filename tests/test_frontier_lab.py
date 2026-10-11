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


# ---- the rule is the evaluation gate's own code (star/eval_gate.py), not a copy kept here ----

def gate_results(statuses):
    return {"suite": {"sha256": "same suite"}, "tasks": {task: {"status": status} for task, status in statuses.items()}}


def test_the_verdict_is_the_one_the_gate_module_gives_for_the_same_tasks():
    from star import eval_gate
    rows=strong_rows()
    set_verdict(rows,"new","task-10",["fail","fail"])          # the baseline passed it: a regression
    set_verdict(rows,"new","task-09",["fail","pass"])          # the baseline passed it: flaky
    set_verdict(rows,"new","task-00",["pass","fail"])          # the baseline failed it: not an improvement
    r=report(rows)
    # The same tasks written by hand as the gate's result files: baseline, candidate run, confirming re-run.
    base=gate_results({f"task-{i:02d}":"fail" if i < 8 else "pass" for i in range(11)})
    first=gate_results({**{f"task-{i:02d}":"pass" for i in range(11)},"task-10":"fail","task-09":"fail","task-00":"fail"})
    again=gate_results({"task-10":"fail","task-09":"pass"})
    expected=eval_gate.gate_change(base,lambda:first,rerun=lambda ids:again)
    assert expected.code==eval_gate.BLOCKED
    assert r["gate"]==expected.to_dict() and r["gate"]["allowed"] is False
    assert r["regressed_tasks"]==sorted(expected.regressions)==["task-10"]
    assert r["flaky_tasks"]==sorted(expected.flaky)==["task-09"]
    assert r["improved_tasks"]==sorted(expected.improvements)==[f"task-{i:02d}" for i in range(1,8)]
    assert r["net_task_wins"]==5 and r["decision"]=="do_not_promote"


def test_the_gate_module_decides_not_a_copy_in_frontier_lab(monkeypatch):
    from star import eval_gate, frontier_lab
    assert frontier_lab.eval_gate is eval_gate
    assert report(sample())["decision"]=="candidate_for_independent_review"
    calls=[]
    real=eval_gate.compare

    def refusing(baseline, candidate, **options):
        calls.append((baseline, candidate))
        verdict=real(baseline, candidate, **options)
        verdict.code=eval_gate.BLOCKED
        verdict.notes.append("stand-in refusal")
        return verdict
    monkeypatch.setattr(eval_gate,"compare",refusing)
    r=report(sample())                                          # the rows that were accepted two lines above
    assert len(calls)==1 and r["decision"]=="do_not_promote" and r["gate"]["allowed"] is False
    assert r["reasons"]==["The evaluation gate did not allow the change (blocked; stand-in refusal)"]
    baseline, candidate=calls[0]                                # what the gate was given: one status per task
    assert baseline["suite"]==candidate["suite"] and set(baseline["tasks"])=={f"task-{i}" for i in range(8)}
    assert [baseline["tasks"][f"task-{i}"]["status"] for i in range(8)]==["fail"]*6+["pass"]*2
    assert [candidate["tasks"][f"task-{i}"]["status"] for i in range(8)]==["fail"]+["pass"]*7

    def regression(baseline, run_candidate, **options):
        return eval_gate.Verdict(eval_gate.BLOCKED, regressions=["task-7"], improvements=["task-1"])
    monkeypatch.setattr(eval_gate,"gate_change",regression)
    r=report(sample())
    assert r["regressed_tasks"]==["task-7"] and r["improved_tasks"]==["task-1"] and r["net_task_wins"]==0
    assert r["decision"]=="do_not_promote" and r["reasons"][0].startswith("1 holdout task(s) the baseline passed now fail")


def test_a_task_that_is_noisy_in_both_arms_is_flaky_for_the_gate_but_not_counted_as_worse():
    rows=strong_rows()
    set_verdict(rows,"base","task-10",["pass","fail"])
    set_verdict(rows,"new","task-10",["fail","pass"])
    r=report(rows)
    assert r["gate"]["flaky"]==["task-10"] and r["gate"]["allowed"] is True
    assert r["flaky_tasks"]==[] and r["regressed_tasks"]==[]
    assert r["net_task_wins"]==8 and r["decision"]=="candidate_for_independent_review"


def test_a_blocked_trial_or_nothing_paired_gives_no_gate_verdict():
    from star import eval_gate
    rows=sample()
    next(x for x in rows if x["candidate"]=="new")["verdict"]="blocked"
    r=report(rows)
    assert r["gate"]["exit_code"]==eval_gate.INCOMPLETE and r["gate"]["incomplete"]==["task-0"]
    assert "The evaluation gate did not allow the change (incomplete)" in r["reasons"] and r["decision"]=="do_not_promote"
    r=report([x for x in sample() if x["candidate"]=="base"])
    assert r["gate"]["exit_code"]==eval_gate.UNUSABLE and r["decision"]=="do_not_promote"
    assert "The evaluation gate did not allow the change (nothing to compare; the baseline has no scored tasks)" in r["reasons"]


def test_a_single_repeat_has_no_confirming_rerun_so_every_failure_is_a_regression():
    rows=[x for x in strong_rows() if x["trial_index"]==0]
    assert report(rows, repeats=1)["decision"]=="candidate_for_independent_review"
    set_verdict(rows,"new","task-10",["fail"])
    r=report(rows, repeats=1)
    assert r["regressed_tasks"]==["task-10"] and r["flaky_tasks"]==[] and r["decision"]=="do_not_promote"
