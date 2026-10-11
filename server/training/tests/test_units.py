"""Unit tests of the pure parts (run on the PC; no server, no Luau)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest   # noqa: E402

from startrain import decontam, gates, harness, mutate, parse, quiet, topics  # noqa: E402
from startrain import similarity as sim  # noqa: E402
from startrain.config import Settings  # noqa: E402
from startrain.store import Store, append_jsonl, read_jsonl  # noqa: E402


# --- parsing -------------------------------------------------------------------------------------------------
def test_parse_task_and_solution():
    reply = "### PROMPT\nWrite a thing.\n### TESTS\n```luau\nlocal M = load_answer()\ncheck('a', true)\n```\n"
    prompt, tests, problem = parse.parse_task(reply)
    assert (prompt, problem) == ("Write a thing.", "")
    assert tests.startswith("local M = load_answer()")
    assert parse.parse_task("no sections")[2]
    assert parse.parse_task("### PROMPT\nx\n### TESTS\nno code")[2] == "TESTS section has no code block"
    code, problem = parse.parse_solution("Here:\n```luau\nlocal a = 1\nreturn a\n```\nIt works.\n")
    assert code == "local a = 1\nreturn a\n" and not problem
    assert parse.parse_solution("nothing")[1]


def test_parse_ideas():
    ideas = parse.parse_ideas("1. Build a ring buffer that drops the oldest item\n- Parse key=value pairs with escapes\nshort\n")
    assert len(ideas) == 2 and ideas[0].startswith("Build a ring")


# --- mutants -------------------------------------------------------------------------------------------------
CODE = '''--!strict
local M = {}
-- if a == b then (a comment must not be mutated)
function M.f(a: number, b: number): boolean
	local s = "a == b and 1 < 2"
	if a == b and a < 10 then
		return true
	end
	M.count += 1
	return a + 1 > b
end
return M
'''


def test_mask_blanks_comments_and_strings():
    masked = sim_masked = mutate.mask(CODE)
    assert len(masked) == len(CODE)
    assert "a comment" not in masked and '"a == b' not in masked.replace(" ", "")
    assert "a == b and a < 10" in masked


def test_mutants_touch_code_only():
    kinds = {m.kind for m in mutate.candidates(CODE)}
    assert {"eq-flip", "lt-le", "and-or", "plus-minus", "int-plus1", "return-nil", "true-false", "add-assign"} <= kinds
    for m in mutate.candidates(CODE):
        assert m.code != CODE
        assert "-- if a == b then (a comment must not be mutated)" in m.code        # comments untouched
        assert 'local s = "a == b and 1 < 2"' in m.code                                # strings untouched
    assert not any(m.kind == "return-nil" and m.line == 11 for m in mutate.candidates(CODE))   # indented only


def test_select_is_seeded_and_spread():
    a = [m.code for m in mutate.select(CODE, 5, 8)]
    assert a == [m.code for m in mutate.select(CODE, 5, 8)]
    assert a != [m.code for m in mutate.select(CODE, 6, 8)]
    assert len({m.kind for m in mutate.select(CODE, 5, 8)}) >= 5


# --- similarity and decontamination ---------------------------------------------------------------------------
def test_similarity_basics():
    a = sim.shingles(sim.tokens("write a luau module named inventory with add remove and count functions"))
    b = sim.shingles(sim.tokens("write a luau module named inventory with add remove and count methods"))
    c = sim.shingles(sim.tokens("completely different words about raycasting and cframes in a vehicle"))
    assert sim.jaccard(a, a) == 1.0 and sim.jaccard(a, b) > 0.3 and sim.jaccard(a, c) == 0.0
    assert sim.text_hash("A  b") == sim.text_hash("a b")
    assert abs(sim.cosine([1, 0], [1, 0]) - 1) < 1e-9 and sim.cosine([1, 0], [0, 1]) == 0


@pytest.fixture()
def suite(tmp_path):
    root = tmp_path / "suite"
    (root / "reference").mkdir(parents=True)
    (root / "tests").mkdir()
    tasks = [{"id": "T-1", "prompt": "Write a Luau ModuleScript named Vault that stores secret numbers and lets the owner read them back safely.",
              "goal": "Vault module"},
             {"id": "T-2", "prompt": "Explain how a RemoteEvent handler should validate the arguments a client sends to the server.", "goal": "remote validation"}]
    (root / "golden-tasks-x.json").write_text(json.dumps(tasks), encoding="utf-8")
    (root / "reference" / "T-1.md").write_text("```luau\nlocal Vault = {}\nfunction Vault.store(owner, secret)\n  assert(type(secret) == 'number')\n  Vault[owner] = secret\nend\nreturn Vault\n```\n", encoding="utf-8")
    (root / "tests" / "T-1.luau").write_text("local Vault = load_answer()\nVault.store('a', 4)\ncheck('stored', Vault.a == 4)\n", encoding="utf-8")
    return root


def test_decontam_catches_exact_and_fuzzy(suite):
    s = Settings()
    index = decontam.build_index(suite)
    d = decontam.Decontaminator(index, s)
    assert d.self_check(suite) == []
    unrelated = sim.fingerprint("Write a ring buffer module for numbers with push and pop and a fixed capacity of ten.",
                                "local R = {}\nfunction R.push(x) end\nreturn R", "local R = load_answer()\ncheck('x', true)")
    assert d.check_text(unrelated) == ""
    paraphrase = sim.fingerprint("Write a Luau ModuleScript named Vault that stores secret numbers and lets the owner read them back safely please.",
                                 "local R = {}\nreturn R", "")
    assert "evaluation prompt" in d.check_text(paraphrase)
    copied = sim.fingerprint("A clean unrelated task statement about timers and countdown helpers that is long enough.",
                             "local Vault = {}\nfunction Vault.store(owner, secret)\n  assert(type(secret) == 'number')\n  Vault[owner] = secret\nend\nreturn Vault\n", "")
    assert "reference answer" in d.check_text(copied)


def test_decontam_vectors(suite):
    s = Settings()
    index = decontam.build_index(suite, embed=lambda texts: [[1.0, 0.0] for _ in texts])
    d = decontam.Decontaminator(index, s)
    assert d.check_vector([1.0, 0.0]) and not d.check_vector([0.0, 1.0])


# --- gates that need no tools --------------------------------------------------------------------------------
GOOD_TESTS = "\n".join(["local M = load_answer()"] + [f'check("case {i}", M.f({i}) == {i})' for i in range(6)])
PURE = "--!strict\nlocal M = {}\nfunction M.f(x: number): number\n\treturn x\nend\nreturn M\n" + "-- padding to be long enough\n" * 5


def cand(**over):
    c = {"mode": "pure", "code": PURE, "tests": GOOD_TESTS + "\n-- " + "x" * 120, "prompt": "p" * 80, "response": PURE, "topic": "t"}
    c.update(over)
    return c


def test_g0_rules():
    s = Settings()
    assert gates.g0_shape(cand(), s).ok
    assert gates.g0_shape(cand(code=PURE.replace("--!strict\n", "")), s).code == "missing_strict_header"
    assert gates.g0_shape(cand(code=PURE + "local x = 1 :: any\n"), s).code == "cast_to_any"
    assert gates.g0_shape(cand(code=PURE + "local m = require(script.Parent.X)\n"), s).code == "forbidden_call"
    assert gates.g0_shape(cand(code=PURE + "print('x')\n"), s).code == "debug_print"
    assert gates.g0_shape(cand(mode="mock"), s).code == "strict_unverifiable"
    assert gates.g0_shape(cand(tests=GOOD_TESTS + '\ncheck("same", M.f(1) == M.f(1))\n-- ' + "x" * 120), s).code == "tautological_check"
    assert gates.g0_shape(cand(tests=GOOD_TESTS + '\ncheck("always", true)\n-- ' + "x" * 120), s).code == "constant_check"
    assert gates.g0_shape(cand(tests="local M = load_answer()\ncheck('a', M.f(1) == 1)\n-- " + "x" * 150), s).code == "few_checks_written"
    assert gates.g0_shape(cand(prompt="short"), s).code == "prompt_length"
    secret = "ghp_" + "a" * 30
    assert gates.g0_shape(cand(response=secret), s).code == "credential_pattern"


@pytest.mark.parametrize("snippet,bad", [
    ("wait(1)", True), ("task.wait(1)", False), ("spawn(f)", True), ("task.spawn(f)", False), ("local t = tick()", True),
    ("part:Destroy()", False), ("conn:disconnect()", True), ("Instance.new('Part', workspace)", True),
    ("local p = Instance.new('Part')", False), ("-- wait(1) in a comment", False), ("local s = 'wait(1)'", False),
    ("x = game.Workspace", True), ("local b = Instance.new('BodyVelocity')", True),
])
def test_g6_lint(snippet, bad):
    verdict = gates.g6_deprecated({"code": snippet})
    assert (not verdict.ok) is bad, snippet


def test_memory_duplicates():
    s = Settings()
    mem = gates.Memory()
    fp = sim.fingerprint("Write a queue module with push pop and size for numbers in strict mode.", "local Q = {}\nreturn Q", "")
    mem.add("a", fp, [1.0, 0.0])
    assert mem.duplicate_of(fp, s) == "a"
    other = sim.fingerprint("Parse key value pairs from a semicolon separated string and return a table.", "local P = {}\nfunction P.parse(s) return {} end\nreturn P", "")
    assert mem.duplicate_of(other, s) == ""
    assert mem.nearest([1.0, 0.0])[1] > 0.99 and mem.nearest([0.0, 1.0])[1] == 0.0


# --- harness output --------------------------------------------------------------------------------------------
def test_harness_script_and_output():
    script = harness.build_test_script("-- prelude\n", "return {}\n]]\n", "check('x', true)")
    assert script.startswith("local __SRC = [=[") and "-- ===== test body =====" in script and script.rstrip().endswith("print('@@DONE')")
    out = harness.parse_output("@@T\tpass\ta\n@@T\tfail\tb\n@@DONE\nnoise\n")
    assert out.passed == 1 and out.failed == 1 and out.done and not out.all_pass(1)
    assert harness.parse_output("@@T\tpass\ta\n@@DONE\n").all_pass(1)
    assert harness.parse_output("@@LOADERR\tbad\n").load_error == "bad"


# --- quiet rules -------------------------------------------------------------------------------------------------
def test_window_and_lock(tmp_path):
    at = lambda h, m: datetime(2026, 10, 11, h, m, tzinfo=timezone.utc)      # noqa: E731
    assert quiet.in_window("", at(12, 0)) and quiet.in_window("04:00-10:00", at(4, 0)) and not quiet.in_window("04:00-10:00", at(10, 0))
    assert quiet.in_window("22:00-04:00", at(23, 30)) and quiet.in_window("22:00-04:00", at(3, 59)) and not quiet.in_window("22:00-04:00", at(12, 0))
    with pytest.raises(ValueError):
        quiet.parse_window("nonsense")
    lock = tmp_path / "lock"
    assert not quiet.lock_held(lock)
    lock.mkdir()
    assert quiet.lock_held(lock, 1200)
    assert not quiet.lock_held(lock, 1200, now=time.time() + 5000)         # stale: ignored, never removed
    assert lock.exists()


class FakeBrain:
    def __init__(self, busy_for=0):
        self.calls = 0
        self.busy_for = busy_for

    def others_active(self, own_model=None):
        self.calls += 1
        return self.calls <= self.busy_for

    def seconds_since_other_activity(self):
        return 1e9 if self.calls > self.busy_for else 0.0


def test_wait_until_clear_pauses_for_lock_pause_file_and_chats(tmp_path):
    s = Settings(home=tmp_path, lock_dir=str(tmp_path / "lock"), poll_s=0.01, idle_s=0)
    s.ensure_dirs()
    (tmp_path / "lock").mkdir()
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            (tmp_path / "lock").rmdir()
            s.pause_file.write_text("x")
        if len(sleeps) == 4:
            s.pause_file.unlink()

    waited = quiet.wait_until_clear(s, FakeBrain(busy_for=1), lambda: False, lambda m: None, sleep=sleep)
    assert set(waited) >= {"lock", "pause-file"} and len(sleeps) >= 4
    assert quiet.wait_until_clear(s, FakeBrain(), lambda: True, lambda m: None, sleep=sleep) == {}      # stop wins


# --- topics and store ---------------------------------------------------------------------------------------------
def test_topics_valid_and_weighted_to_failures():
    assert topics.validate() == []
    ids = {t.id for t in topics.TOPICS}
    assert len(ids) >= 40
    heavy = {t.category for t in topics.TOPICS if t.weight == 3}
    assert {"remote-security", "datastore-safety", "ui-layout", "animation"} <= heavy


def test_store_roundtrip_and_rebuild(tmp_path):
    store = Store(tmp_path)
    kept = {"id": "sv-1", "topic": "t1", "category": "c1", "gates": {"G3": {}}, "prompt": "p", "code": "c"}
    rej = {"id": "sv-2", "topic": "t1", "category": "c1", "gate": "G3", "code": "assertion_failed"}
    store.record_kept(kept, [0.5, 0.5])
    store.record_rejected(rej)
    store.save()
    assert store.state["kept"] == 1 and store.state["candidates"] == 2
    assert Store(tmp_path).state["rejected"] == {"G3": {"assertion_failed": 1}}
    (tmp_path / "state.json").write_text("{broken", encoding="utf-8")        # a damaged state file is rebuilt from the logs
    again = Store(tmp_path)
    assert again.state["kept"] == 1 and again.state["candidates"] == 2 and again.state["by_topic"]["t1"] == {"candidates": 2, "kept": 1}
    assert again.load_vectors() == [("sv-1", [0.5, 0.5])]
    with open(tmp_path / "kept.jsonl", "a", encoding="utf-8") as handle:
        handle.write('{"id": "torn')                                           # a torn last line is ignored
    assert len(read_jsonl(tmp_path / "kept.jsonl")) == 1
    append_jsonl(tmp_path / "x.jsonl", {"a": 1})
    assert read_jsonl(tmp_path / "x.jsonl") == [{"a": 1}]
