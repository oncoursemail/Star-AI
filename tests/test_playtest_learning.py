import asyncio
import contextlib
import json
import re
from pathlib import Path

import pytest

from star import playtest_learning as pl
from star.studio_loop import EDIT_MARK, ChangeJournal
from star.worked_examples import validate_row

SPECS = pl.SPECS_DIR


def spec(**extra):
    base = {"name": "DoorTest", "kind": "door", "brief": "A door puzzle.", "contract": ["The door is a Part named Door."],
            "checks": [{"do": "blocked", "target": "Goal"}, {"do": "touch", "target": "Button"},
                       {"do": "reach", "target": "Goal"}], "playSeconds": 60}
    checked, problems = pl.check_spec({**base, **extra})
    assert checked is not None, problems
    return checked


def answer(body: str, lesson: str = "") -> str:
    return f"Here is the game.\n```lua\n-- Script: Game\n{body}\n```\n" + (f"LESSON: {lesson}\n" if lesson else "")


def test_shipped_specs_are_valid_and_cover_the_game_kinds():
    specs, bad = pl.load_specs(SPECS)
    assert not bad and len(specs) >= 10
    assert {s["kind"] for s in specs} >= {"obby", "coins", "shop", "timer", "door"}
    assert len({s["name"] for s in specs}) == len(specs)


def test_check_spec_refuses_unknown_checks_and_keys():
    bad, problems = pl.check_spec({"name": "X", "kind": "k", "brief": "b", "contract": ["c"],
                                   "checks": [{"do": "teleport"}], "extra": 1})
    assert bad is None and any("unknown 'do'" in p for p in problems) and any("unknown keys" in p for p in problems)


def test_parse_answer_reads_scripts_lesson_and_forbidden_apis():
    text = ("<think>plan</think>```lua\n-- Script: Build\nlocal p = Instance.new('Part')\n```\n"
            "```luau\n-- Script: Logic\nlocal h = game:GetService('HttpService')\n```\nLESSON: Debounce touch events per player.")
    parsed = pl.parse_answer(text)
    assert [s["name"] for s in parsed["scripts"]] == ["Build", "Logic"]
    assert parsed["lesson"] == "Debounce touch events per player."
    assert parsed["problems"] == ["script Logic uses HttpService, which is not allowed in the playtest"]
    assert pl.parse_answer("no code")["problems"] == ["the answer has no ```lua code block"]
    headerless = pl.parse_answer("```lua\nprint(1)\n```")
    assert headerless["scripts"][0]["name"] == "Game1" and not headerless["problems"]
    cut = pl.parse_answer('```lua\n-- Script: Build\nlocal floor = Instance.new("Part", workspace)')
    assert cut["scripts"][0]["source"].endswith("workspace)\n") and not cut["problems"]


def test_apply_luau_stores_sources_as_strings_and_configures_the_robot():
    scripts = [{"name": "Game", "source": 'print("hi")\nlocal s = "]]"\n'}]
    code = pl.apply_luau(spec(), scripts, "abcd1234ef")
    assert 's.Source = "print(\\"hi\\")\\nlocal s = \\"]]\\"\\n"' in code
    config = json.loads(json.loads(re.search(r'robot:SetAttribute\("StarPlayConfig", (".*")\)', code).group(1)))
    assert config["run"] == "abcd1234ef" and [s["do"] for s in config["steps"]] == ["blocked", "touch", "reach"]
    assert "tests:ClearAllChildren()" in code and 'SetAttribute("StarPlayPaused", true)' in code
    assert 'item:SetAttribute("StarPlayPaused", nil)' in pl.remove_luau()
    with pytest.raises(ValueError):
        pl.apply_luau(spec(), scripts, "not-a-token")
    with pytest.raises(ValueError):
        pl.apply_luau(spec(), [{"name": "bad name", "source": ""}], "abcd1234ef")


def line(run, **data):
    return pl.MARK + json.dumps({"run": run, **data})


def test_parse_robot_errors_and_judge():
    run = "feed0001aa"
    console = "\n".join([
        "old output: Error from an earlier session", line("other", kind="start"), line(run, kind="start"),
        line(run, kind="check", index=0, ok=True, why=""),
        line(run, kind="check", index=1, ok=False, **{"do": "blocked"},
             why="the robot reached 'Goal' although it should still be blocked",
             facts={"reason": "timeout", "stuck": [{"at": [1, 2, 3]}]}),
        "Workspace.MapDrafts.Playtest.DoorTest.Game:12: attempt to index nil with 'Touched'",
        "Workspace.Other.Script:3: attempt to call a nil value",
        line(run, kind="done", ok=False)])
    robot = pl.parse_robot(console, run)
    assert robot["started"] and robot["finished"] and not robot["ok"] and len(robot["checks"]) == 2
    errors = pl.output_errors(console, run, "DoorTest")
    assert len(errors["game"]) == 1 and len(errors["other"]) == 1 and not errors["robot"]
    report = pl.judge(robot, errors, [])
    assert not report["passed"] and [f["code"] for f in report["failures"]] == ["blocked", "script-error"]
    text = pl.describe(report)
    assert "should still be blocked" in text and "attempt to index nil" in text and "1 other check(s) passed" in text


