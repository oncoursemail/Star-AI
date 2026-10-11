"""Offline coverage for bounded, parallel, source-grounded research."""
import asyncio

import pytest

from star.deep_research import (
    MAX_CONCURRENT_SEARCHES, MAX_QUERIES, MAX_SOURCES,
    plan_queries, research_web,
)
from star.web_search import source_context


def test_research_plan_is_deterministic_bounded_and_question_specific():
    goal = "Research Roblox Luau types and Studio MCP integration quality"
    first = plan_queries(goal)
    assert first == plan_queries(goal)
    assert len(first) == MAX_QUERIES
    assert first[0] == goal
    assert "Luau" in first[1] and "official documentation" in first[1]
    assert "independent evaluation" in first[2]
    assert all(0 < len(query) <= 600 for query in first)
    with pytest.raises(ValueError):
        plan_queries(" ")
    with pytest.raises(ValueError):
        plan_queries("a" * 12001)
    with pytest.raises(ValueError):
        plan_queries(None)


def test_research_runs_two_searches_concurrently_and_merges_provenance():
    async def scenario():
        active = 0
        peak = 0
        queries = []

        async def search(query, *, limit):
            nonlocal active, peak
            assert limit == 4
            queries.append(query)
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.03)
            active -= 1
            host = "official.example" if "official documentation" in query else (
                "review.example" if "independent evaluation" in query else "topic.example")
            return [
                {"url": f"https://{host}/first", "title": "Reference",
                 "snippet": "Short, unverified excerpt"},
                {"url": f"https://{host}/second", "title": "More",
                 "snippet": "Another excerpt"},
            ]

        output = await research_web("Study Roblox Luau source analysis", provider=search)
        assert len(queries) == MAX_QUERIES
        assert peak == MAX_CONCURRENT_SEARCHES
        assert output.planned_queries == 3
        assert output.failed_queries == 0
        assert len(output.sources) == 6
        assert len({row["url"] for row in output.sources}) == 6
        assert "official.example" in str(output.sources)
        text = source_context(list(output.sources))
        assert "untrusted" in text
        assert "entire articles" in text

    asyncio.run(scenario())


def test_partial_failures_are_counted_and_duplicate_urls_removed():
    async def scenario():
        async def search(query, *, limit):
            if "official documentation" in query:
                raise RuntimeError("apikey=never-echo")
            if "independent evaluation" in query:
                return [{"url": "http://insecure.example/post", "snippet": "Unsafe"}]
            return [
                {"url": "https://one.example/article#section", "snippet": "A"},
                {"url": "https://one.example/article#other", "snippet": "B"},
                {"url": "https://two.example/page", "snippet": "C"},
            ]

        result = await research_web("Roblox DataStore code review", provider=search)
        assert result.failed_queries == 2
        assert len(result.sources) == 2
        assert len({item["url"].split("#")[0] for item in result.sources}) == 2
        assert "apikey" not in str(result)

    asyncio.run(scenario())


def test_domain_diversity_is_selected_before_repeated_hosts():
    async def scenario():
        async def search(query, *, limit):
            if "official documentation" in query:
                return [{"url": "https://docs.example/guide", "snippet": "A"}]
            if "independent evaluation" in query:
                return [{"url": "https://review.example/analysis", "snippet": "B"}]
            return [{"url": f"https://same.example/{index}", "snippet": "C"}
                    for index in range(4)]

        report = await research_web("Roblox runtime architecture", provider=search)
        assert len(report.sources) <= MAX_SOURCES
        assert report.sources[0]["url"] == "https://same.example/0"
        assert report.sources[1]["url"] == "https://docs.example/guide"
        assert report.sources[2]["url"] == "https://review.example/analysis"

    asyncio.run(scenario())


def test_no_results_fails_without_leaking_errors_or_retrying():
    async def scenario():
        calls = 0

        async def search(query, *, limit):
            nonlocal calls
            calls += 1
            raise PermissionError("Bearer very-private-test-token")

        with pytest.raises(RuntimeError, match="no usable source snippets") as error:
            await research_web("Check Roblox docs", provider=search)
        assert calls == 3
        assert "private-test-token" not in str(error.value)

    asyncio.run(scenario())


def test_research_cancellation_propagates_without_more_work():
    async def scenario():
        started = asyncio.Event()

        async def search(query, *, limit):
            started.set()
            await asyncio.sleep(10)
            return []

        task = asyncio.create_task(research_web("Compare Roblox security", provider=search))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
