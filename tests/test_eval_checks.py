"""Scoring rules for golden-task answers (star/eval_checks.py), tested with fakes only."""
import pytest

from star import eval_checks as ec

FENCE = "`" * 3


def block(code: str, lang: str = "luau") -> str:
    return f"{FENCE}{lang}\n{code}\n{FENCE}"


class FakeSandbox:
    def __init__(self, stdout="@@T\tpass\ta\n@@DONE\n", timed_out=False, error=""):
        self.stdout, self.timed_out, self.error, self.sources = stdout, timed_out, error, []

    def run(self, source):
        self.sources.append(source)
        return type("R", (), {"stdout": self.stdout, "timed_out": self.timed_out, "error": self.error, "rc": 0})()


def ok_check(code, strict=False):
    return {"ok": True, "errors": []}


def test_split_answer_removes_what_star_appended():
    body, footer = ec.split_answer("Answer text\n\n**Luau check by STAR:** fine\n\n---\n**Sources retrieved by STAR** (x)\n1. a")
    assert body == "Answer text"
    assert "Sources retrieved" in footer
    assert ec.split_answer("plain") == ("plain", "")


def test_looks_truncated_when_the_text_stops_inside_a_code_block():
    assert ec.looks_truncated("Here:\n" + FENCE + "luau\nlocal a = 1\n")
    assert not ec.looks_truncated("Here:\n" + block("local a = 1") + "\nDone.")
    assert not ec.looks_truncated("")
    assert not ec.looks_truncated("no code at all")
    cut = "Here:\n" + FENCE + "luau\nlocal a = 1\n\n---\n**Sources retrieved by STAR** (x)\n1. y"
    assert ec.looks_truncated(cut)


def test_extract_luau_blocks_only_lua_fences_with_code():
    text = block("local a = 1") + "\n" + block("x = 1", "python") + "\n" + block("   ") + "\n" + block("local b = 2", "lua")
    assert [b.strip() for b in ec.extract_luau_blocks(text)] == ["local a = 1", "local b = 2"]


def test_unlabelled_fences_count_only_when_no_labelled_block_exists_and_they_read_as_luau():
    bare = FENCE + "\nlocal a = 1\nreturn a\n" + FENCE
    assert [b.strip() for b in ec.extract_luau_blocks("Here:\n" + bare)] == ["local a = 1\nreturn a"]
    assert ec.extract_luau_blocks("Output:\n" + FENCE + "\nhello world\n" + FENCE) == []
    mixed = bare + "\n" + block("local b = 2")
    assert [b.strip() for b in ec.extract_luau_blocks(mixed)] == ["local b = 2"]


def test_strip_luau_comments_and_strings():
    code = 'local a = "goto" -- goto here\nlocal b = [[goto]] --[[ goto\n]] local c = 1'
    assert "goto" not in ec.strip_luau(code, strings=True)
    kept = ec.strip_luau(code)
    assert '"goto"' in kept and "-- goto" not in kept
    assert ec.strip_luau(code).count("\n") == code.count("\n")          # line numbers survive


def test_strip_luau_handles_escapes_and_long_brackets():
    assert ec.strip_luau('local s = "a\\"b" -- c', strings=True).strip() == 'local s = ""'
    assert ec.strip_luau("x = [==[ ]] -- ]==] y", strings=True).strip() == "x = [[]] y"


def test_final_return_to_local_only_top_level():
    code = "local function f()\n\treturn x\nend\nreturn Mod"
    assert ec.final_return_to_local(code).endswith("local __M = Mod")
    assert ec.final_return_to_local("local function f()\n\treturn x\nend") is None


def test_long_bracket_avoids_the_text():
    opener, closer = ec.long_bracket("a ]] b ]=] c")
    assert opener == "[==[" and closer == "]==]"


def test_pattern_checks_scopes_and_forbid():
    auto = {"require": [{"id": "svc", "re": r'GetService\("Players"\)', "why": "need Players"},
                        {"id": "either", "any": [r"Foo", r"Bar"], "why": "need Foo or Bar"}],
            "forbid": [{"id": "no_wait", "re": r"\bwait\(", "why": "no wait", "scope": "code_nostr"}]}
    good = ['local p = game:GetService("Players") -- wait(1)\nBar()']
    assert all(c.ok for c in ec.pattern_checks(auto, good, ""))
    bad = ['local p = 1\nwait(2)']
    results = {c.id: c for c in ec.pattern_checks(auto, bad, "")}
    assert not results["require:svc"].ok and results["require:svc"].detail == "need Players"
    assert not results["require:either"].ok
    assert not results["forbid:no_wait"].ok and "wait(" in results["forbid:no_wait"].detail