class Verdict:
    identity = type("I", (), {"place_id": 128074805767678, "game_id": 10770312935})()
    editable = True


class FakeStudio:
    """The GuardedStudio interface. 'Plays' the game: a script containing BUG fails the door check, else passes."""

    def __init__(self, robot_error=False):
        self.studio_id, self.verdict, self.journal = "s1", Verdict(), ChangeJournal()
        self.console, self.calls, self.scripts, self.run, self.robot_error = "", [], {}, None, robot_error

    def _receipt(self, result):
        tag = f"StarEdit_{len(self.journal.entries):08x}"
        self.journal.entries.append({"kind": "luau", "tag": tag, "known": True, "ok": True})
        receipt = {"tag": tag, "ok": True, "recorded": True, "connectorRecorded": False, "added": [], "addedCount": 1,
                   "removed": 0, "result": result}
        return {"content": [{"type": "text", "text": EDIT_MARK + json.dumps(receipt)}]}

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "execute_luau":
            code = arguments["code"]
            if "STAR playtest apply" in code:
                self.run = re.search(r'root:SetAttribute\("StarPlayRun", "([0-9a-f]+)"\)', code).group(1)
                self.scripts = {m.group(1): json.loads(m.group(2)) for m in
                                re.finditer(r's.Name = "([A-Za-z0-9_]+)"\n\ts.Source = (".*")', code)}
                return self._receipt(pl.APPLY_MARK + json.dumps({"run": self.run, "scripts": len(self.scripts)}))
            if "STAR playtest cleanup" in code:
                return self._receipt(pl.APPLY_MARK + json.dumps({"removed": 1}))
            raise AssertionError(code[:80])
        if name == "start_stop_play":
            if arguments["is_start"]:
                buggy = any("BUG" in s for s in self.scripts.values())
                checks = [line(self.run, kind="start"), line(self.run, kind="check", index=0, **{"do": "spawn"}, ok=True, why="")]
                if self.robot_error:
                    checks.append(line(self.run, kind="check", index=1, **{"do": "blocked"}, ok=False, robot_error=True,
                                       why="attempt to index nil"))
                else:
                    checks.append(line(self.run, kind="check", index=1, **{"do": "blocked"}, ok=not buggy,
                                       why="the robot reached 'Goal' although it should still be blocked" if buggy else ""))
                    checks += [line(self.run, kind="check", index=i, **{"do": d}, ok=True, why="")
                               for i, d in ((2, "touch"), (3, "reach"))]
                checks.append(line(self.run, kind="done", ok=not buggy and not self.robot_error))
                self.console += "\n".join(checks) + "\n"
            return {"content": [{"type": "text", "text": "ok"}]}
        if name == "get_console_output":
            return {"content": [{"type": "text", "text": self.console}]}
        raise AssertionError(name)


class FakeBrain:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, messages):
        self.calls.append(messages)
        return {"ok": True, "text": self.answers.pop(0), "seconds": 1.0, "tokens": 50, "model": "fake"}


async def no_sleep(_):
    return None


def opener(studio):
    @contextlib.asynccontextmanager
    async def open_guarded():
        yield studio, {"verified": True}
    return open_guarded


