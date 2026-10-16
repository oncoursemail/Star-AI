"""Offline tests for star.agent_fleet using throwaway git repos and python subprocesses."""
import subprocess
import sys
import threading
import time

import pytest

from star import agent_fleet as fl

PY = sys.executable
RES = {"ram_total_mib": 32000, "ram_free_mib": 20000, "cpu_busy": 0.1, "cpus": 16}


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "a.txt").write_text("base\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "init")
    return r


def writer(text):
    return [PY, "-c", f"open('a.txt','a').write({text!r})"]


PASS = [PY, "-c", "import sys; sys.exit(0)"]
FAIL = [PY, "-c", "import sys; sys.exit(1)"]


def test_plan_slots_honest_states():
    assert fl.plan_slots({**RES, "ram_free_mib": None})[0] == 0
    assert "waiting" in fl.plan_slots({**RES, "cpu_busy": 0.95})[1]
    assert fl.plan_slots({**RES, "ram_free_mib": 5000})[0] == 0
    assert fl.plan_slots(RES)[0] == 4
    assert fl.plan_slots(RES, cap=2)[0] == 2


def test_live_sample_has_expected_keys():
    assert set(fl.sample_resources(0.05)) == {"ram_total_mib", "ram_free_mib", "cpu_busy", "cpus"}


def test_off_by_default(repo, monkeypatch):
    monkeypatch.delenv("STAR_AGENT_FLEET", raising=False)
    r = fl.run_fleet(repo, [fl.FleetTask("t1", writer("x"), PASS)], resources=RES)
    assert r.slots == 0 and r.receipts == [] and "disabled" in r.reason


def test_protected_refused(tmp_path):
    p = tmp_path / "Paintball"
    p.mkdir()
    assert "protected" in fl.run_fleet(p, [], enabled=True, resources=RES).reason


def test_only_passing_task_is_proposed_and_nothing_merged(repo, tmp_path):
    tasks = [fl.FleetTask("good", writer("g"), PASS), fl.FleetTask("bad", writer("b"), FAIL),
             fl.FleetTask("noop", PASS, PASS), fl.FleetTask("crash", FAIL, PASS),
             fl.FleetTask("off", writer("o"), PASS, enabled=False)]
    r = fl.run_fleet(repo, tasks, enabled=True, resources=RES, worktrees=tmp_path / "wts")
    st = {x.task_id: x.status for x in r.receipts}
    assert st == {"good": "proposed", "bad": "tests_failed", "noop": "no_changes", "crash": "agent_failed",
                  "off": "disabled"}
    assert "a.txt" in r.receipts[0].diffstat
    assert (repo / "a.txt").read_text() == "base\n"
    count = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", "main"], capture_output=True, text=True)
    assert count.stdout.strip() == "1"


def test_no_test_command_is_never_a_pass(repo, tmp_path):
    r = fl.run_fleet(repo, [fl.FleetTask("t", writer("x"), [])], enabled=True, resources=RES,
                     worktrees=tmp_path / "w")
    assert r.receipts[0].status == "error"


def test_cancel_during_test_run(repo, tmp_path):
    cancel = threading.Event()
    slow = [PY, "-c", "import time; time.sleep(30)"]
    threading.Timer(2.0, cancel.set).start()
    t0 = time.monotonic()
    r = fl.run_fleet(repo, [fl.FleetTask("t", writer("x"), slow)], enabled=True, resources=RES,
                     worktrees=tmp_path / "w", cancel=cancel)
    assert r.receipts[0].status == "cancelled" and time.monotonic() - t0 < 20


def test_three_agents_edit_same_file_without_conflict(repo, tmp_path):
    tasks = [fl.FleetTask(f"w{i}", writer(f"line{i}\n"), PASS) for i in range(3)]
    r = fl.run_fleet(repo, tasks, enabled=True, resources=RES, worktrees=tmp_path / "w")
    assert [x.status for x in r.receipts] == ["proposed"] * 3
