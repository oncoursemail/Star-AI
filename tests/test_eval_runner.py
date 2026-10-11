"""The evaluation runner (star/eval_runner.py) with fakes, and the shipped suite's own consistency."""
import json
import os
from pathlib import Path

import pytest

from star import eval_checks as ec
from star import eval_runner as er

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evals" / "roblox" / "golden-tasks-v2.json"
PACKS = {"roblox-ui-layout", "roblox-secure-remotes", "roblox-datastore-safety",
         "roblox-animation-tools", "roblox-performance-streaming"}


def mini_task(tid, mode="automated", **extra):
    return {"id": tid, "category": "c", "goal": "g", "required_evidence": ["e"], "pass_conditions": ["p"],
            "run_mode": mode, "prompt": "Write " + tid, "auto": {"code": False, "compile": False}, **extra}


def mini_suite(tmp_path, tasks=None):
    tasks = tasks or [mini_task("A-1"), mini_task("A-2"), mini_task("S-1", mode="studio", auto=None)]
    for t in tasks:
        if t.get("auto") is None:
            t.pop("auto", None)
            t["studio_check"] = "look at it"
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    return er.load_suite(path)


def scorer_for(passing):
    def scorer(task, answer):
        score = ec.TaskScore()
        score.checks.append(ec.Check("x", task["id"] in passing, "" if task["id"] in passing else "nope"))
        return score
    return scorer


def asker(answers=None, seconds=1.5, fail_on=()):
    log = []

    def ask(task, cancel=None):
        log.append(task["id"])
        if task["id"] in fail_on:
            raise TimeoutError("server timed out at 10.17.0.146:8080")
        return er.Asked((answers or {}).get(task["id"], "answer for " + task["id"]),
                        [{"event": "route_selected", "profile": "roblox"}, {"event": "assistant_delta", "text": "x"},
                         {"event": "skill_packs", "names": ["roblox-ui-layout"]}], seconds)
    ask.log = log
    return ask


RUN_INFO = {"model": "star-fast", "mode": "auto", "fingerprint": "abc"}


def test_run_suite_scores_checkpoints_and_skips_studio_tasks(tmp_path):
    suite, out = mini_suite(tmp_path), tmp_path / "r.json"
    result = er.run_suite(suite, out=out, ask=asker(), scorer=scorer_for({"A-1"}), run_info=dict(RUN_INFO), log=lambda m: None)
    assert result["complete"] and result["summary"]["pass"] == 1 and result["summary"]["fail"] == 1
    assert result["tasks"]["S-1"]["status"] == "skipped"
    a1 = result["tasks"]["A-1"]
    assert a1["status"] == "pass" and a1["packs"] == ["roblox-ui-layout"] and a1["seconds"] == 1.5
    assert [e["event"] for e in a1["events"]] == ["route_selected", "skill_packs"]       # no token deltas stored
    assert result["tasks"]["A-2"]["reasons"] == ["x: nope"]
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["scored"] == 2


def test_run_suite_resumes_without_asking_again(tmp_path):
    suite, out = mini_suite(tmp_path), tmp_path / "r.json"
    first = asker(fail_on=("A-2",))
    er.run_suite(suite, out=out, ask=first, scorer=scorer_for({"A-1", "A-2"}), run_info=dict(RUN_INFO), log=lambda m: None)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["tasks"]["A-2"]["status"] == "error" and first.log == ["A-1", "A-2"]
    second = asker()
    er.run_suite(suite, out=out, ask=second, scorer=scorer_for({"A-1", "A-2"}), run_info=dict(RUN_INFO), log=lambda m: None)
    assert second.log == []                                       # an error is kept unless asked to retry
    third = asker()
    result = er.run_suite(suite, out=out, ask=third, scorer=scorer_for({"A-1", "A-2"}), run_info=dict(RUN_INFO),
                          retry_errors=True, log=lambda m: None)
    assert third.log == ["A-2"] and result["summary"]["pass"] == 2


def test_infrastructure_failures_are_errors_not_failures_and_are_scrubbed(tmp_path):
    suite, out = mini_suite(tmp_path), tmp_path / "r.json"
    result = er.run_suite(suite, out=out, ask=asker(fail_on=("A-1",)), scorer=scorer_for({"A-2"}),
                          run_info=dict(RUN_INFO), log=lambda m: None, secrets=["sekrit-key"])
    assert result["tasks"]["A-1"]["status"] == "error" and result["summary"]["error"] == 1
    text = out.read_text(encoding="utf-8")
    assert "10.17.0.146" not in text and "<private-address>" in text


