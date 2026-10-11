"""scripts/measure_first_token.py builds its two layouts the way the app did and does."""
import importlib.util
import json
from pathlib import Path

import httpx

from star.agent import FAST_RULES, RULES
from star.desktop_core import Settings

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_first_token.py"
spec = importlib.util.spec_from_file_location("measure_first_token", SCRIPT)
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)

TURNS = [("How do I tween a door?", "Use TweenService."), ("And close it?", "Reverse the tween.")]


def test_legacy_layout_keeps_the_conversation_inside_the_system_message():
    messages = measure.legacy_messages(TURNS, "Next question")
    assert [m["role"] for m in messages] == ["system", "user"]
    system = messages[0]["content"]
    assert system.startswith(RULES) and "RECENT CONVERSATION" in system and "assistant: Reverse the tween." in system
    # The start of the request changes every turn: that is the defect being measured.
    assert measure.legacy_messages(TURNS[:1], "x")[0] != messages[0]


def test_stable_layout_is_append_only():
    settings = Settings(provider="star_server", server_endpoint="http://192.168.50.20:8080/v1", model="star-fast")
    first = measure.stable_messages(settings, TURNS[:1], TURNS[1][0])
    second = measure.stable_messages(settings, TURNS, "Next question")
    assert first[0] == second[0] == {"role": "system", "content": FAST_RULES}
    assert second[1:4] == [*first[1:3], {"role": "user", "content": TURNS[1][0]}]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user", "assistant", "user"]


def test_chat_reads_server_timings_and_never_prints_the_key(capsys):
    frames = [{"choices": [{"delta": {"content": "Hel"}}]}, {"choices": [{"delta": {"content": "lo"}}]},
              {"choices": [], "timings": {"prompt_n": 12, "cache_n": 340, "prompt_per_second": 48.5,
                                          "predicted_n": 2, "predicted_per_second": 4.61}}]
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        body = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames) + "data: [DONE]\n\n"
        return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})
    server = measure.Server("http://192.168.50.20:8080/v1", "star-fast", "sk-secret-0123456789", 30)
    server.http = httpx.Client(transport=httpx.MockTransport(handle), headers=server.http.headers)
    row = server.chat([{"role": "user", "content": "hi"}], max_tokens=8, extras={"cache_prompt": True, "id_slot": 1})
    assert row["text"] == "Hello" and row["prompt_read"] == 12 and row["prompt_cached"] == 340
    assert row["prompt_tok_s"] == 48.5 and row["gen_tok_s"] == 4.61
    assert seen[0]["cache_prompt"] is True and seen[0]["id_slot"] == 1 and seen[0]["stream"] is True
    measure.show("turn", row | {"text": ""})
    assert "sk-secret" not in capsys.readouterr().out
