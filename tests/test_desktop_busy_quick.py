"""Desktop chat does not queue behind background answers (docs/agents/chat-speed-20261013.md).

When every slot of the main model is generating, general chat routed to it is answered by the quick
model; Roblox, code and tool turns keep the main model. Offline: fake client, fake slot probe.
"""
import star.desktop_core as core
from star.brain_router import busy_downgrade_allowed
from tests.test_model_routing import clean_process_memory, desk, reply  # noqa: F401  (fixtures)

GENERAL = "compare cats and dogs as pets"          # Auto mode: 'reasoning' profile -> star-fast


def slots_full(answer):
    async def probe(settings, model, **_):
        return answer
    return probe


def test_general_chat_moves_to_the_quick_model_when_the_main_model_is_full(desk, monkeypatch):
    monkeypatch.setattr(core, "model_slots_full", slots_full(True))
    request = desk.turn(GENERAL, [reply("Both are great.", model="star-voice")], mode="auto")
    assert request["model"] == "star-voice"
    kinds = [event.get("event") for event in desk.events]
    assert "route_busy_quick" in kinds
    selected = [e for e in desk.events if e.get("event") == "route_selected"]
    assert selected[-1]["model"] == "star-fast"       # the router's choice is still reported truthfully


def test_code_and_roblox_wait_for_the_main_model_even_when_it_is_full(desk, monkeypatch):
    monkeypatch.setattr(core, "model_slots_full", slots_full(True))
    for prompt in ("compare two python sorting algorithms", "How do I tween a part with TweenService in Roblox?"):
        request = desk.turn(prompt, [reply("Answer.", model="star-fast")], mode="auto")
        assert request["model"] == "star-fast", prompt
    assert "route_busy_quick" not in [event.get("event") for event in desk.events]


def test_free_main_model_keeps_its_route(desk, monkeypatch):
    monkeypatch.setattr(core, "model_slots_full", slots_full(False))
    request = desk.turn(GENERAL, [reply("Both are great.", model="star-fast")], mode="auto")
    assert request["model"] == "star-fast"


def test_busy_downgrade_rule_is_general_chat_only():
    assert busy_downgrade_allowed(GENERAL, "reasoning")
    assert not busy_downgrade_allowed(GENERAL, "roblox")
    assert not busy_downgrade_allowed("debug my lua script", "reasoning")
    assert not busy_downgrade_allowed("What does RemoteEvent:FireServer do in Roblox?", "reasoning")