def test_loop_fixes_a_failed_game_and_feeds_night_school(tmp_path):
    studio = FakeStudio()
    brain = FakeBrain([answer("-- BUG: door starts open\nprint(1)"),
                       answer("print('door closed until the button')", "Keep a door closed until its trigger fires.")])
    suite = asyncio.run(pl.run_suite([spec()], opener(studio), brain, tmp_path / "out", log=lambda *_: None,
                                     run_kwargs={"sleep": no_sleep, "poll": 0}))
    report = suite["reports"][0]
    assert report["passed"] and not report["first_pass"] and len(report["iterations"]) == 2
    first, second = report["iterations"]
    assert [f["code"] for f in first["report"]["failures"]] == ["blocked"] and second["report"]["passed"]
    fix_task = brain.calls[1][-1]["content"]
    assert "should still be blocked" in fix_task and "LESSON:" in fix_task and brain.calls[1][-2]["role"] == "assistant"
    assert studio.calls.count("start_stop_play") == 4 and report["cleanup"]["ok"]
    assert studio.calls.count("execute_luau") == 4          # cleanup first, 2 builds, cleanup after
    assert suite["summary"]["fix_rate"] == 1.0 and suite["summary"]["fixed"] == 1 and suite["summary"]["playtests"] == 2
    assert report["lesson"]["text"] == "Keep a door closed until its trigger fires."
    outbox = tmp_path / "outbox"
    written = pl.write_outbox(outbox, suite["reports"])
    assert written == {"examples": 1, "lessons": 1}
    rows = [json.loads(x) for x in (outbox / "worked-examples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and validate_row(rows[0]).group_id == "playtest-DoorTest"
    assert "after a failed first playtest" in rows[0]["evidence"][0]
    lessons = json.loads((outbox / "star-lessons-playtest.json").read_text(encoding="utf-8"))
    assert "CANDIDATE" in lessons["note"]
    assert (tmp_path / "out" / "suite.json").is_file()


def test_first_pass_is_an_example_without_a_lesson(tmp_path):
    report = asyncio.run(pl.GameRun(FakeStudio(), FakeBrain([answer("print('ok')")]), tmp_path, log=lambda *_: None,
                                    sleep=no_sleep, poll=0).run(spec()))
    assert report["first_pass"] and report["lesson"] is None and pl.worked_example(report)["evidence"][0].endswith("first try)")


def test_forbidden_api_is_a_fix_task_without_a_playtest(tmp_path):
    studio = FakeStudio()
    brain = FakeBrain([answer("local h = game:GetService('DataStoreService')"), answer("print('fine')", "No DataStores.")])
    report = asyncio.run(pl.GameRun(studio, brain, tmp_path, log=lambda *_: None, sleep=no_sleep, poll=0).run(spec()))
    assert report["passed"] and report["iterations"][0]["playtest"] is None
    assert report["iterations"][0]["report"]["failures"][0]["code"] == "static"
    assert studio.calls.count("start_stop_play") == 2


def test_robot_error_is_not_sent_to_star(tmp_path):
    brain = FakeBrain([answer("print('ok')")])
    report = asyncio.run(pl.GameRun(FakeStudio(robot_error=True), brain, tmp_path, log=lambda *_: None,
                                    sleep=no_sleep, poll=0).run(spec()))
    assert not report["passed"] and len(report["iterations"]) == 1 and len(brain.calls) == 1
    assert pl.summarize([report], 1.0)["fix_rate"] is None


def test_switch_off_refuses_to_run(monkeypatch, capsys):
    monkeypatch.delenv(pl.SWITCH, raising=False)
    assert pl.main(["run", str(SPECS), "--out", "x", "--home", "y"]) == 3
    assert "switched off" in capsys.readouterr().out
    assert pl.main(["check", str(SPECS)]) == 0


def test_brain_never_reports_url_or_key(tmp_path):
    key = tmp_path / "key"
    key.write_text("secret-key-123\n", encoding="utf-8")

    def broken(request, timeout):
        assert request.headers["Authorization"] == "Bearer secret-key-123"
        raise OSError("http://brain.invalid:8080 refused")
    result = pl.Brain("http://brain.invalid:8080", key_file=str(key), opener=broken)([{"role": "user", "content": "x"}])
    assert result == {"ok": False, "text": "", "error": "OSError", "seconds": result["seconds"]}


def test_luau_strings_escape_non_ascii_and_control_characters():
    # JSON's ’ is a Luau compile error; a curly quote in STAR's answer broke a live apply.
    assert pl._lua_string("it’s \\ \"x\"\n\t\x01") == r'"it\u{2019}s \\ \"x\"\n\t\001"'
    assert pl._lua_string("\U0001F600").isascii()


def test_apply_retries_when_studio_cannot_say_which_place_is_open(tmp_path):
    class Flaky(FakeStudio):
        refusals = 1

        async def call_tool(self, name, arguments):
            if name == "execute_luau" and "STAR playtest apply" in arguments["code"] and self.refusals:
                self.refusals -= 1
                return {"isError": True, "content": [{"type": "text", "text": "Edit refused: STAR could not confirm "
                                                      "which place is open right now, so nothing was changed"}]}
            return await super().call_tool(name, arguments)
    report = asyncio.run(pl.GameRun(Flaky(), FakeBrain([answer("print('ok')")]), tmp_path, log=lambda *_: None,
                                    sleep=no_sleep, poll=0).run(spec()))
    assert report["passed"] and not report.get("studio_problem")
