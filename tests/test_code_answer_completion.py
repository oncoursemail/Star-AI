"""Fake-provider regressions on the real STAR agent and desktop provider paths."""
import asyncio
from types import SimpleNamespace

from star import code_answer_completion as completion
from star.agent import execute


CUT_FUNCTION = (
    "Here is the module.\n\n```luau\nlocal function calculate()\n"
    "    local count = 3\n    pri"
)


def reply(text, finish="stop", calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=text, tool_calls=calls), finish_reason=finish,
    )])


def chunk(text=None, finish=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text, tool_calls=None), finish_reason=finish,
    )])


class Stream:
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for item in self.chunks:
            yield item


class Model:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def run(model, **kwargs):
    events = []
    result = asyncio.run(execute(
        client=model, model="fake", prompt="Write a Luau module.", image_paths=[],
        on_event=events.append, **kwargs,
    ))
    return result, events


def test_option_is_off_by_default(monkeypatch):
    monkeypatch.delenv(completion.ENV_VAR, raising=False)
    assert not completion.enabled()
    assert not completion.enabled({completion.ENV_VAR: "yes"})
    assert completion.enabled({completion.ENV_VAR: " ON "})
    model = Model([reply(CUT_FUNCTION, finish="length")])
    (answer, _, _), events = run(model)
    assert answer == CUT_FUNCTION and len(model.requests) == 1
    assert not any(item["event"] == "answer_continuing" for item in events)


def test_cut_in_middle_of_function_is_continued_on_real_provider_path():
    model = Model([
        reply(CUT_FUNCTION, finish="length"),
        reply("```luau\n    print(count)\nend\n```\n", finish="stop"),
    ])
    (answer, _, _), events = run(model, complete_code_answers=True)
    assert answer == (
        "Here is the module.\n\n```luau\nlocal function calculate()\n"
        "    local count = 3\n    print(count)\nend\n```\n"
    )
    assert not completion.open_fence(answer)
    assert len(model.requests) == 2
    assert events.count({"event": "answer_continuing"}) == 1
    followup = model.requests[1]
    assert followup["max_tokens"] == 900
    assert "tools" not in followup and "tool_choice" not in followup
    assert followup["messages"][:-2] == model.requests[0]["messages"]
    assert followup["messages"][-2]["content"].endswith("    local count = 3\n")
    assert "pri" in followup["messages"][-1]["content"]


def test_cut_inside_luau_string_replaces_entire_line():
    cut = '```luau\nlocal function message()\n    local text = "hel'
    model = Model([
        reply(cut, finish="length"),
        reply('```luau\n    local text = "hello"\n    return text\nend\n```\n'),
    ])
    (answer, _, _), _ = run(model, complete_code_answers=True)
    assert answer == '```luau\nlocal function message()\n    local text = "hello"\n    return text\nend\n```\n'
    assert answer.count("local text") == 1
    assert not completion.open_fence(answer)


def test_complete_answer_is_byte_identical_and_costs_no_extra_call():
    whole = "```luau\nprint('ok')\n```\n\nDone."
    model = Model([reply(whole)])
    (answer, _, _), events = run(model, complete_code_answers=True)
    assert answer == whole
    assert len(model.requests) == 1
    assert not any(event["event"] == "answer_continuing" for event in events)
    assert model.requests[0]["max_tokens"] == 1600


def test_two_consecutive_length_cuts_recover_in_three_calls():
    model = Model([
        reply(CUT_FUNCTION, finish="length"),
        reply("```luau\n    for i = 1, count do\n        pri", finish="length"),
        reply("```luau\n        print(i)\n    end\nend\n```\n"),
    ])
    (answer, _, _), events = run(model, complete_code_answers=True)
    assert len(model.requests) == 3
    assert events.count({"event": "answer_continuing"}) == 2
    assert "for i = 1, count do" in answer
    assert "print(i)\n    end\nend\n```" in answer
    assert "pri\n" not in answer
    assert completion.open_fence(answer) is None


def test_two_cuts_without_closing_fence_get_honest_warning():
    model = Model([
        reply(CUT_FUNCTION, finish="length"),
        reply("```luau\n    for i = 1, count do\n", finish="length"),
        reply("```luau\n        print(i)\n", finish="length"),
    ])
    (answer, _, _), events = run(model, complete_code_answers=True)
    assert len(model.requests) == 3
    assert events.count({"event": "answer_continuing"}) == 2
    assert completion.open_fence(answer) is None
    assert answer.endswith(completion.INCOMPLETE_CODE)
    assert "do not run it as-is" in answer