def test_pattern_scope_prose_ignores_code():
    auto = {"require": [{"id": "n", "re": r"162", "why": "w", "scope": "prose"}]}
    body = "no number here\n" + block("local x = 162")
    assert not ec.pattern_checks(auto, ec.extract_luau_blocks(body), body)[0].ok
    assert ec.pattern_checks(auto, [], "it was 162")[0].ok


def test_parse_test_output_ignores_answer_noise():
    out = ec.parse_test_output("hello\n@@T\tpass\tone\n@@T\tfail\ttwo\nnoise @@T\tpass\tfake\n@@DONE\n")
    assert out.results == [("one", True), ("two", False)] and out.done


def test_unit_checks_reports_failures_and_expected_count():
    out = ec.parse_test_output("@@T\tpass\ta\n@@T\tfail\tb\n@@DONE\n")
    check = ec.unit_checks(out, FakeSandbox(), 2)[0]
    assert not check.ok and "b" in check.detail and "1/2" in check.detail
    assert ec.unit_checks(ec.parse_test_output("@@T\tpass\ta\n@@DONE\n"), FakeSandbox(), 1)[0].ok
    short = ec.unit_checks(ec.parse_test_output("@@T\tpass\ta\n@@DONE\n"), FakeSandbox(), 3)[0]
    assert not short.ok and "1 of 3" in short.detail


def test_unit_checks_failure_modes():
    assert "did not load" in ec.unit_checks(ec.parse_test_output("@@LOADERR\tboom\n"), FakeSandbox(), None)[0].detail
    assert "aborted" in ec.unit_checks(ec.parse_test_output("@@T\tpass\ta\n@@ERR\tx\n@@DONE\n"), FakeSandbox(), None)[0].detail
    assert "timed out" in ec.unit_checks(ec.UnitOutcome(), FakeSandbox(timed_out=True), None)[0].detail
    assert not ec.unit_checks(ec.parse_test_output(""), FakeSandbox(), None)[0].ok


def test_build_test_script_embeds_answer_before_prelude_and_survives_brackets():
    script = ec.build_test_script("-- prelude", "local s = [[x]] ]=] y", "check('t', true)")
    assert script.startswith("local __SRC = [==[")
    assert script.index("-- prelude") > script.index("local s = [[x]]")
    assert "check('t', true)" in script and script.rstrip().endswith("print('@@DONE')")


def test_citation_check():
    footer = "\n\n---\n**Sources retrieved by STAR** (official documentation)\n\n1. [Size](https://create.roblox.com/docs/ui/size-modifiers) · cited\n2. [Other](https://create.roblox.com/docs/x) · retrieved, not cited\n"
    assert ec.citation_check({"citation": {"required": True}}, footer).ok
    assert ec.citation_check({"citation": {"url_contains_any": ["size-modifiers"]}}, footer).ok
    wrong = ec.citation_check({"citation": {"url_contains_any": ["datastore"]}}, footer)
    assert not wrong.ok and "datastore" in wrong.detail
    assert "no documentation" in ec.citation_check({}, "").detail
    assert "cites none" in ec.citation_check({}, footer.replace("· cited", "· retrieved, not cited")).detail


def test_lenient_source_only_rewrites_the_header():
    assert ec.lenient_source("--!strict\nlocal a = 1").startswith("--!nonstrict")
    assert ec.lenient_source("local a = 1 -- --!strict") == "local a = 1 -- --!strict"


def test_effective_errors_ignore_globals_the_prompt_names():
    result = {"errors": [{"line": 1, "message": "Unknown global 'BuyItem'; consider assigning to it first"},
                         {"line": 2, "message": "Unknown global 'Mystery'; consider assigning to it first"},
                         {"line": 3, "message": "Expected this to be 'number', but got 'string'"}]}
    kept = ec.effective_errors(result, "the handler BuyItem.OnServerEvent is broken")
    assert [e["line"] for e in kept] == [2, 3]


def task(**auto):
    return {"id": "T-1", "prompt": "write code", "auto": auto}


def test_score_answer_passes_and_records_timings():
    answer = "Here.\n" + block("local a = 1\nreturn a")
    score = ec.score_answer(task(), answer, luau_check=ok_check)
    assert score.passed and score.blocks == 1 and "luau_check_s" in score.timings


