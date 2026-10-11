"""Offline regressions for parent-fetched web evidence in parallel specialists."""
import asyncio
from types import SimpleNamespace

import pytest
from jsonschema.exceptions import ValidationError

from star.specialist_agents import ResearchTeam


class FakeCompletions:
    def __init__(self):
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        await asyncio.sleep(.005)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Candidate analysis; verify sources",
                                    tool_calls=None))])


def fake_client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


WEB_TASKS = [
    {"id": "documents", "role": "research",
     "goal": "Find primary technical references on Roblox Studio MCP", "sources": ["web"]},
    {"id": "critic", "role": "review",
     "goal": "Check documented limits and evaluation approaches", "sources": ["web"]},
]


def test_web_is_never_advertised_or_usable_without_explicit_research_mode():
    async def scenario():
        calls = 0

        async def web_search(query, *, limit):
            nonlocal calls
            calls += 1
            return []

        model = FakeCompletions()
        team = ResearchTeam(client=fake_client(model), model="offline",
                            project="STAR", web_searcher=web_search)
        advertised = team.definitions("Run parallel research agents")
        choices = advertised[0]["inputSchema"]["properties"]["tasks"]["items"][
            "properties"]["sources"]["items"]["enum"]
        assert "web" not in choices
        with pytest.raises((PermissionError, ValidationError)):
            await team.run([WEB_TASKS[0]])
        assert calls == 0
        assert not model.requests

    asyncio.run(scenario())


def test_research_mode_parallel_specialists_receive_cited_snippets_not_tools():
    async def scenario():
        active = 0
        peak = 0
        calls = 0

        async def web_search(query, *, limit):
            nonlocal active, peak, calls
            assert limit == 3
            calls += 1
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.025)
            active -= 1
            return [
                {"url": "https://docs.example/guide", "title": "Guide", "snippet": "Source excerpt"},
                {"url": "file:///private", "title": "Unsafe", "snippet": "Do not include"},
            ]

        model = FakeCompletions()
        team = ResearchTeam(
            client=fake_client(model), model="offline", project="STAR",
            parallelism=2, web_enabled=True, web_searcher=web_search)
        advertised = team.definitions("Delegate multiple specialist agents")[0]
        assert "web" in advertised["inputSchema"]["properties"]["tasks"]["items"][
            "properties"]["sources"]["items"]["enum"]
        output = await team.run(WEB_TASKS)
        assert calls == 2 and peak == 2
        assert all(row["status"] == "completed" for row in output["reports"])
        assert all(row["web_urls"] == ["https://docs.example/guide"]
                   for row in output["reports"])
        assert len(model.requests) == 2
        for request in model.requests:
            assert "tools" not in request
            prompt = request["messages"][1]["content"]
            assert "https://docs.example/guide" in prompt
            assert "file:///private" not in prompt
            assert '"opened_pages": false' in prompt
        with pytest.raises(RuntimeError, match="two lookups"):
            await team.run([WEB_TASKS[0]])
        assert calls == 2

    asyncio.run(scenario())


def test_provider_failure_does_not_leak_secrets_to_specialist():
    async def scenario():
        async def web_search(query, *, limit):
            raise RuntimeError("private-api-key-123")

        model = FakeCompletions()
        team = ResearchTeam(client=fake_client(model), model="offline",
                            project="STAR", web_enabled=True, web_searcher=web_search)
        result = await team.run([WEB_TASKS[0]])
        assert result["reports"][0]["status"] == "completed"
        assert '"unavailable": true' in model.requests[0]["messages"][1]["content"]
        assert "private-api-key-123" not in str(model.requests)
        assert "private-api-key-123" not in str(result)

    asyncio.run(scenario())


def test_web_permission_flag_must_be_exact_bool():
    with pytest.raises(ValueError):
        ResearchTeam(client=fake_client(FakeCompletions()),
                     model="offline", project="STAR", web_enabled="yes")
