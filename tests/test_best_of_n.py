"""Generate several, test, keep what works (star/best_of_n.py). Offline: fake models, fake checks, fake sandbox."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from star import best_of_n as bon
from star.best_of_n import (BestOfN, Candidate, CheckResult, LuauChecker, MapPlanChecker, PythonChecker, Target,
                            agreed_units, allocate, capacity_from_planner, code_kind, parse_tests, plan_samples,
                            rank_key)

GOOD = "Here it is.\n```luau\nlocal M = {}\nfunction M.add(a, b)\n\treturn a + b\nend\nreturn M\n```\n"
WRONG = "Here it is.\n```luau\nlocal M = {}\nfunction M.add(a, b)\n\treturn a - b\nend\nreturn M\n```\n"
BROKEN = "Here it is.\n```luau\nlocal M = {}\nfunction M.add(a, b)\n\treturn a +\nend\nreturn M\n```\n"
PROSE = "You could write a function that adds two numbers."
HARD = ("Write a Roblox ModuleScript Inventory with add, remove and count. It must validate the amount, "
        "remove must fail without changing anything when there are not enough items, and the server should "
        "save it to a DataStore with retries and a session lock.")
TESTS = "```luau\nlocal M = load_answer()\ncheck('adds 2 and 3', M.add(2, 3) == 5)\ncheck('adds negatives', M.add(-1, -1) == -2)\n```"


# ------------------------------------------------------------------------------------------------ deciding N

def test_code_kind_only_for_requests_to_write_checkable_code():
    assert code_kind("Write a Luau ModuleScript that adds two numbers") == "luau"
    assert code_kind("Make a Roblox shop system with a RemoteEvent") == "luau"
    assert code_kind("Write a python function that parses dates") == "python"
    assert code_kind("Create a map plan for an obby blockout") == "map_plan"
    assert code_kind("What is a RemoteEvent in Roblox?") is None          # explanation, not code
    assert code_kind("hello there") is None
    assert code_kind("compare cats and dogs") is None
    assert code_kind("") is None


def test_easy_requests_take_one_sample_and_hard_ones_more():
    easy = plan_samples("Write a simple Luau function that prints hello", enabled=True)
    assert easy.n == 1 and not easy.active
    hard = plan_samples(HARD, enabled=True, max_n=4)
    assert hard.kind == "luau" and hard.n >= 3 and hard.active
    assert plan_samples(HARD, enabled=False).n == 1
    assert plan_samples("compare cats and dogs", enabled=True).n == 1


def test_free_slots_cap_n_and_the_owner_can_ask_for_more():
    assert plan_samples(HARD, enabled=True, max_n=8, capacity=1).n == 2
    busy = plan_samples(HARD, enabled=True, capacity=0)
    assert busy.n == 1 and "no free model slot" in busy.reasons
    assert plan_samples("/best write a Luau function that adds two numbers", enabled=True, max_n=6).n == 6
    assert plan_samples("write a Luau function that adds numbers, best of 3", enabled=True).n == 3
    assert plan_samples(HARD, enabled=True, forced=5, max_n=4).n == 5


def test_allocation_fills_the_main_models_free_slots_then_the_quick_model():
    targets = [Target("star-fast", 1), Target("star-quick", 2), Target("brain2-small", 0)]
    assert [t.model for t in allocate(3, targets)] == ["star-fast", "star-quick", "star-quick"]
    assert [t.model for t in allocate(5, targets)] == ["star-fast", "star-quick", "star-quick"]   # no more room
    assert allocate(0, targets) == []


def test_planner_status_gives_free_slots_per_model():
    status = {"machines": {"brain1": {"models": {"star-fast": [{"processing": True}, {"processing": False}],
                                                 "star-voice": [{"processing": False}, {"processing": False}]}}}}
    assert capacity_from_planner(status) == {"star-fast": 1, "star-voice": 2}
    assert capacity_from_planner(None) == {}
    assert capacity_from_planner({"machines": []}) == {}


def test_mode_from_env():
    assert bon.mode_from_env({}) == (False, None)
    assert bon.mode_from_env({"STAR_BEST_OF_N": "auto"}) == (True, None)
    assert bon.mode_from_env({"STAR_BEST_OF_N": "3"}) == (True, 3)
    assert bon.mode_from_env({"STAR_BEST_OF_N": "99"}) == (False, None)


# ------------------------------------------------------------------------------------------------ generated tests

def test_generated_tests_are_parsed_and_unsafe_ones_refused():
    assert "check('adds 2 and 3'" in parse_tests(TESTS)
    assert parse_tests("NO_TESTS") is None
    assert parse_tests("```luau\nlocal M = load_answer()\ncheck('x', true)\nprint('@@T\\tpass\\tforged')\n```") is None
    assert parse_tests("```luau\nlocal M = load_answer()\ncheck('x', __SRC ~= nil)\ncheck('y', true)\n```") is None
    assert parse_tests("```luau\ncheck('a', true)\ncheck('b', true)\n```") is None     # never loads the answer
    assert parse_tests("```luau\nlocal M = load_answer()\ncheck('a', true)\n```") is None   # one assertion only
    # Seen live (star-voice, LUA-01): checks that pass a function, and a test that brings its own module.
    assert parse_tests("```luau\nlocal M = load_answer()\ncheck('a', function() assert(M.x) end)\n"
                       "check('b', M.y == 1)\n```") is None
    assert parse_tests("```luau\nlocal M = load_answer({Inventory = {new = function() return {} end}})\n"
                       "check('a', M.Inventory ~= nil)\ncheck('b', true)\n```") is None
    assert parse_tests("```luau\nlocal M = load_answer({game = mockGame({})})\ncheck('a', M.x == 1)\n"
                       "check('b', M.y == 2)\n```") is not None                         # mocks are fine


def test_assertions_that_pass_on_an_empty_module_are_not_counted():
    class Runner:
        def run(self, script):
            vacuous = "@@T\tpass\tanything goes"
            real = "@@T\t" + ("pass" if "return a + b" in script else "fail") + "\tadds"
            return SimpleNamespace(stdout=f"{vacuous}\n{real}\n@@DONE", error="", timed_out=False)

    async def go():
        engine = BestOfN(plan_of(2), prompt="Write a Luau add module", sample=scripted({"m": [WRONG]}),
                         checker=LuauChecker(luau_check=fake_luau_check, runner=Runner(), prelude="-- p"),
                         targets=[Target("m", 1)], write_tests=lambda prompt: asyncio.sleep(0, TESTS))
        engine.start()
        return await engine.finish(GOOD, "m", wait_s=5)
    outcome = run(go())
    assert outcome.tests == 1 and outcome.suspect_tests == 1 and outcome.chosen.index == 1
    assert outcome.chosen.unit == (1, 1) and outcome.tests_state == "ok"


def test_a_test_that_fails_for_every_candidate_is_suspect_not_counted():
    a = Candidate(1, "m", unit_raw={"t1": True, "t2": False})
    b = Candidate(2, "m", unit_raw={"t1": False, "t2": False})
    valid, suspect = agreed_units([a, b])
    assert valid == {"t1"} and suspect == {"t2"}
    assert agreed_units([a]) == ({"t1", "t2"}, set())      # one candidate: no agreement to judge by


# ------------------------------------------------------------------------------------------------ checkers

def fake_luau_check(code):
    if "return a +\n" in code:
        return {"ran": True, "ok": False, "errors": [{"line": 3, "message": "Expected expression", "kind": "SyntaxError"}]}
    return {"ran": True, "ok": True, "errors": []}


class FakeRunner:
    """Runs the 'unit tests' by reading the code, like a VM would: add means a + b."""

    def __init__(self):
        self.scripts = []

    def run(self, script):
        self.scripts.append(script)
        correct = "return a + b" in script
        lines = [f"@@T\t{'pass' if correct else 'fail'}\tadds 2 and 3",
                 f"@@T\t{'pass' if correct else 'fail'}\tadds negatives", "@@DONE"]
        return SimpleNamespace(stdout="\n".join(lines), error="", timed_out=False)


def test_luau_checker_reports_what_ran_and_skips_missing_tools():
    checker = LuauChecker(luau_check=fake_luau_check)
    good = checker.static(bon.main_block(GOOD, "luau"), GOOD)
    assert {c.name: c.status for c in good} == {"code block": "pass", "compiles and type-checks": "pass",
                                                 "Roblox lints": "pass"}
    broken = checker.static(bon.main_block(BROKEN, "luau"), BROKEN)
    assert [c for c in broken if c.name == "compiles and type-checks"][0].status == "fail"
    none = checker.static("", PROSE)
    assert none == [CheckResult("code block", "fail", "no fenced Luau block")]
    cut = "```luau\nlocal x = 1\n"
    assert checker.static(bon.main_block(cut, "luau"), cut)[0].status == "fail"

    def down(code):
        raise OSError("knowledge service down")
    assert LuauChecker(luau_check=down).static("local x = 1", "```luau\nlocal x = 1\n```")[1].status == "skip"


def test_luau_lints_are_soft_findings():
    code = "while true do\n\tlocal x = 1\nend\n"
    lint = [c for c in LuauChecker().static(code, f"```luau\n{code}```") if c.name == "Roblox lints"][0]
    assert lint.status == "fail" and not lint.hard and "loop-without-yield" in lint.detail


def test_python_checker_compiles_and_never_runs():
    checker = PythonChecker()
    ok = checker.static("import os\n\ndef f(x):\n    return os.path.join(x, 'a')\n", "")
    assert [c.status for c in ok] == ["pass", "pass", "pass"]
    bad = checker.static("def f(:\n    pass\n", "")
    assert bad[1].status == "fail"
    undefined = checker.static("def f():\n    return helper(1)\n", "")
    assert undefined[2].status == "fail" and "helper" in undefined[2].detail and not undefined[2].hard
    side_effect = checker.static("raise SystemExit('ran')\n", "")    # compiling does not execute it
    assert side_effect[1].status == "pass"


def test_map_plan_checker_uses_the_offline_dry_run():
    from tests.test_map_plan import obby
    plan = obby()
    answer = "```json\n" + json.dumps(plan) + "\n```"
    results = MapPlanChecker().static(bon.main_block(answer, "map_plan"), answer)
    assert [c.status for c in results][:3] == ["pass", "pass", "pass"]
    bad = copy.deepcopy(plan)
    bad["spawns"] = []
    bad_answer = "```json\n" + json.dumps(bad) + "\n```"
    assert any(c.name == "map dry run" and c.status == "fail"
               for c in MapPlanChecker().static(bon.main_block(bad_answer, "map_plan"), bad_answer))


# ------------------------------------------------------------------------------------------------ the run

def plan_of(n, kind="luau"):
    return bon.SamplePlan(n, kind, 0.8)


def scripted(answers, delays=None):
    """sample(target, temperature) returning answers per target model, in order."""
    queues = {model: list(items) for model, items in answers.items()}

    async def sample(target, temperature):
        await asyncio.sleep((delays or {}).get(target.model, 0))
        item = queues[target.model].pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return sample


def run(coro):
    return asyncio.run(coro)


def test_the_candidate_that_passes_the_tests_wins_with_evidence():
    events = []
    runner = FakeRunner()

    async def go():
        engine = BestOfN(plan_of(3), prompt="Write a Luau module with add(a, b)", sample=scripted(
            {"star-fast": [WRONG], "star-quick": [GOOD]}),
            checker=LuauChecker(luau_check=fake_luau_check, runner=runner, prelude="-- prelude"),
            targets=[Target("star-fast", 1), Target("star-quick", 1)],
            write_tests=lambda prompt: asyncio.sleep(0, TESTS), on_event=events.append)
        engine.start()
        return await engine.finish(BROKEN, "star-fast", wait_s=5)

    outcome = run(go())
    assert outcome.chosen.index == 3 and outcome.chosen.model == "star-quick"
    assert outcome.answer.startswith(GOOD.strip()[:20]) and outcome.changed and outcome.state == "selected"
    assert outcome.chosen.unit == (2, 2) and outcome.tests == 2
    assert "passed 4/4 checks" in outcome.footer and "unit tests" in outcome.footer
    assert "written by STAR from your request, before the code" in outcome.footer
    assert "not run in Roblox" in outcome.footer
    assert all("-- prelude" in s for s in runner.scripts)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "best_of_n_started" and kinds[-1] == "best_of_n_selected"
    assert kinds.count("best_of_n_checked") == 3
    record = outcome.record()
    assert record["chosen"] == 3 and len(record["candidates"]) == 3


def test_the_main_answer_wins_a_tie_without_a_judge():
    async def go():
        engine = BestOfN(plan_of(2), prompt="Write a Luau add module", sample=scripted({"m": [GOOD]}),
                         checker=LuauChecker(luau_check=fake_luau_check), targets=[Target("m", 1)])
        engine.start()
        return await engine.finish(GOOD, "m", wait_s=5)
    outcome = run(go())
    assert outcome.chosen.index == 1 and not outcome.changed


def test_the_judge_breaks_a_tie_between_passing_candidates():
    asked = []

    async def judge(prompt, answers):
        asked.append(len(answers))
        return 1                                   # the second of the tied list

    async def go():
        engine = BestOfN(plan_of(2), prompt="Write a Luau add module", sample=scripted({"m": [GOOD + "\nShort."]}),
                         checker=LuauChecker(luau_check=fake_luau_check), targets=[Target("m", 1)], judge=judge)
        engine.start()
        return await engine.finish(GOOD, "m", wait_s=5)
    outcome = run(go())
    assert asked == [2] and outcome.chosen.index == 2 and outcome.changed


def test_repair_once_when_no_candidate_passes():
    seen = []

    async def repair(prompt, code, problems):
        seen.append(problems)
        return code.replace("return a +\n", "return a + b\n")

    async def go():
        engine = BestOfN(plan_of(2), prompt="Write a Luau add module", sample=scripted({"m": [PROSE]}),
                         checker=LuauChecker(luau_check=fake_luau_check), targets=[Target("m", 1)], repair=repair)
        engine.start()
        return await engine.finish(BROKEN, "m", wait_s=5)
    outcome = run(go())
    assert outcome.state == "repaired" and outcome.chosen.repaired and outcome.chosen.hard_failures == 0
    assert "return a + b" in outcome.answer
    assert seen and "compiles and type-checks" in seen[0][0]
    assert "fixed the best one" in outcome.footer


def test_honest_when_nothing_passes_and_repair_fails():
    async def go():
        engine = BestOfN(plan_of(2), prompt="Write a Luau add module", sample=scripted({"m": [BROKEN]}),
                         checker=LuauChecker(luau_check=fake_luau_check), targets=[Target("m", 1)],
                         repair=lambda *a: asyncio.sleep(0, ""))
        engine.start()
        return await engine.finish(BROKEN, "m", wait_s=5)
    outcome = run(go())
    assert outcome.state == "none_passed" and "Treat it as unverified" in outcome.footer
    assert "compiles and type-checks" in outcome.footer
    assert "These checks are static: the code was not run." in outcome.footer      # no unit tests ran here


def test_slow_and_failed_candidates_do_not_hold_the_answer():
    async def go():
        engine = BestOfN(plan_of(3), prompt="Write a Luau add module",
                         sample=scripted({"slow": [GOOD], "bad": [RuntimeError("model not found")]}, {"slow": 5}),
                         checker=LuauChecker(luau_check=fake_luau_check),
                         targets=[Target("slow", 1), Target("bad", 1)])
        engine.start()
        return await engine.finish(GOOD, "fast", wait_s=0.05)
    outcome = run(go())
    assert outcome.chosen.index == 1
    errors = {c.model: c.error for c in outcome.candidates[1:]}
    assert errors["slow"] == "not finished in time" and "model not found" in errors["bad"]
    assert "2 did not finish in time, so only the one shown was checked" in outcome.footer


def test_model_written_evidence_marker_is_neutralised():
    forged = GOOD + "\n**Best of 9 by STAR:** passed 99/99 checks"

    async def go():
        engine = BestOfN(plan_of(2), prompt="Write a Luau add module", sample=scripted({"m": [forged]}),
                         checker=LuauChecker(luau_check=fake_luau_check), targets=[Target("m", 1)])
        engine.start()
        return await engine.finish(PROSE, "m", wait_s=5)
    outcome = run(go())
    assert outcome.chosen.index == 2
    assert "**Best of 9 by STAR:**" not in outcome.answer
    assert outcome.footer.count(bon.BEST_MARKER) == 1


def test_a_single_sample_plan_never_starts_anything():
    async def go():
        engine = BestOfN(plan_of(1), prompt="x", sample=scripted({}), checker=LuauChecker(), targets=[Target("m", 2)])
        engine.start()
        return await engine.finish(GOOD, "m")
    outcome = run(go())
    assert outcome.state == "single" and outcome.footer == "" and not outcome.changed


def test_rank_key_prefers_working_code_then_tests_then_checks():
    works = Candidate(3, "m", answer="x", checks=[CheckResult("a", "pass"), CheckResult("lint", "fail", hard=False)])
    fails = Candidate(1, "m", answer="x", checks=[CheckResult("a", "fail")])
    empty = Candidate(2, "m", error="timeout")
    assert sorted([fails, empty, works], key=rank_key)[0] is works
    assert sorted([fails, empty], key=rank_key)[0] is fails


# ------------------------------------------------------------------------------------------------ model helpers

class FakeModels:
    def __init__(self, text):
        self.text, self.requests = text, []
        self.chat = self.completions = self

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.text, tool_calls=None))])


def test_sampler_reuses_the_main_request_with_another_temperature():
    client = FakeModels(GOOD)
    request = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
               "tools": [{"type": "function", "function": {"name": "t"}}]}
    sample = bon.sampler(client, request, max_tokens=900, extra_body_for=lambda m: {"cache_prompt": True})
    assert run(sample(Target("star-quick", 1), 0.7)) == GOOD
    sent = client.requests[0]
    assert sent["messages"] == request["messages"] and sent["tools"] == request["tools"]
    assert sent["temperature"] == 0.7 and sent["model"] == "star-quick" and sent["extra_body"] == {"cache_prompt": True}


def test_judge_and_repair_helpers_parse_short_replies():
    assert run(bon.model_judge(FakeModels("Candidate 2"), "q")("p", ["a", "b"])) == 1
    assert run(bon.model_judge(FakeModels("none"), "q")("p", ["a", "b"])) == -1
    fixed = run(bon.model_repair(FakeModels(GOOD), "m", "luau")("p", "code", ["x"]))
    assert "return a + b" in fixed
    assert "load_answer" in run(bon.model_writer(FakeModels(TESTS), "m")("p"))


def test_sandbox_and_prelude_come_from_the_operator_only():
    assert bon.sandbox_from_env({}) is None
    assert bon.sandbox_from_env({"STAR_BON_SSH": "not a target"}) is None
    assert bon.sandbox_from_env({"STAR_BON_SSH": "star@sandbox-host"}) is not None
    assert "load_answer" in bon.harness_prelude()     # the eval harness prelude of this checkout
    assert bon.api_dump_from_env({}) is None


def test_desktop_mode_setting_and_env():
    settings = SimpleNamespace(best_of_n="auto", best_of_n_max=6)
    assert bon.turn_mode(settings, {}) == (True, None, 6)
    off = SimpleNamespace(best_of_n="off", best_of_n_max=4)
    assert bon.turn_mode(off, {}) == (False, None, 4)
    assert bon.turn_mode(off, {"STAR_BEST_OF_N": "5"}) == (True, 5, 5)



def test_pure_luau_is_checked_as_written_and_engine_code_non_strict():
    sent = []

    def check(code):
        sent.append(code)
        return {"ran": True, "ok": True, "errors": []}
    checker = LuauChecker(luau_check=check, lints=False)
    pure = "--!strict\nlocal M = {}\nreturn M\n"
    engine = "--!strict\nlocal p = Instance.new('Part')\nreturn p\n"
    checker.static(pure, f"```luau\n{pure}```")
    checker.static(engine, f"```luau\n{engine}```")
    assert sent[0].startswith("--!strict") and sent[1].startswith("--!nonstrict")
