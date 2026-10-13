"""STAR knows the time: the per-turn line (end of the context) and the star_clock tool."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from star import clock
from star.agent import execute, volatile_context
from star.context_layout import CONTEXT_CLOSE

FIXED = datetime(2026, 10, 13, 13, 5, tzinfo=timezone(timedelta(hours=-5), "Central Daylight Time"))


def _has_iana() -> bool:
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("Asia/Tokyo")
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def no_server_clock():
    clock.forget_server_clock()
    yield
    clock.forget_server_clock()


def test_now_line_has_local_date_time_zone_and_utc():
    line = clock.now_line(FIXED)
    assert line == "Now: Tuesday 2026-10-13 13:05 CDT (UTC-05:00) on the owner's PC; 18:05 UTC."


def test_server_clock_is_mentioned_only_when_it_differs():
    assert "STAR Server" not in clock.now_line(FIXED, offset=30)
    line = clock.now_line(FIXED, offset=600)
    assert "STAR Server clock reads 2026-10-13 18:15 UTC (+10 min)" in line


def test_server_clock_is_read_from_an_http_date_header():
    now = FIXED.timestamp()
    clock.observe_server_date("Tue, 13 Oct 2026 18:15:00 GMT", now=now)
    assert clock.server_offset() == pytest.approx(600, abs=1)
    clock.observe_server_date("not a date")          # ignored, never raises
    assert clock.server_offset() == pytest.approx(600, abs=1)
    assert "+10 min" in clock.now_line(FIXED)


def test_server_observation_expires():
    ticks = iter([0.0, 10_000.0])
    clock.observe_server_date("Tue, 13 Oct 2026 18:15:00 GMT", now=FIXED.timestamp(), monotonic=lambda: 0.0)
    assert clock.server_offset(monotonic=lambda: 10_000.0) is None
    del ticks


def test_the_time_line_is_the_last_line_of_the_context_block():
    block = volatile_context([("WEB SEARCH", "snippet")], now="Now: X", today="2026-10-13")
    lines = block.splitlines()
    assert lines[-1] == CONTEXT_CLOSE and lines[-2] == "Now: X"
    # Plain chat with nothing else still gets the time line.
    plain = volatile_context([], now="Now: X")
    assert plain.splitlines()[1:] == ["Now: X", CONTEXT_CLOSE]
    assert volatile_context([], today="2026-10-13") == ""


class Models:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.replies.pop(0)


def reply(content=None, calls=None):
    return SimpleNamespace(model="m", choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls), finish_reason="stop")])


def test_execute_appends_the_time_after_the_user_words_and_keeps_the_system_prefix_stable():
    async def run():
        models = Models(reply("It is 13:05."), reply("Again."))
        client = SimpleNamespace(chat=SimpleNamespace(completions=models))
        await execute(client=client, model="m", prompt="what time is it", image_paths=[], now="Now: A")
        await execute(client=client, model="m", prompt="what time is it", image_paths=[], now="Now: B")
        first, second = models.requests
        assert first["messages"][0] == second["messages"][0]          # byte-stable system prefix
        assert "Now:" not in first["messages"][0]["content"]
        text = first["messages"][-1]["content"][0]["text"]
        assert text.startswith("what time is it") and text.rstrip().endswith("Now: A\n" + CONTEXT_CLOSE)
        assert "tools" not in first                                       # plain question: no clock tool
    asyncio.run(run())


def test_rules_tell_star_to_use_tools_instead_of_refusing():
    from star.agent import FAST_RULES, RULES
    for rules in (RULES, FAST_RULES):
        flat = " ".join(rules.lower().split())
        assert "never say you lack real-time data" in flat
        assert "cite source urls" in flat
        assert "Truthfully report uncertainty" in rules


@pytest.mark.parametrize("prompt", ["what time is it in Tokyo?", "convert 3pm EST to London time",
                                    "how many days until Christmas", "what day was 2026-01-01",
                                    "is UTC+5 ahead of me", "what timezone is Sydney in"])
def test_time_questions_get_the_clock_tool(prompt):
    assert clock.wants_clock(prompt)


@pytest.mark.parametrize("prompt", ["what time is it", "make a day/night cycle script",
                                    "how long does task.wait take", "Calculate 2 + 2", "watch this video"])
def test_other_prompts_do_not(prompt):
    assert not clock.wants_clock(prompt)


def test_execute_runs_the_clock_tool_when_the_model_asks():
    call = SimpleNamespace(id="c1", function=SimpleNamespace(
        name="star_clock", arguments=json.dumps({"action": "now", "zones": ["UTC"]})))

    async def run():
        models = Models(reply(None, [call]), reply("done"))
        client = SimpleNamespace(chat=SimpleNamespace(completions=models))
        events = []
        await execute(client=client, model="m", prompt="what time is it in UTC+0 vs time zones", image_paths=[],
                      now="", on_event=events.append)
        assert [t["function"]["name"] for t in models.requests[0]["tools"]] == ["star_clock"]
        tool_message = [m for m in models.requests[1]["messages"] if m["role"] == "tool"][0]
        output = json.loads(json.loads(tool_message["content"])["output"])
        assert output["results"][0]["zone"] == "UTC"
        assert {"event": "tool_finished", "tool": "star_clock", "is_error": False} in events
    asyncio.run(run())


def test_clock_now_and_offsets():
    out = clock.run_clock({"action": "now", "zones": ["UTC", "UTC+05:30", "-03"]}, now=FIXED)
    assert [r["time"] for r in out["results"]] == ["Tuesday 2026-10-13 18:05", "Tuesday 2026-10-13 23:35",
                                                  "Tuesday 2026-10-13 15:05"]


def test_clock_convert_add_diff():
    out = clock.run_clock({"action": "convert", "time": "2026-10-13T09:00", "from_zone": "UTC",
                           "zones": ["UTC-05:00"]}, now=FIXED)
    assert out["results"][0]["time"] == "Tuesday 2026-10-13 04:00"
    out = clock.run_clock({"action": "convert", "time": "3:30 pm", "from_zone": "UTC", "zones": ["UTC+01:00"]},
                          now=FIXED)
    assert out["results"][0]["time"].endswith("16:30")
    out = clock.run_clock({"action": "add", "time": "2026-10-13", "from_zone": "UTC", "days": 100}, now=FIXED)
    assert out["result"]["time"] == "Thursday 2027-01-21 00:00"
    out = clock.run_clock({"action": "diff", "time": "2026-10-13", "end": "2026-12-25", "from_zone": "UTC"},
                          now=FIXED)
    assert out["total_days"] == 73 and out["span"].startswith("73 days")


def test_clock_errors_are_tool_errors_not_exceptions():
    assert clock.tool_result({"action": "now", "zones": ["Nowhere/Atlantis"]})["isError"] is True
    assert clock.tool_result({"action": "fly"})["isError"] is True
    assert clock.tool_result({"action": "add", "days": "many"})["isError"] is True
    assert clock.tool_result({"action": "convert", "time": "25:99"})["isError"] is True


@pytest.mark.skipif(not _has_iana(), reason="IANA zones need the tzdata package on Windows")
def test_iana_and_city_names():
    out = clock.run_clock({"action": "now", "zones": ["Asia/Tokyo", "London"]}, now=FIXED)
    assert out["results"][0]["time"] == "Wednesday 2026-10-14 03:05"
    assert out["results"][1]["zone"] == "Europe/London" and out["results"][1]["time"].endswith("19:05")