def test_stars_own_failure_to_answer_is_a_failed_task_not_an_infrastructure_error(tmp_path):
    def ask(task, cancel=None):
        raise RuntimeError("Model-call limit exceeded; results are not considered complete")

    result = er.run_suite(mini_suite(tmp_path, [mini_task("A-1")]), out=tmp_path / "r.json", ask=ask,
                          scorer=scorer_for(set()), run_info=dict(RUN_INFO), log=lambda m: None)
    record = result["tasks"]["A-1"]
    assert record["status"] == "fail" and "Model-call limit exceeded" in record["reasons"][0]
    assert result["summary"]["fail"] == 1 and result["summary"]["error"] == 0


def test_scoring_infra_error_is_an_error_record(tmp_path):
    def scorer(task, answer):
        raise ec.InfraError("sandbox: ssh to the sandbox timed out")

    result = er.run_suite(mini_suite(tmp_path), out=tmp_path / "r.json", ask=asker(), scorer=scorer,
                          run_info=dict(RUN_INFO), log=lambda m: None)
    assert result["summary"]["error"] == 2 and "sandbox" in result["tasks"]["A-1"]["reasons"][0]


def test_resume_refuses_a_different_suite_or_configuration(tmp_path):
    out = tmp_path / "r.json"
    er.run_suite(mini_suite(tmp_path), out=out, ask=asker(), scorer=scorer_for(set()), run_info=dict(RUN_INFO), log=lambda m: None)
    with pytest.raises(ValueError):
        er.run_suite(mini_suite(tmp_path), out=out, ask=asker(), scorer=scorer_for(set()),
                     run_info={**RUN_INFO, "fingerprint": "different"}, log=lambda m: None)


def test_only_selected_tasks_run_and_unknown_ids_are_rejected(tmp_path):
    suite = mini_suite(tmp_path)
    ask = asker()
    er.run_suite(suite, out=tmp_path / "r.json", ask=ask, scorer=scorer_for(set()), run_info=dict(RUN_INFO),
                 task_ids=["A-2"], log=lambda m: None)
    assert ask.log == ["A-2"]
    with pytest.raises(ValueError):
        er.run_suite(suite, out=tmp_path / "x.json", ask=ask, scorer=scorer_for(set()), run_info=dict(RUN_INFO), task_ids=["NOPE"])


def test_runner_pauses_while_the_server_lock_exists(tmp_path):
    states = iter([True, True, False, True, False])
    probes, sleeps = [], []

    def probe():
        value = next(states, False)
        probes.append(value)
        return value

    clock = {"t": 0.0}

    def sleep(seconds):
        sleeps.append(seconds)
        clock["t"] += seconds

    ask = asker()
    result = er.run_suite(mini_suite(tmp_path), out=tmp_path / "r.json", ask=ask, scorer=scorer_for({"A-1", "A-2"}),
                          lock_probe=probe, run_info=dict(RUN_INFO), sleep=sleep, now=lambda: clock["t"], log=lambda m: None)
    assert ask.log == ["A-1", "A-2"] and len(sleeps) == 3                   # 2 sleeps before A-1, 1 before A-2
    assert result["run"]["waited_for_lock_s"] == pytest.approx(3 * er.LOCK_POLL_SECONDS)


def test_a_lock_that_never_clears_stops_the_run_with_progress_saved(tmp_path):
    clock = {"t": 0.0}

    def sleep(s):
        clock["t"] += s

    ask = asker()
    result = er.run_suite(mini_suite(tmp_path), out=tmp_path / "r.json", ask=ask, scorer=scorer_for(set()),
                          lock_probe=lambda: True, run_info=dict(RUN_INFO), sleep=sleep, now=lambda: clock["t"], log=lambda m: None)
    assert not result["complete"] and "lock" in result["run"]["stopped"] and ask.log == []


