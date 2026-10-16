"""Offline tests for the open Roblox benchmark (fake Studio, fake brain; no Luau runs here)."""
import asyncio
import contextlib
import json
import re

import pytest

from star import roblox_benchmark as rb
from star.studio_loop import EDIT_MARK, ChangeJournal


def test_tasks_load_and_cover_three_levels():
    tasks = rb.load_tasks()
    assert len(tasks) == 20
    assert {t["level"] for t in tasks} == {"easy", "medium", "hard"}
    assert len({t["id"] for t in tasks}) == 20
    for task in tasks:
        source = rb.check_source(task)
        assert source.count('say("done"') == 1 and "pcall(function()" in source
        assert "check(" in task["check"]


@pytest.mark.parametrize("task", rb.load_tasks(), ids=lambda t: t["id"])
def test_reference_answers_parse_without_problems(task):
    scripts, problems = rb.scripts_for(task, "```lua\n" + task["reference"] + "```")
    assert problems == [] and scripts
    if task["kind"] == "module":
        assert [(s["name"], s["class"]) for s in scripts] == [("Solution", "ModuleScript")]
        assert "return" in scripts[0]["source"]
    else:
        assert all(s["class"] == "Script" for s in scripts)
    # The offline API checker finds nothing doubtful in the known-good answers.
    assert rb.api_findings(scripts) == []


def test_malformed_task_is_refused(tmp_path):
    (tmp_path / "E01-x.json").write_text(json.dumps({"id": "E01-x", "level": "easy", "kind": "module",
                                                     "prompt": "short", "playSeconds": 30}), encoding="utf-8")
    with pytest.raises(ValueError):
        rb.load_tasks(tmp_path)


def test_forbidden_api_and_missing_code_are_static_failures():
    task = {"kind": "script"}
    scripts, problems = rb.scripts_for(task, "```lua\nlocal h = game:GetService('HttpService')\n```")
    assert scripts and any("HttpService" in p for p in problems)
    assert rb.scripts_for(task, "no code here")[1]


def test_apply_luau_stores_answer_and_check_and_refuses_bad_ids():
    task = rb.load_tasks(only={"E01-format-time"})[0]
    code = rb.apply_luau(task, [{"name": "Solution", "class": "ModuleScript", "source": "return {}"}], "abcdef012345")
    assert 'Instance.new("ModuleScript")' in code and '"StarBenchCheck"' in code
    assert 'x:SetAttribute("StarBenchRun", "abcdef012345")' in code and "bench:ClearAllChildren()" in code
    with pytest.raises(ValueError):
        rb.apply_luau(task, [], "not-hex")
    with pytest.raises(ValueError):
        rb.apply_luau({**task, "id": "bad id"}, [], "abcdef012345")


def line(run, **data):
    return rb.MARK + json.dumps({"run": run, **data})


def test_parse_and_judge():
    console = "\n".join([line("r1", kind="start"), line("other", kind="done", checks=[]),
                         "Workspace.MapDrafts.Bench.E01-x.Solution:3: attempt to index nil",
                         line("r1", kind="done", checks=[{"name": "a", "ok": True}, {"name": "b", "ok": False, "why": "no"}])])
    parsed = rb.parse_console(console, "r1")
    assert parsed["started"] and parsed["finished"] and len(parsed["checks"]) == 2
    verdict = rb.judge(parsed, [], [])
    assert not verdict["passed"] and verdict["checks_passed"] == 1 and verdict["why"] == ["b: no"]
    assert rb.answer_errors(console, "r1", "E01-x") == ["Workspace.MapDrafts.Bench.E01-x.Solution:3: attempt to index nil"]
    ok = rb.parse_console(line("r2", kind="start") + "\n" + line("r2", kind="done", checks=[{"name": "a", "ok": True}]), "r2")
    assert rb.judge(ok, [], [])["passed"]
    assert not rb.judge(ok, ["E01 error"], [])["passed"]
    assert rb.judge(rb.parse_console("", "r3"), [], [])["why"] == ["the check never started"]
    hung = rb.parse_console(line("r4", kind="start") + "\n" + line("r4", kind="check", name="a", ok=True, why=""), "r4")
    verdict = rb.judge(hung, [], [])
    assert not hung["finished"] and verdict["checks_passed"] == 1 and verdict["why"] == ["the check did not finish in time"]
    assert "check(\"setup\"" in rb.check_source(rb.load_tasks(only={"E01-format-time"})[0])


class Verdict:
    editable = True


