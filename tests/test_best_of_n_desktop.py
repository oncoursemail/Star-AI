"""Best-of-N in a real desktop turn (star/desktop_core.run_task), offline: fake STAR Server client and slot probe."""
import asyncio

import star.best_of_n as bon
from star.agent import execute
from star.react_shell import PERMITTED_SETTINGS, sanitize_event
from tests.test_model_routing import Client, Models, clean_process_memory, desk, reply  # noqa: F401  (fixtures)

PROMPT = ("Write a Roblox Luau ModuleScript Inventory with add, remove and count. It must validate the amount and "
          "remove must fail without changing anything when there are not enough items.")
GOOD = ("```luau\nlocal Inventory = {}\nfunction Inventory.count(inv, item)\n\treturn inv[item] or 0\nend\n"
        "return Inventory\n```\n")
BUSY_LOOP = "```luau\nwhile true do\n\tlocal x = 1\nend\n```\n"


def row_parts(row):
    return [str(part) for part in tuple(row)]


def free(count):
    async def probe(settings, model):
        return count
    return probe


def by_model(table):
    """A response chosen by the request's model, so concurrent candidates get stable answers."""
    def answer(kwargs):
        return reply(table[kwargs["model"]], model=kwargs["model"])
    return answer


def test_code_turn_with_the_setting_on_keeps_the_version_that_passes(desk, monkeypatch):
    monkeypatch.delenv("STAR_BON_SSH", raising=False)
    monkeypatch.delenv("STAR_EVAL_SSH", raising=False)
    monkeypatch.setattr(bon, "probe_free_slots", free(2))
    desk.settings.best_of_n = "auto"
    # The main answer (star-fast, temperature 0) has no code; the quick model's candidate has working code.
    answers = by_model({"star-fast": "Use a table keyed by item name.", "star-voice": GOOD})
    desk.turn(PROMPT, [answers] * 6, mode="auto")
    body = [row for row in desk.chats.recent("STAR", 4, chat_id=desk.chat, include_events=False)
            if "assistant" in tuple(row)][-1]
    body = next(part for part in row_parts(body) if "```" in part or "Best of" in part)
    assert "local Inventory = {}" in body and "**Best of" in body and "by STAR:**" in body
    requests = desk.models.requests
    main = [r for r in requests if r["temperature"] == 0 and r["model"] == "star-fast"]
    extra = [r for r in requests if r["temperature"] > 0]
    assert main and extra
    assert all(r["messages"] == main[0]["messages"] for r in extra)       # the same request, other temperatures
    assert all(r["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False for r in extra)
    assert all("id_slot" not in r["extra_body"] for r in extra)           # the server places candidates
    kinds = [e.get("event") for e in desk.events]
    assert "best_of_n_started" in kinds and "best_of_n_selected" in kinds


def test_setting_off_or_plain_chat_runs_exactly_one_request(desk, monkeypatch):
    monkeypatch.setattr(bon, "probe_free_slots", free(2))
    desk.turn(PROMPT, [reply(GOOD, model="star-fast")], mode="auto")
    assert len(desk.models.requests) == 1
    desk.settings.best_of_n = "auto"
    desk.turn("hello there", [reply("Hi!", model="star-voice")])
    assert len(desk.models.requests) == 2
    assert not [e for e in desk.events if str(e.get("event", "")).startswith("best_of_n")]


def test_busy_server_writes_one_version(desk, monkeypatch):
    monkeypatch.setattr(bon, "probe_free_slots", free(0))
    desk.settings.best_of_n = "auto"
    desk.turn(PROMPT, [reply(GOOD, model="star-fast")], mode="auto")
    assert len(desk.models.requests) == 1
    assert "best_of_n_skipped" in [e.get("event") for e in desk.events]


def test_execute_reports_its_first_request_once():
    seen = []
    models = Models([reply("Hi!")])
    answer, _, _ = asyncio.run(execute(client=Client(models), model="m", prompt="hello there", image_paths=[],
                                       mode="fast", today="2026-10-13", on_first_request=seen.append))
    assert answer == "Hi!" and len(seen) == 1
    assert seen[0]["messages"][-1]["role"] == "user" and seen[0]["max_tokens"] == 1600

    def broken(request):
        raise RuntimeError("observer failed")
    models = Models([reply("Still fine.")])
    answer, _, _ = asyncio.run(execute(client=Client(models), model="m", prompt="hello there", image_paths=[],
                                       mode="fast", today="2026-10-13", on_first_request=broken))
    assert answer == "Still fine."


def test_progress_events_reach_the_ui_as_numbers_only():
    assert sanitize_event({"event": "best_of_n_started", "n": 3}) == {"phase": "Writing 3 versions to test"}
    assert sanitize_event({"event": "best_of_n_checked", "index": 2, "passed": 5, "ran": 6}) == {
        "phase": "Checked version 2 (5/6 checks)"}
    assert sanitize_event({"event": "best_of_n_selected", "index": 2, "passed": 6, "ran": 6, "answer": "secret"}) == {
        "phase": "Keeping version 2 (6/6 checks)"}
    assert sanitize_event({"event": "best_of_n_candidate", "index": 99}) == {"phase": "Testing versions"}
    assert {"best_of_n", "best_of_n_max"} <= PERMITTED_SETTINGS


def test_settings_validate_best_of_n(desk):
    import pytest
    settings = desk.settings
    settings.best_of_n, settings.best_of_n_max = "auto", 8
    settings.validate()
    for value, maximum in (("always", 4), ("auto", 1), ("auto", 9), ("auto", "4")):
        settings.best_of_n, settings.best_of_n_max = value, maximum
        with pytest.raises(ValueError):
            settings.validate()