def test_a_truncated_answer_is_asked_for_again_then_recorded_as_truncated(tmp_path):
    cut = "Here:\n" + "`" * 3 + "luau\nlocal a ="
    answers = iter([cut, "complete answer"])

    def ask(task, cancel=None):
        return er.Asked(next(answers), [], 1.0)

    result = er.run_suite(mini_suite(tmp_path, [mini_task("A-1")]), out=tmp_path / "r.json", ask=ask,
                          scorer=scorer_for({"A-1"}), run_info=dict(RUN_INFO), log=lambda m: None)
    record = result["tasks"]["A-1"]
    assert record["status"] == "pass" and record["truncation_retries"] == 1 and "truncated" not in record
    always_cut = er.run_suite(mini_suite(tmp_path, [mini_task("A-1")]), out=tmp_path / "r2.json",
                              ask=lambda task, cancel=None: er.Asked(cut, [], 1.0), scorer=scorer_for(set()),
                              run_info=dict(RUN_INFO), log=lambda m: None)
    stuck = always_cut["tasks"]["A-1"]
    assert stuck["status"] == "fail" and stuck["truncated"] and stuck["truncation_retries"] == er.MAX_TRUNCATION_RETRIES


def test_a_request_is_stopped_and_repeated_when_the_lock_appears_during_it(tmp_path):
    import threading
    import time as _time
    locked = {"now": False}
    attempts = []

    def probe():
        return locked["now"]

    def ask(task, cancel):
        attempts.append(task["id"])
        if len(attempts) == 1:
            locked["now"] = True                       # someone takes the lock while this request runs
            assert cancel.wait(2), "the watcher should have cancelled the request"
            locked["now"] = False                      # ... and releases it again
            raise RuntimeError("STAR task cancelled by user")
        return er.Asked("fine", [], 1.0)

    result = er.run_suite(mini_suite(tmp_path, [mini_task("A-1")]), out=tmp_path / "r.json", ask=ask,
                          scorer=scorer_for({"A-1"}), lock_probe=probe, run_info=dict(RUN_INFO), sleep=lambda s: None,
                          log=lambda m: None, watch_interval=0.01)
    assert attempts == ["A-1", "A-1"] and result["tasks"]["A-1"]["status"] == "pass"


def test_lock_watcher_only_cancels_when_the_lock_exists():
    import threading
    cancel = threading.Event()
    with er.LockWatcher(lambda: False, cancel, interval=0.01) as quiet:
        cancel.wait(0.1)
    assert not cancel.is_set() and not quiet.fired
    with er.LockWatcher(lambda: None, cancel, interval=0.01):
        cancel.wait(0.1)
    assert not cancel.is_set()                         # an unreachable probe never cancels work
    with er.LockWatcher(lambda: True, cancel, interval=0.01) as loud:
        assert cancel.wait(1)
    assert loud.fired
    with er.LockWatcher(None, threading.Event()):       # no probe: nothing runs
        pass


def test_an_unreachable_lock_probe_does_not_block_the_run():
    assert er.wait_for_lock(lambda: None, sleep=lambda s: None, log=lambda m: None) < 1


def test_scrub_removes_private_addresses_and_secrets():
    data = {"a": "http://192.168.1.20:8080/v1 and 10.0.0.5 and 172.20.3.4", "b": ["key=SECRET123"], "c": 5, "d": "8.8.8.8"}
    clean = er.scrub(data, ["SECRET123"])
    assert "192.168" not in json.dumps(clean) and "10.0.0.5" not in json.dumps(clean) and "172.20" not in json.dumps(clean)
    assert "SECRET123" not in json.dumps(clean) and clean["c"] == 5 and clean["d"] == "8.8.8.8"


def test_rescore_updates_scores_but_refuses_a_changed_prompt(tmp_path):
    suite, out = mini_suite(tmp_path), tmp_path / "r.json"
    result = er.run_suite(suite, out=out, ask=asker(), scorer=scorer_for({"A-1"}), run_info=dict(RUN_INFO), log=lambda m: None)
    again = er.rescore(suite, json.loads(out.read_text(encoding="utf-8")), scorer_for({"A-1", "A-2"}), log=lambda m: None)
    assert again["summary"]["pass"] == 2 and "rescored_at" in again["run"]
    broken = json.loads(out.read_text(encoding="utf-8"))
    broken["tasks"]["A-1"]["prompt_sha256"] = "0" * 16
    with pytest.raises(ValueError):
        er.rescore(suite, broken, scorer_for(set()), log=lambda m: None)
    assert result["summary"]["pass"] == 1


