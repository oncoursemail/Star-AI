"""Studio stuck in Play after a playtest stop: the display fallback (all with fakes, no Studio, no xdotool)."""
import asyncio

from star import playtest_learning as pl
from star import studio_lab_parallel as parallel
from star import studio_play_fallback as fb
from tests.test_playtest_learning import FakeBrain, FakeStudio, answer, no_sleep, spec


class Clock:
    """A fake clock: sleeping advances it, so the waits run instantly."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


def make(states, *, on_press=None):
    """states: the modes the state call returns in turn (the last one repeats)."""
    clock, log, calls = Clock(), [], {"state": 0, "stops": 0, "presses": 0}

    async def get_state():
        index = min(calls["state"], len(states) - 1)
        calls["state"] += 1
        return states[index]

    async def request_stop():
        calls["stops"] += 1

    def press_stop():
        calls["presses"] += 1
        if on_press:
            on_press()
        return {"ok": True}
    guard = fb.PlayGuard(get_state, request_stop=request_stop, press_stop=press_stop, sleep=clock.sleep, clock=clock,
                         wait=4.0, poll=1.0, log=log.append)
    return guard, calls, log


def test_already_in_edit_presses_nothing():
    guard, calls, _ = make(["Edit"])
    assert asyncio.run(guard.ensure_edit(send_stop=True)) == {"edit": True, "method": "edit", "seconds": 0.0}
    assert calls["stops"] == 0 and calls["presses"] == 0


def test_connector_stop_that_lands_a_little_late_needs_no_key_press():
    guard, calls, _ = make(["Playing", "Playing", "Playing", "Edit"])
    result = asyncio.run(guard.ensure_edit(send_stop=True))
    assert result["edit"] is True and result["method"] == "connector" and calls["stops"] == 1 and calls["presses"] == 0


def test_stuck_in_play_is_fixed_by_pressing_stop_on_the_display():
    # The live case: the stop said "Game Stopped" and Studio stayed in Play until Stop was pressed on the display.
    state = ["Playing"]

    async def get_state():
        return state[0]
    clock, log = Clock(), []
    guard = fb.PlayGuard(get_state, press_stop=lambda: state.__setitem__(0, "Edit") or {"ok": True}, sleep=clock.sleep,
                         clock=clock, wait=4.0, poll=1.0, log=log.append)
    result = asyncio.run(guard.ensure_edit())
    assert result["edit"] is True and result["method"] == "display" and result["display"] == {"ok": True}
    assert any("pressing Stop on the display" in line for line in log)


def test_still_in_play_after_the_key_press_is_reported_not_hung():
    guard, calls, log = make(["Playing"])
    result = asyncio.run(guard.ensure_edit(send_stop=True))
    assert result["edit"] is False and result["method"] == "stuck" and calls["presses"] == 1
    assert any("STUCK IN PLAY" in line for line in log)


def test_unknown_state_never_sends_a_key():
    guard, calls, _ = make([None])
    assert asyncio.run(guard.ensure_edit(send_stop=True))["edit"] is None
    assert calls["presses"] == 0 and calls["stops"] == 0

    async def broken():
        raise RuntimeError("connector gone")
    assert asyncio.run(fb.PlayGuard(broken, press_stop=lambda: 1 / 0).ensure_edit())["edit"] is None


def test_display_stop_runs_xdotool_search_activate_key():
    seen = []

    def run(command, **kwargs):
        seen.append((command, kwargs["env"]["DISPLAY"]))
        return type("R", (), {"stdout": "123\n456\n" if command[1] == "search" else "", "stderr": "", "returncode": 0})()
    result = fb.display_stop(run=run, which=lambda _: "/usr/bin/xdotool", pause=lambda _: None, display=":7")
    assert result["ok"] and result["window"] == "123" and result["key"] == "shift+F5"
    assert [c[0][1] for c in seen] == ["search", "windowactivate", "key"] and {c[1] for c in seen} == {":7"}
    assert seen[-1][0][-1] == "shift+F5"
    assert fb.display_stop(which=lambda _: None)["ok"] is False

    def empty(*args, **kwargs):
        return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()
    assert fb.display_stop(run=empty, which=lambda _: "x", pause=lambda _: None)["detail"].startswith("no Studio window")


def test_playtest_reports_a_stuck_stop_and_logs_how_long_play_took_to_start(tmp_path):
    studio = FakeStudio()
    clock = Clock()

    async def stuck():
        return "Playing"
    studio.play_guard = fb.PlayGuard(stuck, press_stop=lambda: {"ok": True}, sleep=clock.sleep, clock=clock, wait=2.0,
                                     poll=1.0, log=lambda *_: None)
    lines = []
    report = asyncio.run(pl.GameRun(studio, FakeBrain([answer("print('ok')")]), tmp_path, log=lines.append,
                                    sleep=no_sleep, poll=0).run(spec()))
    step = report["iterations"][0]
    assert report["studio_problem"] and step["playtest"]["stopped"] is False
    assert step["playtest"]["edit"]["edit"] is False
    assert step["playtest"]["start_s"] is not None
    assert any(line.startswith("play start: Studio confirmed in") for line in lines)
    assert any(f["code"] == "studio" for f in step["report"]["failures"])


def test_playtest_is_unchanged_when_the_stop_really_leaves_play(tmp_path):
    studio = FakeStudio()

    async def edit():
        return "Edit"
    studio.play_guard = fb.PlayGuard(edit)
    report = asyncio.run(pl.GameRun(studio, FakeBrain([answer("print('ok')")]), tmp_path, log=lambda *_: None,
                                    sleep=no_sleep, poll=0).run(spec()))
    assert not report.get("studio_problem") and report["iterations"][0]["playtest"]["edit"]["method"] == "edit"


class PlaySession:
    """A raw connector session whose Studio is (and stays) in the given mode."""

    def __init__(self, mode):
        self.mode, self.calls = mode, []

    async def call_tool(self, name, arguments=None):
        self.calls.append(name)
        if name == "get_studio_state":
            return {"content": [{"type": "text", "text": f"- Current Studio Mode: {self.mode}\n- Available DataModels: Edit"}]}
        return {"content": [{"type": "text", "text": "Game Stopped"}]}


def test_open_instance_skips_a_studio_that_stays_in_play(monkeypatch):
    monkeypatch.setattr(fb, "WAIT_SECONDS", 0.0)
    monkeypatch.setattr(fb, "display_stop", lambda: {"ok": True})
    session = PlaySession("Play")
    guarded, facts = asyncio.run(parallel.open_instance(session, [], "s1", home="."))
    assert guarded is None and facts["verified"] is False and "stuck in Play" in facts["problem"]
    assert facts["play_guard"]["method"] == "stuck" and session.calls.count("start_stop_play") == 1


def test_leave_edit_mode_records_a_studio_that_stays_in_play(monkeypatch):
    monkeypatch.setattr(fb, "WAIT_SECONDS", 0.0)
    monkeypatch.setattr(fb, "display_stop", lambda: {"ok": True})
    facts = {}
    asyncio.run(pl.leave_edit_mode(PlaySession("Play"), "s1", facts))
    assert facts["left_play_mode"]["method"] == "stuck"
    facts = {}
    asyncio.run(pl.leave_edit_mode(PlaySession("Edit"), "s1", facts))
    assert facts == {}