class FakeStudio:
    """GuardedStudio stand-in: a playtest passes every check unless the stored answer contains BUG."""

    def __init__(self):
        self.studio_id, self.verdict, self.journal = "s1", Verdict(), ChangeJournal()
        self.console, self.calls, self.run, self.buggy, self.fail_starts = "", [], None, False, 0

    def _receipt(self, result):
        self.journal.entries.append({"kind": "luau", "ok": True})
        return {"content": [{"type": "text", "text": EDIT_MARK + json.dumps({"ok": True, "result": result})}]}

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "execute_luau":
            code = arguments["code"]
            if "STAR benchmark apply" in code:
                self.run = re.search(r'"StarBenchRun", "([0-9a-f]+)"', code).group(1)
                self.buggy = "BUG" in code
                return self._receipt(rb.APPLY_MARK + json.dumps({"run": self.run, "scripts": 1}))
            if "STAR benchmark cleanup" in code:
                return self._receipt(rb.APPLY_MARK + json.dumps({"removed": 1}))
            raise AssertionError(code[:80])
        if name == "start_stop_play":
            if arguments["is_start"] and self.fail_starts:
                self.fail_starts -= 1
                return {"isError": True, "content": [{"type": "text", "text": "no Playing state"}]}
            if arguments["is_start"]:
                self.console += line(self.run, kind="start") + "\n" + line(
                    self.run, kind="done", checks=[{"name": "c", "ok": not self.buggy, "why": "wrong" if self.buggy else ""}]) + "\n"
            return {"content": [{"type": "text", "text": "ok"}]}
        if name == "get_console_output":
            return {"content": [{"type": "text", "text": self.console}]}
        raise AssertionError(name)


def opener(studio):
    @contextlib.asynccontextmanager
    async def open_guarded():
        yield studio, {"verified": True}
    return open_guarded


async def no_sleep(_):
    return None


def test_answers_are_asked_once_and_scored_in_fake_studio(tmp_path):
    tasks = rb.load_tasks(only={"E01-format-time", "H02-priority-queue"})
    calls = []

    def brain_for(model):
        def brain(messages):
            calls.append((model, messages[-1]["content"][:30]))
            body = "return {} -- BUG" if model == "m2" else "return {}"
            return {"ok": True, "text": f"```lua\n{body}\n```", "seconds": 2.0, "tokens": 10}
        return brain

    answers = tmp_path / "answers"
    rb.collect_answers(tasks, ["m1", "m2", rb.REFERENCE], answers, brain_for=brain_for, log=lambda *_: None)
    rb.collect_answers(tasks, ["m1", "m2"], answers, brain_for=brain_for, log=lambda *_: None)
    assert len(calls) == 4 and (answers / "m1" / "E01-format-time.txt").is_file()
    assert calls[0][1].startswith("Module task:")

    studio = FakeStudio()
    result = asyncio.run(rb.run_bench(tasks, ["m1", "m2", rb.REFERENCE, "missing"], answers, opener(studio),
                                      tmp_path / "out", log=lambda *_: None, bench_kwargs={"sleep": no_sleep, "poll": 0}))
    summary = result["summary"]
    assert result["ok"] and summary["m1"]["passed"] == 2 and summary["m1"]["score"] == 4
    assert summary["m2"]["passed"] == 0 and summary[rb.REFERENCE]["passed"] == 2
    assert summary["missing"]["passed"] == 0 and summary["m1"]["median_brain_seconds"] == 2.0
    assert studio.calls.count("start_stop_play") == 13     # 1 safety stop + 6 playtests (missing answers not played)
    md = (tmp_path / "out" / "results.md").read_text(encoding="utf-8")
    assert "| m1 | 2/2 | 4/4 |" in md and "| H02-priority-queue | pass | fail 0/1 | pass | fail 0/0 |" in md


def test_no_studio_is_a_clean_refusal(tmp_path):
    @contextlib.asynccontextmanager
    async def none():
        yield None, {"problem": "Studio signed out"}
    result = asyncio.run(rb.run_bench(rb.load_tasks(only={"E01-format-time"}), ["m"], tmp_path, none, tmp_path / "o"))
    assert result == {"ok": False, "problem": "Studio signed out"}


def test_studio_failures_are_retried_and_then_reported(tmp_path):
    tasks = rb.load_tasks(only={"E01-format-time", "E02-make-part"})
    studio = FakeStudio()
    kwargs = {"sleep": no_sleep, "poll": 0, "retry_wait": 0}

    def bench(folder):
        return asyncio.run(rb.run_bench(tasks, [rb.REFERENCE], tmp_path, opener(studio), tmp_path / folder,
                                        log=lambda *_: None, bench_kwargs=kwargs, reopen_wait=0))
    studio.fail_starts = 1          # one missed start: retried in place
    result = bench("a")
    assert result["ok"] and result["summary"][rb.REFERENCE]["passed"] == 2
    studio.fail_starts = 2          # both tries fail: the session is reopened and the task played again
    result = bench("b")
    assert result["ok"] and result["summary"][rb.REFERENCE]["passed"] == 2
    studio.fail_starts = 99         # Studio never plays: every task is reported as not run
    result = bench("c")
    assert not result["ok"] and len(result["rows"]) == 2 and all(r["studio_problem"] for r in result["rows"])


def test_endpoints_file_makes_any_openai_compatible_contestant(tmp_path):
    path = tmp_path / "endpoints.json"
    path.write_text(json.dumps({"other-ai": {"url": "http://127.0.0.1:9", "model": "m-1",
                                             "key_file": str(tmp_path / "nokey")}}), encoding="utf-8")
    brain_for = rb.brain_factory(rb.load_endpoints(path))
    other, star = brain_for("other-ai"), brain_for("star-fast")
    assert (other.url, other.model) == ("http://127.0.0.1:9", "m-1") and star.model == "star-fast"
    assert star.extra == {} and rb.brain_factory({}, rb.NO_THINK)("star-deep").extra == rb.NO_THINK
    path.write_text(json.dumps({"x": {"model": "m"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        rb.load_endpoints(path)