def test_isolated_appdata_never_touches_the_real_profile_and_restores(monkeypatch):
    monkeypatch.setenv("APPDATA", "REAL-PROFILE")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    with er.isolated_appdata() as folder:
        assert os.environ["APPDATA"] == str(folder) != "REAL-PROFILE" and folder.is_dir()
    assert os.environ["APPDATA"] == "REAL-PROFILE" and "XDG_DATA_HOME" not in os.environ
    assert not folder.exists()


def test_selftest_expects_references_to_pass_and_bad_or_empty_answers_to_fail(tmp_path):
    suite = mini_suite(tmp_path)
    ref = tmp_path / "reference"
    ref.mkdir()
    (ref / "A-1.md").write_text("good", encoding="utf-8")
    (ref / "A-2.bad.md").write_text("bad", encoding="utf-8")

    def scorer(task, answer):
        return scorer_for({task["id"]} if answer == "good" else set())(task, answer)

    assert er.selftest(suite, scorer, log=lambda m: None) == 0
    (ref / "A-2.bad.md").write_text("good", encoding="utf-8")            # a bad example that passes is a problem
    assert er.selftest(suite, scorer, log=lambda m: None) == 1
    assert er.selftest(suite, lambda t, a: scorer_for({t["id"]})(t, a), log=lambda m: None) >= 2   # empty answers pass


# --- the shipped suite -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def suite():
    return er.load_suite(SUITE)


def test_shipped_suite_has_50_tasks_and_at_least_30_automated(suite):
    assert len(suite.tasks) == 50 and len({t["id"] for t in suite.tasks}) == 50
    assert len(suite.runnable()) >= 30
    v1 = json.loads((ROOT / "evals" / "roblox" / "golden-tasks-v1.json").read_text(encoding="utf-8"))
    assert len(v1) == 25 and {t["id"] for t in v1} <= {t["id"] for t in suite.tasks}


def test_every_automated_task_has_checks_a_reference_and_known_packs(suite):
    for task in suite.runnable():
        auto = task["auto"]
        assert auto.get("unit_test") or auto.get("require") or auto.get("require_any") or auto.get("citation"), task["id"]
        assert (SUITE.parent / "reference" / f"{task['id']}.md").is_file(), task["id"]
        assert set(task.get("helps", [])) <= PACKS, task["id"]
    for task in suite.tasks:
        assert task.get("studio_check") or task.get("grader"), task["id"]
        assert task["split"] in {"development", "holdout"} and task.get("expected_sources"), task["id"]


def test_new_tasks_follow_the_owner_priorities(suite):
    new = [t for t in suite.tasks if t["id"] not in {x["id"] for x in json.loads(
        (ROOT / "evals" / "roblox" / "golden-tasks-v1.json").read_text(encoding="utf-8"))}]
    assert len(new) == 25
    ui = [t for t in new if t["id"].startswith("UI-")]
    assert len(ui) == 8 and sum(1 for t in new if t["id"].startswith(("NET-1", "NET-0"))) == 10
    assert sum(1 for t in new if t["id"].startswith("ANI-")) == 4 and sum(1 for t in new if t["id"].startswith("PERF-")) == 3
    assert all(t["run_mode"] in {"automated", "studio"} for t in new)


def test_suite_files_contain_no_private_addresses_or_secrets():
    for path in (ROOT / "evals").rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md", ".luau"}:
            text = path.read_text(encoding="utf-8")
            assert not er._PRIVATE_IP.search(text), path
            assert "alexbuz" not in text, path


def test_the_self_builder_cannot_write_the_graders_the_gate_or_the_packs():
    from star.selfbuild import skill_path
    for path in ("evals/roblox/golden-tasks-v2.json", "evals/roblox/tests/NET-01.luau", "evals/roblox/prelude.luau",
                 "evals/results/baseline-v2.json", "star/eval_checks.py", "star/eval_gate.py", "star/eval_runner.py",
                 "star/eval_sandbox.py", "star/skill_packs/__init__.py", "star/skill_packs/roblox-ui-layout/SKILL.md"):
        assert not skill_path(path), path
