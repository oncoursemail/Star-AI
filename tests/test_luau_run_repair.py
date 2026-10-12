"""Real finalization and ten standalone scripted practice checks (not a real Luau VM).

The fake VM maps known-wrong and known-correct Luau modules to deterministic
verdicts; it is intentionally not represented as Luau execution evidence.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from star import doc_grounding, doc_knowledge, luau_run_repair
from star.desktop_core import Settings
from star.luau_run_review import source_spans

FENCE = chr(96) * 3


@dataclass(frozen=True)
class Practice:
    topic: str
    wrong: str
    right: str
    x: int
    expected: int
    y: int
    expected_y: int


# Not derived from golden tasks or the blind holdout.
CASES = [
    Practice("Cap player health at 100", "math.clamp(value, 0, 99)", "math.clamp(value, 0, 100)", 120, 100, -5, 0),
    Practice("Stamina recharge floors first", "math.ceil(value) * 3", "math.floor(value) * 3", 2.7, 6, 5.9, 15),
    Practice("Triple coin rewards", "value * 2", "value * 3", 2, 6, 5, 15),
    Practice("Subtract shop discounts", "value + 2", "value - 2", 5, 3, 10, 8),
    Practice("Cap jump boost at ten", "math.max(value, 10)", "math.min(value, 10)", 5, 5, 15, 10),
    Practice("Divide critical power by ten", "value / 100", "value / 10", 10, 1, 50, 5),
    Practice("Clamp negative armor damage", "value - 10", "math.max(0, value - 10)", 5, 0, 20, 10),
    Practice("Wrap round indices at five", "value % 4", "value % 5", 4, 4, 7, 2),
    Practice("Double squared combo points", "value * value", "value * value * 2", 2, 8, 3, 18),
    Practice("Round half-cooldowns upward", "math.floor(value / 2)", "math.ceil(value / 2)", 3, 2, 5, 3),
]


def code(expression: str) -> str:
    return "local function calculate(value: number): number\n    return " + expression + "\nend\nreturn calculate\n"


def answer(expression: str) -> str:
    return "Here is the mechanic:\n" + FENCE + "luau\n" + code(expression) + FENCE + "\n"


def assertions(item: Practice) -> str:
    return (FENCE + "luau\n"
            + f"assert(result({item.x}) == {item.expected})\n"
            + f"assert(result({item.y}) == {item.expected_y})\n"
            + FENCE)


def verdict(ok: bool = True, *, timeout: bool = False) -> dict:
    return {"ran": True, "executed": True, "ok": ok, "status": "pass" if ok else "fail",
            "exit_code": 0 if ok else 1, "timed_out": timeout, "output_limited": False,
            "error": "" if ok else "timeout" if timeout else "runtime_error",
            "errors": [], "output": "untrusted model response",
            "usage": {"wall_seconds": 0.01, "cpu_seconds": 0.001,
                      "max_rss_bytes": 8192, "output_bytes": 16}}


class ScriptedVM:
    """Fake runner uses exact known module text, not a Luau interpreter."""

    def __init__(self, accepted: str, *, timeout: bool = False, missing: bool = False):
        self.accepted, self.timeout, self.missing = accepted, timeout, missing
        self.calls = []
        self.checked = []

    def luau_run(self, source, *, tests="", time_limit_s=0, memory_limit_mb=0):
        self.calls.append((source, tests))
        assert time_limit_s == 3 and memory_limit_mb == 256
        assert len(tests.splitlines()) in (2, 3, 4)
        if self.missing:
            raise OSError("VM not installed")
        return verdict(ok=(source == code(self.accepted)) and not self.timeout, timeout=self.timeout)

    def luau_check(self, source, *, strict=False):
        self.checked.append(source)
        return {"ran": True, "ok": True, "errors": []}


def context():
    return Settings(luau_run_before_answer=True), SimpleNamespace(model="test", task_timeout=600)


@pytest.mark.parametrize("item", CASES, ids=lambda p: p.topic)
def test_ten_original_wrong_logic_cases_caught_and_repaired(item):
    settings, route = context()
    vm = ScriptedVM(item.right)
    writes, fixes = [], []

    async def writer(source):
        writes.append(source)
        return assertions(item)

    async def fixer(source, signal):
        fixes.append((source, signal))
        return FENCE + "luau\n" + code(item.right) + FENCE

    final, records = asyncio.run(luau_run_repair.review(
        answer(item.wrong), settings, route, prompt=item.topic,
        writer=writer, fixer=fixer, runner=vm))
    assert records[0]["state"] == "repaired"
    assert records[0]["ok"] is True and records[0]["attempts"] == 2
    assert records[0]["repairs"] == 1 and records[0]["assertions"] == 2
    assert len(vm.calls) == 2 and len(vm.checked) == 1
    assert len(writes) == len(fixes) == 1
    assert source_spans(final)[0][2] == code(item.right)
    assert "not independent proof" in final
    assert "untrusted model response" not in final


def test_correct_code_remains_identical_inside_fence():
    settings, route = context()
    item = CASES[0]
    vm = ScriptedVM(item.right)

    async def writer(_):
        return assertions(item)

    async def no_fix(*_):
        pytest.fail("passing code should not be rewritten")

    initial = answer(item.right)
    final, rows = asyncio.run(luau_run_repair.review(
        initial, settings, route, writer=writer, fixer=no_fix, runner=vm))
    assert final.startswith(initial.rstrip())
    assert source_spans(final)[0][2] == code(item.right)
    assert len(vm.calls) == 1 and rows[0]["state"] == "passed"


def test_hanging_loop_hits_limit_and_never_gets_retried():
    settings, route = context()
    original = FENCE + "luau\nwhile true do end\nreturn 1\n" + FENCE
    vm = ScriptedVM("return 1", timeout=True)

    async def writer(_):
        return FENCE + "luau\nassert(result == 1)\nassert(result ~= 2)\n" + FENCE

    async def no_fix(*_):
        pytest.fail("timed-out execution must never cause a repair model call")

    final, rows = asyncio.run(luau_run_repair.review(
        original, settings, route, writer=writer, fixer=no_fix, runner=vm))
    assert len(vm.calls) == 1 and rows[0]["state"] == "timeout"
    assert rows[0]["repairs"] == 0 and final.startswith(original)


def test_second_repair_is_allowed_but_never_a_third():
    settings, route = context()
    item = CASES[0]
    vm = ScriptedVM(item.right)
    attempts = []

    async def writer(_):
        return assertions(item)

    async def fixer(source, _failure):
        attempts.append(source)
        expression = "math.clamp(value, 0, 98)" if len(attempts) == 1 else item.right
        return FENCE + "luau\n" + code(expression) + FENCE

    final, rows = asyncio.run(luau_run_repair.review(
        answer(item.wrong), settings, route, writer=writer, fixer=fixer, runner=vm))
    assert rows[0]["state"] == "repaired"
    assert rows[0]["attempts"] == 3 and rows[0]["repairs"] == 2
    assert len(vm.calls) == 3 and len(attempts) == 2
    assert source_spans(final)[0][2] == code(item.right)


def test_repair_failing_static_check_is_never_shown():
    settings, route = context()
    item = CASES[0]
    vm = ScriptedVM(item.right)

    def rejects(_source):
        return {"ran": True, "ok": False, "errors": [{"message": "bad"}]}

    async def writer(_):
        return assertions(item)

    async def fixer(_source, _failure):
        return FENCE + "luau\n" + code(item.right) + FENCE

    initial = answer(item.wrong)
    final, rows = asyncio.run(luau_run_repair.review(
        initial, settings, route, writer=writer, fixer=fixer, runner=vm,
        checker=rejects))
    assert rows[0]["state"] == "failed" and rows[0]["repairs"] == 0
    assert len(vm.calls) == 1
    assert source_spans(final)[0][2] == code(item.wrong)


def test_missing_vm_is_unavailable_not_a_turn_error_or_pass():
    settings, route = context()
    vm = ScriptedVM(CASES[0].right, missing=True)

    async def writer(_):
        return assertions(CASES[0])

    initial = answer(CASES[0].wrong)
    final, rows = asyncio.run(luau_run_repair.review(
        initial, settings, route, writer=writer, runner=vm))
    assert final.startswith(initial.rstrip()) and "not verified" in final
    assert rows[0]["state"] == "unavailable" and rows[0]["ran"] is False
    assert len(vm.calls) == 1


def test_unconfigured_vm_does_not_even_generate_assertions():
    settings, route = context()

    async def no_write(_):
        pytest.fail("no model call when VM is unconfigured")

    final, rows = asyncio.run(luau_run_repair.review(
        answer(CASES[0].wrong), settings, route, runner=None, writer=no_write))
    assert rows[0]["state"] == "not_configured" and "skipped" in final


@pytest.mark.parametrize("invalid", [
    "assert(result(1) == 1)",
    FENCE + "luau\nassert(result(1) == 1)\n" + FENCE,
    FENCE + "luau\nassert(result(1) == 1)\nprint('unwanted')\n" + FENCE,
    FENCE + "luau\nassert(result(1) == 1)\nassert(result(2) == 2); print('oops')\n" + FENCE,
])
def test_invalid_generated_assertions_cannot_run(invalid):
    settings, route = context()
    vm = ScriptedVM(CASES[0].right)

    async def writer(_):
        return invalid

    final, rows = asyncio.run(luau_run_repair.review(
        answer(CASES[0].wrong), settings, route, writer=writer, runner=vm))
    assert rows[0]["state"] == "invalid_assertions"
    assert vm.calls == [] and "not run" in final


def test_roblox_engine_calls_are_skipped_without_inventing_mocks():
    settings, route = context()
    vm = ScriptedVM("irrelevant")
    initial = FENCE + "luau\nreturn game:GetService('Players')\n" + FENCE
    final, rows = asyncio.run(luau_run_repair.review(initial, settings, route, runner=vm))
    assert final.startswith(initial) and rows[0]["state"] == "skipped_engine"
    assert vm.calls == []


def test_setting_off_is_byte_identical_for_answer_messages_and_archive():
    settings, route = context()
    settings.luau_run_before_answer = False
    initial = answer(CASES[0].wrong)

    async def no_write(_):
        pytest.fail("disabled runtime must not contact any model")

    assert asyncio.run(luau_run_repair.review(
        initial, settings, route, runner=None, writer=no_write)) == (initial, [])
    assert Settings().luau_run_before_answer is False
    messages = [{"role": "user", "content": "Make a function"}]
    archive = [{"already": "there"}]
    before = (initial, deepcopy(messages), deepcopy(archive))
    assert asyncio.run(doc_grounding.finalize(
        doc_grounding.Grounding(), route, (initial, messages, archive),
        settings=settings, model_client=object())) == before


class FakeModel:
    def __init__(self, item):
        self.item = item
        self.calls = []

    @property
    def chat(self):
        return SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = (assertions(self.item) if len(self.calls) == 1
                   else FENCE + "luau\n" + code(self.item.right) + FENCE)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_real_finalization_writes_assertions_runs_and_persists_repair(monkeypatch):
    item = CASES[0]
    settings, route = context()
    vm = ScriptedVM(item.right)
    monkeypatch.setattr(doc_knowledge, "client_for", lambda _settings: vm)
    model = FakeModel(item)
    original = answer(item.wrong)
    messages = [{"role": "user", "content": item.topic}]
    output, saved, archive = asyncio.run(doc_grounding.finalize(
        doc_grounding.Grounding(), route, (original, messages, []),
        settings=settings, model_client=model, prompt=item.topic))
    assert item.right in output and item.wrong not in output
    assert len(model.calls) == 2 and len(vm.calls) == 2
    assert saved[-1] == {"role": "assistant", "content": output}
    assert messages == [{"role": "user", "content": item.topic}]
    assert archive[-1]["star_luau_run"]["blocks"][0]["state"] == "repaired"
    assert "untrusted model response" not in str(archive)


def test_legacy_settings_default_and_reject_truthy_strings(tmp_path):
    stored = tmp_path / "settings.json"
    stored.write_text("{}", encoding="utf-8")
    legacy = Settings.load(stored)
    assert legacy.luau_run_before_answer is False
    legacy.luau_run_before_answer = "true"
    with pytest.raises(ValueError, match="true or false"):
        legacy.validate()
