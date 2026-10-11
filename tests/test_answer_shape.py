"""An answer that runs into the length limit (star/answer_shape.py and the agent loop's use of it)."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from star import answer_shape
from star.agent import execute, malformed_tool_call
from star.answer_shape import LENGTH_NOTE, continuation, splice, stops_inside_code

CUT = ("Here is the module.\n\n```luau\nlocal Pool = {}\n\nfunction Pool.new(size)\n\tlocal self = {}\n"
       "\tfor i = 1, si")


def reply(content=None, calls=None, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls),
                                                    finish_reason=finish)])


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def run(model, **more):
    events = []
    answer, messages, _ = asyncio.run(execute(client=model, model="fake", prompt="Write a pool module in Luau",
                                              image_paths=[], on_event=events.append, **more))
    return answer, messages, [e["event"] for e in events]


# --- the string work ------------------------------------------------------------------------------

def test_an_odd_number_of_fence_lines_means_the_text_stops_inside_code():
    assert stops_inside_code(CUT) and stops_inside_code("```lua\nprint(1)")
    assert not stops_inside_code("```lua\nprint(1)\n```\nDone.") and not stops_inside_code("no code") and not stops_inside_code("")
    # a fence quoted inside a line of prose is not a fence line
    assert not stops_inside_code("Use a ```luau fence.\n\n```luau\nprint(1)\n```")


def test_the_continuation_keeps_whole_lines_and_names_where_to_go_on():
    kept, instruction = continuation(CUT)
    assert kept.endswith("\tlocal self = {}\n") and "for i = 1, si" not in kept
    assert "local self = {}" in instruction and "for i = 1, si" in instruction
    assert "Do not repeat lines" in instruction and "only the remaining lines" in instruction


@pytest.mark.parametrize("answer_from_model", [
    "```luau\n\tfor i = 1, size do\n\t\tself[i] = i\n\tend\n\treturn self\nend\n\nreturn Pool\n```\nIt preallocates.",
    # repeats the last complete line before going on
    "```luau\n\tlocal self = {}\n\tfor i = 1, size do\n\t\tself[i] = i\n\tend\n\treturn self\nend\n\nreturn Pool\n```\nIt preallocates.",
    # no fence at all, just the lines
    "\tfor i = 1, size do\n\t\tself[i] = i\n\tend\n\treturn self\nend\n\nreturn Pool\n",
    # starts the whole block again
    "```luau\nlocal Pool = {}\n\nfunction Pool.new(size)\n\tlocal self = {}\n\tfor i = 1, size do\n\t\tself[i] = i\n\tend\n"
    "\treturn self\nend\n\nreturn Pool\n```\nIt preallocates.",
])
def test_splice_joins_whatever_shape_the_model_continues_in(answer_from_model):
    kept, _ = continuation(CUT)
    whole = splice(kept, answer_from_model)
    if "```" not in answer_from_model:
        assert stops_inside_code(whole), "the model did not close the block: the caller does"
        whole += "```\n"
    code = whole.split("```luau\n", 1)[1].split("```", 1)[0]
    assert code == ("local Pool = {}\n\nfunction Pool.new(size)\n\tlocal self = {}\n\tfor i = 1, size do\n\t\tself[i] = i\n"
                    "\tend\n\treturn self\nend\n\nreturn Pool\n")
    assert whole.startswith("Here is the module.\n\n```luau\n") and not stops_inside_code(whole)
    assert whole.count("```") == 2


def test_text_before_a_fenced_continuation_never_lands_inside_the_code():
    """Seen on the real server: a paragraph and a sources list came first, then the fenced continuation
    (which also repeated the last line). Only the block belongs in the code."""
    kept, _ = continuation(CUT)
    reply = ("A ModuleScript is a special type of script [1][2].\n\n---\nSources (official documentation)\n\n"
             "1. [Intro to module scripts](https://create.roblox.com/docs/x) · cited\n\n"
             "```lua\n\tlocal self = {}\n\tfor i = 1, size do\n\t\tself[i] = i\n\tend\n\treturn self\nend\n\nreturn Pool\n```\n\n"
             "This preallocates the pool.")
    whole = splice(kept, reply)
    code = whole.split("```luau\n", 1)[1].split("```", 1)[0]
    assert "ModuleScript is a special" not in whole and "Sources" not in whole
    assert code == ("local Pool = {}\n\nfunction Pool.new(size)\n\tlocal self = {}\n\tfor i = 1, size do\n\t\tself[i] = i\n"
                    "\tend\n\treturn self\nend\n\nreturn Pool\n")
    assert whole.rstrip().endswith("This preallocates the pool.") and not stops_inside_code(whole)


def test_a_continuation_that_was_cut_too_leaves_the_block_open_and_an_empty_reply_changes_nothing():
    kept, _ = continuation(CUT)
    still_open = splice(kept, "```luau\n\tfor i = 1, size do\n")
    assert stops_inside_code(still_open) and still_open.endswith("\tfor i = 1, size do\n")
    assert splice(kept, "  \n") == kept


def test_the_shape_rule_is_short_and_puts_the_code_first():
    assert len(answer_shape.SHAPE_RULES) < 800, "it is read on every code turn: about 150 tokens"
    assert "complete" in answer_shape.SHAPE_RULES and "first" in answer_shape.SHAPE_RULES


@pytest.mark.parametrize("prompt, expected", [
    ("Write a server script that saves coins", True),
    ("Fix this:\n```lua\nprint(1)\n```", True),
    ("Can you add a cooldown to my remote?", True),
    ("How does TweenService ease a value?", False),
    ("What is the difference between Rate and Emit on a ParticleEmitter?", False),
    ("Describe the scripting model", False),            # "scripting" is not the verb "script"
])
def test_the_rule_is_for_requests_that_ask_for_code(prompt, expected):
    assert answer_shape.asks_for_code(prompt) is expected


def test_the_rule_is_off_unless_switched_on():
    assert not answer_shape.rule_enabled({}) and not answer_shape.rule_enabled({"STAR_ANSWER_SHAPE": "off"})
    assert answer_shape.rule_enabled({"STAR_ANSWER_SHAPE": " ON "})


def test_run_task_adds_the_rule_only_when_switched_on_and_only_to_a_full_code_request(monkeypatch, tmp_path):
    """The request the model would get, captured from a fake client: no network, no model."""
    import contextlib
    from star import desktop_core as core

    sent = []

    class Captured(Exception):
        pass

    class Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def create(self, **kwargs):
            sent.append(kwargs)
            raise Captured()

    @contextlib.asynccontextmanager
    async def fake_open(settings):
        yield Client()

    monkeypatch.setenv("STAR_SKILL_PACKS", "off")
    monkeypatch.setattr(core, "app_data", lambda: tmp_path / "STAR")
    monkeypatch.setattr(core, "open_client", fake_open)
    monkeypatch.setattr(core.doc_grounding, "client_for", lambda settings: None)     # no knowledge service
    settings = core.Settings(model="m")

    def user_text(prompt, mode="auto"):
        sent.clear()
        with pytest.raises(Captured):
            core.run_task(settings, prompt, mode=mode)
        content = sent[0]["messages"][-1]["content"]
        return content if isinstance(content, str) else content[0]["text"]

    question = "Write a Luau ModuleScript that pools bullets for my shooter."
    monkeypatch.delenv("STAR_ANSWER_SHAPE", raising=False)
    assert answer_shape.SHAPE_HEADING not in user_text(question), "off by default: the request is as it was before"
    monkeypatch.setenv("STAR_ANSWER_SHAPE", "on")
    assert answer_shape.SHAPE_HEADING in user_text(question) and "hard length limit" in user_text(question)
    assert answer_shape.SHAPE_HEADING not in user_text(question, mode="fast"), "a quick answer stays as it was"
    assert answer_shape.SHAPE_HEADING not in user_text("Plan a birthday party for ten children.")
    # a Roblox question that asks for an explanation is not told to lead with code
    assert answer_shape.SHAPE_HEADING not in user_text("How does a Roblox client decide which parts are streamed in?")
    monkeypatch.setenv("STAR_ANSWER_SHAPE", "off")
    assert answer_shape.SHAPE_HEADING not in user_text(question)


# --- the agent loop -------------------------------------------------------------------------------

def test_an_answer_cut_inside_its_code_is_finished_with_one_more_request():
    model = FakeClient([reply(CUT, finish="length"),
                        reply("```luau\n\tfor i = 1, size do\n\t\tself[i] = i\n\tend\n\treturn self\nend\nreturn Pool\n```\nDone.")])
    answer, _, events = run(model, continuation_tokens=900)
    assert "for i = 1, size do" in answer and "return Pool\n```" in answer and not stops_inside_code(answer)
    assert "for i = 1, si\n" not in answer
    assert events.count("answer_continuing") == 1
    follow_up = model.requests[1]
    assert follow_up["max_tokens"] == 900
    assert follow_up["messages"][-2]["role"] == "assistant" and follow_up["messages"][-2]["content"].endswith("local self = {}\n")
    assert follow_up["messages"][-1]["role"] == "user" and "cut off by the length limit" in follow_up["messages"][-1]["content"]
    # everything before the two added messages is the original request, byte for byte (the server re-reads nothing)
    assert follow_up["messages"][:-2] == model.requests[0]["messages"]


def test_a_continuation_that_finishes_the_code_but_is_cut_in_its_prose_says_so():
    model = FakeClient([reply(CUT, finish="length"),
                        reply("```luau\n\tfor i = 1, size do\n\tend\n\treturn self\nend\nreturn Pool\n```\nStore it a", finish="length")])
    answer, _, _ = run(model, continuation_tokens=900)
    assert "return Pool\n```" in answer and answer.endswith("Store it a" + LENGTH_NOTE) and len(model.requests) == 2


def test_at_most_two_continuations_and_an_unfinished_block_is_closed_and_labelled():
    model = FakeClient([reply(CUT, finish="length"), reply("```luau\n\tfor i = 1, size do\n", finish="length"),
                        reply("```luau\n\t\tself[i] = i\n", finish="length")])
    answer, _, events = run(model, continuation_tokens=900)
    assert events.count("answer_continuing") == 2 and len(model.requests) == 3
    assert not stops_inside_code(answer) and "the code block above is incomplete" in answer
    assert "self[i] = i" in answer


def test_a_cut_in_the_closing_prose_costs_no_model_call_and_is_said_plainly():
    text = "```luau\nprint(1)\n```\n\nThis prints one and then it"
    model = FakeClient([reply(text, finish="length")])
    answer, _, events = run(model, continuation_tokens=900)
    assert answer == text + LENGTH_NOTE and len(model.requests) == 1 and "answer_continuing" not in events


def test_a_complete_answer_and_a_quick_turn_are_left_alone():
    whole = "```luau\nprint(1)\n```\nDone."
    model = FakeClient([reply(whole)])
    assert run(model, continuation_tokens=900)[0] == whole and len(model.requests) == 1
    quick = FakeClient([reply(CUT, finish="length")])
    assert run(quick)[0] == CUT and len(quick.requests) == 1, "continuation_tokens=0: the answer is returned as written"


def test_a_failed_continuation_never_loses_the_answer():
    model = FakeClient([reply(CUT, finish="length"), RuntimeError("server went away")])
    answer, _, _ = run(model, continuation_tokens=900)
    assert answer.startswith(CUT) and not stops_inside_code(answer) and "incomplete" in answer


# --- a tool call the server could not parse -------------------------------------------------------

class ServerError(Exception):
    status_code = 500


TOOL_ERROR = ServerError("Error code: 500 - {'error': {'code': 500, 'message': 'Failed to parse tool call arguments "
                         "as JSON: [json.exception.parse_error.101] parse error', 'type': 'server_error'}}")


def test_the_error_is_recognised_by_its_text_only():
    assert malformed_tool_call(TOOL_ERROR)
    assert not malformed_tool_call(ServerError("Error code: 500 - out of memory"))
    assert not malformed_tool_call(TimeoutError("timed out"))


def test_an_unparseable_tool_call_is_answered_again_without_tools():
    model = FakeClient([TOOL_ERROR, reply("```luau\nprint(1)\n```")])
    answer, _, events = run(model, github_enabled=True)          # github_enabled attaches two tools
    assert answer == "```luau\nprint(1)\n```" and "tool_call_unparseable" in events
    assert model.requests[0]["tools"] and "tools" not in model.requests[1] and "tool_choice" not in model.requests[1]
    assert model.requests[1]["messages"] == model.requests[0]["messages"]


def test_the_plain_retry_happens_once_and_only_for_that_error():
    twice = FakeClient([TOOL_ERROR, TOOL_ERROR])
    with pytest.raises(ServerError):
        run(twice, github_enabled=True)
    assert len(twice.requests) == 2
    other = FakeClient([ServerError("Error code: 500 - out of memory")])
    with pytest.raises(ServerError):
        run(other, github_enabled=True)
    no_tools = FakeClient([TOOL_ERROR])
    with pytest.raises(ServerError):
        run(no_tools)                                             # nothing to drop: the error is the answer
    assert len(no_tools.requests) == 1
