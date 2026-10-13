"""Real-path regression tests for advisory answer-integrity detection."""
import pytest

from star.answer_integrity import inspect_answer


def fenced(source):
    return "```luau\n" + source + "\n```"


@pytest.mark.parametrize("code", [
    "function f()\nreturn 1",
    "if ready then\nprint('go')",
    "for i = 1, 3 do\nprint(i)",
    "while alive do\nbreak",
    "do\nlocal n = 1",
    "function f()\nif ok then\nreturn true\nend",
    "for i = 1, 3 do\nif i > 1 then print(i) end",
    "repeat\nx += 1",  # until missing
])
def test_missing_constructs_are_reported(code):
    verdict = inspect_answer(fenced(code))
    assert any(issue.code == "unclosed_luau_block" for issue in verdict.issues), code
    assert "end or until" in verdict.repair_instruction


@pytest.mark.parametrize("code", [
    "function f()\nreturn 1\nend",
    "if ready then\nprint('yes')\nelseif later then\nprint('later')\nelse\nprint('no')\nend",
    "for i = 1, 3 do\nprint(i)\nend",
    "while alive do\nbreak\nend",
    "do\nlocal n = 1\nend",
    "repeat\nx += 1\nuntil x == 2",
    "function f()\nfor i=1,3 do\nif i==1 then continue end\nend\nend",
    "local x = 'end if function for while do'",
    'local x = "function end" -- if then end',
    "local x = [[function if for while do end]]",
    "local x = [==[function if while do end]==]",
    "local x = [=[function end]=]",
    "--[[ function if for while do end ]]\nlocal n = 1",
    "--[==[ function if for do end ]==]\nlocal n = 1",
    'local x = "escaped \\"function\\" end"',
    "local x = " + chr(96) + "function if end" + chr(96),
])
def test_complete_or_quoted_keywords_are_not_false_positives(code):
    assert inspect_answer(fenced(code)).ok, code


@pytest.mark.parametrize("answer", [
    "```luau\nlocal n = 1",
    "```~luau\nfunction f() end",
    "```python\nprint(1)",
])
def test_unclosed_markdown_fences_are_reported(answer):
    verdict = inspect_answer(answer)
    assert "unclosed_fence" in {issue.code for issue in verdict.issues}


@pytest.mark.parametrize("ending", [
    "I can improve the result and",
    "The next thing to do is",
    "For the next step we will",
    "You should check this with",
    "Here are the changes,",
])
def test_trailing_half_sentence_detection(ending):
    verdict = inspect_answer(ending)
    assert "trailing_fragment" in {issue.code for issue in verdict.issues}


@pytest.mark.parametrize("clean", [
    "The script is complete.",
    "Code follows:\n```luau\nlocal x = 1\n```",
    "### Steps:",
    "Here is a Lua function and a note.",
    "The word function outside a fence is only prose.",
    "All checks passed",
])
def test_complete_prose_is_not_marked_as_truncated(clean):
    assert inspect_answer(clean).ok


def test_reported_errors_with_unchanged_code_are_actionable():
    answer = fenced("local score = 1\nreturn score")
    verdict = inspect_answer(answer, self_check="ERROR: assertion failed on score", previous_code=answer)
    assert [issue.code for issue in verdict.issues] == ["unrepaired_selfcheck"]
    assert "rerun the self-check" in verdict.repair_instruction


def test_repaired_code_after_reported_errors_not_falsely_flagged():
    old = fenced("local score = 0\nreturn score")
    new = fenced("local score = 1\nreturn score")
    assert inspect_answer(new, self_check="ERROR: test failed on score", previous_code=old).ok


def test_changed_only_comment_does_not_hide_unchanged_code():
    before = fenced("local score = 1\nreturn score")
    after = fenced("local score = 1\n-- changed only this comment\nreturn score")
    verdict = inspect_answer(after, self_check="FAILED test", previous_code=before)
    assert "unrepaired_selfcheck" in {issue.code for issue in verdict.issues}


@pytest.mark.parametrize("report", [
    "No errors; all checks passed",
    "0 errors",
    "Error fixed in this version",
    "Assertions passed",
])
def test_selfcheck_success_language_does_not_trigger(report):
    candidate = fenced("return 1")
    assert inspect_answer(candidate, self_check=report, previous_code=candidate).ok


def test_no_previous_snapshot_is_not_inferred_to_be_unchanged():
    assert inspect_answer(fenced("return 1"), self_check="Error: function missing").ok


def test_structured_verdict_has_multiple_independent_reasons():
    bad = "```luau\nfunction unfinished()\nreturn 1"
    verdict = inspect_answer(bad)
    codes = {issue.code for issue in verdict.issues}
    assert {"unclosed_fence", "unclosed_luau_block"} <= codes
    assert not verdict.ok and verdict.reason


@pytest.mark.parametrize("invalid", [None, 123, {}])
def test_invalid_types_fail_explicitly(invalid):
    with pytest.raises(TypeError):
        inspect_answer(invalid)
    with pytest.raises(TypeError):
        inspect_answer("", self_check=invalid)
    with pytest.raises(TypeError):
        inspect_answer("", previous_code=invalid)


def test_docs_describe_provenance_and_non_integration():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[1] / "docs/agents/answer-integrity.md").read_text()
    assert "not wired" in doc.lower()
    assert "FAILURE_LEDGER.md" in doc
    assert "code_answer_completion.py" in doc
    assert "Roblox Studio" in doc