def test_score_answer_fails_without_code_or_with_compile_errors():
    assert not ec.score_answer(task(), "no code at all", luau_check=ok_check).passed
    bad = lambda code, strict=False: {"ok": False, "errors": [{"line": 2, "message": "boom"}]}
    score = ec.score_answer(task(), block("x ="), luau_check=bad)
    assert not score.passed and "line 2: boom" in score.reasons[0]
    assert not ec.score_answer(task(), "", luau_check=ok_check).passed


def test_unknown_globals_in_later_blocks_are_placeholders_but_the_first_block_is_checked_in_full():
    def check(code, strict=False):
        if "path.to" in code:
            return {"ok": False, "errors": [{"line": 1, "message": "Unknown global 'path'; consider assigning to it first"}]}
        if "oops" in code:
            return {"ok": False, "errors": [{"line": 1, "message": "Unknown global 'oops'; consider assigning to it first"}]}
        return {"ok": True, "errors": []}
    usage = block("local m = require(path.to.Module)")
    assert ec.score_answer(task(), block("return 1") + usage, luau_check=check).passed
    assert not ec.score_answer(task(), block("oops()") + usage, luau_check=check).passed        # first block: a real defect
    assert not ec.score_answer(task(), usage + block("return 1"), luau_check=check).passed      # first block is the example here


def test_score_answer_docs_question_needs_no_code_but_a_citation():
    spec = task(code=False, compile=False, citation={"required": True})
    assert not ec.score_answer(spec, "An answer [1].", luau_check=ok_check).passed
    footer = "\n\n---\n**Sources retrieved by STAR** (x)\n\n1. [A](https://create.roblox.com/docs/a) · cited\n"
    assert ec.score_answer(spec, "An answer [1]." + footer, luau_check=ok_check).passed


def test_score_answer_checks_each_block_up_to_the_limit_and_skips_oversize():
    calls = []

    def counting(code, strict=False):
        calls.append(code)
        return {"ok": True, "errors": []}

    answer = "\n".join(block(f"local v{i} = {i}") for i in range(5))
    ec.score_answer(task(), answer, luau_check=counting)
    assert len(calls) == ec.MAX_CHECKED_BLOCKS
    huge = block("-- " + "x" * (ec.MAX_CHECK_CHARS + 10))
    assert "longer than" in ec.score_answer(task(), huge, luau_check=ok_check).reasons[0]


def test_score_answer_unit_test_runs_longest_block_in_sandbox():
    box = FakeSandbox("@@T\tpass\tone\n@@DONE\n")
    answer = block("local small = 1") + "\n" + block("local big = 1\nlocal bigger = 2\nreturn big")
    score = ec.score_answer(task(unit_test={"file": "t.luau", "checks": 1}), answer, luau_check=ok_check,
                            sandbox=box, prelude="-- P", test_body="check('one', true)")
    assert score.passed and "unit_s" in score.timings
    assert "local bigger = 2" in box.sources[0] and "local small = 1" not in box.sources[0]


def test_score_answer_infrastructure_problems_raise():
    def down(code, strict=False):
        raise OSError("unreachable")

    with pytest.raises(ec.InfraError):
        ec.score_answer(task(), block("local a = 1"), luau_check=down)
    with pytest.raises(ec.InfraError):
        ec.score_answer(task(unit_test={"file": "t", "checks": 1}), block("local a = 1"), luau_check=ok_check,
                        sandbox=FakeSandbox(error="ssh to the sandbox timed out"), prelude="", test_body="x")
    with pytest.raises(ec.InfraError):
        ec.score_answer(task(unit_test={"file": "t", "checks": 1}), block("local a = 1"), luau_check=ok_check)


def test_typecheck_probe_must_be_rejected():
    spec = task(typecheck_probe={"suffix": "__M.map(1)"})
    seen = []

    def rejecting(code, strict=False):
        seen.append(code)
        return {"ok": False, "errors": [{"kind": "TypeError", "message": "bad"}]}

    probed = ec.score_answer(spec, block("local M = {}\nreturn M"), luau_check=lambda c, strict=False: (
        rejecting(c, strict) if "__M.map" in c else {"ok": True, "errors": []}))
    assert probed.passed and "local __M = M" in seen[0]
    accepted = ec.score_answer(spec, block("local M = {}\nreturn M"), luau_check=ok_check)
    assert not accepted.passed and "accepted a call" in accepted.reasons[0]
    no_return = ec.score_answer(spec, block("local M = {}"), luau_check=ok_check)
    assert not no_return.passed
