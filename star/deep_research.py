"""Bounded parallel web evidence for an explicitly selected Research turn.

STAR asks separate search questions through its already-configured search provider.
Search results are *snippets*, never opened pages, verified facts, instructions,
credentials or grants of tool access. This module does not fetch arbitrary URLs.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from .web_search import _safe_results, search_web

MAX_QUERIES = 3
MAX_CONCURRENT_SEARCHES = 1
MAX_SOURCES = 8
_STOPWORDS = frozenset({
    "about", "after", "also", "and", "are", "being", "better", "can",
    "could", "deep", "everything", "find", "for", "from", "have", "help",
    "how", "into", "more", "much", "need", "please", "research", "should",
    "that", "the", "their", "them", "these", "this", "using", "want",
    "what", "when", "where", "which", "with", "would", "your",
})


@dataclass(frozen=True)
class ResearchBatch:
    sources: tuple[dict[str, str], ...]
    planned_queries: int
    failed_queries: int


def plan_queries(question: str) -> tuple[str, ...]:
    """Produce at most three independent search angles, without an LLM call."""
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 12000:
        raise ValueError("Research objective must contain 1–12,000 characters")
    direct = question.strip()[:600].strip()
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+#-]*", question)
    keywords: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.casefold()
        if len(key) < 3 or key in _STOPWORDS or key in seen:
            continue
        keywords.append(term[:60])
        seen.add(key)
        if len(keywords) == 14:
            break
    focus = " ".join(keywords)[:220] or direct[:220]
    candidates = (
        direct,
        f"{focus} primary sources official documentation",
        f"{focus} limitations comparisons independent evaluation",
    )
    # De-duplicate short questions whose different facets collapse.
    return tuple(dict.fromkeys(query[:600] for query in candidates))


async def research_web(
    question: str,
    *,
    provider: Callable[..., Awaitable[list[dict]]] | None = None,
) -> ResearchBatch:
    """Run at most three searches sequentially; merge distinct sources.

    A failed search does not hide evidence from successful searches. If none
    returns usable snippets, fail explicitly instead of fabricating research.
    No retries, unbounded loops, page visits or model-produced search scripts.
    """
    queries = plan_queries(question)
    if provider is None:
        # Report the actionable missing-key error before provider exceptions are
        # redacted; this path runs only after the owner selects Team + Research.
        from .providers import get_api_key
        if not get_api_key('brave') and not get_api_key('tavily'):
            raise RuntimeError('Web research needs a Brave Search or Tavily API key. Add one in Settings → AI providers.')
    search = provider if provider is not None else search_web
    if not callable(search):
        raise TypeError("A callable approved search provider is required")
    slots = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

    async def fetch(query: str) -> list[dict] | None:
        async with slots:
            try:
                raw = await search(query, limit=4)
                if not isinstance(raw, list):
                    raise ValueError("Search provider returned an invalid result")
                # Sanitize again even if the provider claims its output is safe.
                return _safe_results(raw, text_field="snippet", limit=4)
            except Exception:
                # Never expose provider exceptions: they may contain credentials.
                return None

    batches = await asyncio.gather(*(fetch(query) for query in queries))
    failures = sum(not batch for batch in batches)
    if failures == len(queries):
        raise RuntimeError("Research providers returned no usable source snippets")

    # Round-robin preserves coverage of different research angles. Prefer
    # distinct domains first, then fill remaining places with other pages.
    selected: list[dict[str, str]] = []
    seen_urls: set[tuple[str, str, str]] = set()
    seen_hosts: set[str] = set()
    for distinct_hosts in (True, False):
        for index in range(4):
            for batch in batches:
                if not batch or index >= len(batch):
                    continue
                hit = batch[index]
                parsed = urlsplit(hit["url"])
                host = (parsed.hostname or "").lower()
                identity = (host, parsed.path.rstrip("/"), parsed.query)
                if identity in seen_urls or (distinct_hosts and host in seen_hosts):
                    continue
                selected.append(hit)
                seen_urls.add(identity)
                seen_hosts.add(host)
                if len(selected) >= MAX_SOURCES:
                    return ResearchBatch(tuple(selected), len(queries), failures)
    return ResearchBatch(tuple(selected), len(queries), failures)
