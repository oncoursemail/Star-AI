"""Evidence Broker tests: source integrity, exact retrieval, conservative opt-in gating."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from star import agent, tool_evidence
from star.tool_evidence import EvidenceBroker


def fixture_text() -> str:
    return ("URL: https://docs.example.test/source\n" + "ordinary evidence\n" * 800
            + "WARNING: a later section needs inspection\n"
            + "appendix data\n" * 100)


def test_long_read_only_web_evidence_is_compacted_but_exactly_retrievable():
    raw = fixture_text()
    broker = EvidenceBroker()
    summary = broker.stage("star_web_fetch", raw)
    assert summary is not None
    assert summary["status"] == "partial_preview_original_available"
    assert summary["original_characters"] == len(raw)
    assert "WARNING" in summary["preview"]
    assert "https://docs.example.test/source" in summary["preview"]
    assert len(json.dumps(summary)) < len(raw) // 2
    result = broker.read(summary["reference"], 9000, 1024)
    assert result["text"] == raw[9000:10024]
    assert result["next_offset"] == 10024
    assert result["source_is_untrusted"] is True
    assert broker.read(summary["reference"], len(raw) - 50, 100)["complete"]


def test_no_compaction_of_workspace_studio_code_proposals_errors_or_short_text():
    broker = EvidenceBroker()
    raw = fixture_text()
    for tool in ("workspace_read", "workspace_write", "workspace_edit",
                 "execute_luau", "star_candidate_code_team", "star_github_read",
                 "star_mcp_call", "star_delegate"):
        assert broker.stage(tool, raw) is None
    assert broker.stage("star_web_fetch", "small output") is None
    assert broker.count == 0

    error = {"isError": True, "content": [{"type": "text", "text": raw}]}
    wrapped = json.loads(agent.tool_payload(error, broker=broker, tool_name="star_web_fetch"))
    assert wrapped["isError"] is True
    assert wrapped["output"] == raw
    assert broker.count == 0


def test_tool_payload_only_stages_text_and_retains_legacy_behavior_without_broker():
    raw = fixture_text()
    broker = EvidenceBroker()
    good = {"isError": False, "content": [{"type": "text", "text": raw}]}
    compact = json.loads(agent.tool_payload(good, broker=broker, tool_name="star_web_fetch"))
    assert json.loads(compact["output"])["reference"] == "ev1"
    assert broker.count == 1
    original = json.loads(agent.tool_payload(good))
    assert original["output"] == raw
    image = {"isError": False, "content": [{"type": "text", "text": raw},
                                            {"type": "image", "data": "synthetic"}]}
    kept = json.loads(agent.tool_payload(image, broker=broker, tool_name="star_web_fetch"))
    assert kept["output"] == raw
    assert broker.count == 1


def test_invalid_and_stale_references_are_refused():
    broker = EvidenceBroker()
    for ref in ("ev1", "../../other", "ev4", "ev5", "", "ev1\n"):
        with pytest.raises(ValueError):
            broker.read(ref, 0)
    broker.stage("star_web_fetch", fixture_text())
    for offset, limit in ((-1, 50), (0, 0), (0, 8001),
                          (len(fixture_text()), 20), (True, 10), (0, False),
                          ("0", 20)):
        with pytest.raises(ValueError):
            broker.read("ev1", offset, limit)


def test_bounded_memory_no_eviction_of_staged_ids():
    broker = EvidenceBroker()
    data = fixture_text()
    for i in range(tool_evidence.MAX_ITEMS):
        value = broker.stage("star_web_fetch", data + str(i))
        assert value["reference"] == f"ev{i + 1}"
    assert broker.stage("star_web_fetch", data) is None
    assert broker.read("ev1", 0, 20)["text"] == data[:20]
    huge = "text" * (tool_evidence.MAX_CHARS_PER_ITEM // 4 + 1)
    assert EvidenceBroker().stage("star_web_fetch", huge) is None


def test_original_tool_output_over_cap_is_still_explicitly_marked_truncated():
    data = {"isError": False, "content": [{"type": "text", "text": "x" * 31000}]}
    old = json.loads(agent.tool_payload(data))
    assert old["output"].endswith("[TRUNCATED — narrow the next query]")


def test_execute_exposes_exact_read_after_large_web_fetch(monkeypatch):
    monkeypatch.setenv("STAR_EVIDENCE_BROKER", "on")
    from star import web_fetch
    source = fixture_text()
    assert len(source) > tool_evidence.MIN_CHARS

    async def fake_fetch(args, **_):
        return {"isError": False, "content": [{"type": "text", "text": source}]}

    monkeypatch.setattr(web_fetch, "tool_result", fake_fetch)

    def call(name, args):
        return SimpleNamespace(id="c" + name, function=SimpleNamespace(
            name=name, arguments=json.dumps(args)))

    outputs = [
        [call("star_web_fetch", {"url": "https://example.com/"})],
        [call("star_evidence_read", {"reference": "ev1", "offset": 9800, "limit": 70})],
        [],
    ]

    class Model:
        def __init__(self):
            self.requests = []

        async def create(self, **request):
            self.requests.append(request)
            tools = request.get("tools", [])
            assert "star_evidence_read" in [t["function"]["name"] for t in tools]
            actions = outputs[len(self.requests) - 1]
            return SimpleNamespace(model="fake", choices=[SimpleNamespace(
                message=SimpleNamespace(content="complete" if not actions else "",
                                        tool_calls=actions), finish_reason="stop")])

    model = Model()
    client = SimpleNamespace(chat=SimpleNamespace(completions=model))
    answer, messages, archive = asyncio.run(agent.execute(
        client=client, model="fake", prompt="Research a public web page.",
        image_paths=[], web_search_enabled=True, max_calls=3, today="2026-10-15",
        now="", context_chars=40000))
    tools = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
    assert answer == "complete" and archive == [] and len(tools) == 2
    first = json.loads(tools[0]["output"])
    assert first["reference"] == "ev1"
    assert tools[1]["isError"] is False
    exact = json.loads(tools[1]["output"])
    assert exact["text"] == source[9800:9870]


def test_execute_default_off_does_not_change_tool_catalogue(monkeypatch):
    monkeypatch.delenv("STAR_EVIDENCE_BROKER", raising=False)
    received = []

    class Model:
        async def create(self, **request):
            received.append(request)
            return SimpleNamespace(model="fake", choices=[SimpleNamespace(
                message=SimpleNamespace(content="done", tool_calls=None),
                finish_reason="stop")])

    client = SimpleNamespace(chat=SimpleNamespace(completions=Model()))
    asyncio.run(agent.execute(client=client, model="fake",
                              prompt="Look up an article.", image_paths=[],
                              web_search_enabled=True, now=""))
    names = [t["function"]["name"] for t in received[0]["tools"]]
    assert "star_web_fetch" in names
    assert "star_evidence_read" not in names