def test_failed_provider_preserves_partial_code_with_warning():
    model = Model([reply(CUT_FUNCTION, finish="length"), RuntimeError("provider unavailable")])
    (answer, _, _), _ = run(model, complete_code_answers=True)
    assert len(model.requests) == 2
    assert answer.startswith(CUT_FUNCTION)
    assert answer.endswith(completion.INCOMPLETE_CODE)
    assert completion.open_fence(answer) is None


def test_cut_in_prose_after_closed_code_is_continued():
    part = "```luau\nprint('hello')\n```\nThen it rea"
    model = Model([reply(part, finish="length"), reply("ches the players.")])
    (answer, _, _), _ = run(model, complete_code_answers=True)
    assert answer == part + "ches the players."
    assert len(model.requests) == 2


def test_open_fence_is_detected_without_length_reason_and_inline_markers_are_ignored():
    part = "Use inline ``` here.\n\n~~~lua\nprint(1)\n"
    assert completion.open_fence(part) == ("~", 3, part.index("~~~"))
    assert completion.open_fence("Use ``` inline, but no code fence") is None
    assert completion.open_fence("~~~~lua\nprint(1)\n~~~") is not None
    assert completion.open_fence("~~~lua\nprint(1)\n~~~") is None
    model = Model([reply("```lua\nprint(1)\n", finish="stop"), reply("```lua\n```\n")])
    (answer, _, _), _ = run(model, complete_code_answers=True)
    assert completion.open_fence(answer) is None


def test_streamed_cut_is_never_shown_before_continuation_finishes():
    model = Model([
        Stream([
            chunk("Here is the module.\n\n```luau\nlocal function calculate()\n"),
            chunk("    local count = 3\n    pri", finish="length"),
        ]),
        reply("```luau\n    print(count)\nend\n```\n"),
    ])
    (answer, messages, _), events = run(model, complete_code_answers=True, stream_tokens=True)
    deltas = [(i, event["text"]) for i, event in enumerate(events) if event["event"] == "assistant_delta"]
    continuing_at = next(i for i, event in enumerate(events) if event["event"] == "answer_continuing")
    assert len(deltas) == 1 and deltas[0] == (continuing_at + 1, answer)
    assert "    pri\n" not in answer, "the truncated line must be replaced, not appended"
    assert model.requests[0]["stream"] is True
    assert "stream" not in model.requests[1]
    assert messages[-1] == {"role": "assistant", "content": answer}


def test_streamed_complete_answer_has_identical_text_without_followups():
    whole = "```luau\nprint(1)\n```\nDone."
    model = Model([Stream([chunk("```luau\nprint(1)\n"), chunk("```\nDone.", finish="stop")])])
    (answer, messages, _), events = run(model, complete_code_answers=True, stream_tokens=True)
    assert answer == whole and len(model.requests) == 1
    assert "".join(e["text"] for e in events if e["event"] == "assistant_delta") == whole
    assert messages[-1]["content"] == whole


def test_tool_schemas_are_not_forwarded_to_recovery():
    model = Model([reply(CUT_FUNCTION, finish="length"),
                   reply("```luau\n    print(count)\nend\n```\n")])
    (answer, _, _), _ = run(model, complete_code_answers=True, github_enabled=True)
    assert completion.open_fence(answer) is None
    assert model.requests[0]["tools"]
    assert "tools" not in model.requests[1]
    assert model.requests[1]["messages"][-1]["role"] == "user"


def test_automatic_environment_switch_drives_desktop_run_task(monkeypatch, desk):
    from star.desktop_core import run_task

    monkeypatch.setenv(completion.ENV_VAR, "on")
    monkeypatch.setenv("STAR_SKILL_PACKS", "off")
    desk.models.responses = [
        reply(CUT_FUNCTION, finish="length"),
        reply("```luau\n    print(count)\nend\n```\n"),
    ]
    answer = run_task(desk.settings, "Write a Luau module.", chat_id=desk.chat, mode="fast")
    assert answer.endswith("end\n```\n")
    assert len(desk.models.requests) == 2
    assert "max_tokens" in desk.models.requests[1]
    assert completion.open_fence(answer) is None


from test_first_token import desk  # noqa: E402, F401 - real run_task fake-desktop fixture
