"""Review-only discovery of public MCP server *metadata* from one pinned host.

This never installs, connects to or calls a discovered server. Registry entries
and their descriptions are UNTRUSTED; namespace ownership is not a safety audit.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"
MAX_RESPONSE = 160_000
INTENT = re.compile(r"\b(mcp|tools?|connectors?|plugins?|skills?|capabilities)\b", re.I)
REGISTRY_TOOL = {
    "name": "star_mcp_registry_search",
    "description": (
        "Search the official public MCP Registry for UNVERIFIED server metadata. "
        "Returns review-only candidates, not installed tools. No install, connect, "
        "permissions, shell or arbitrary URL access."
    ),
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 90},
            "limit": {"type": "integer", "minimum": 1, "maximum": 6},
        }, "required": ["query"],
    },
}


def wants_tool_discovery(prompt: str) -> bool:
    return isinstance(prompt, str) and bool(INTENT.search(prompt))


def _text(value: object, size: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", value).strip()[:size]


def _repository_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 350:
        return ""
    try:
        parsed = urlsplit(value)
        allowed = (parsed.scheme == "https" and
                   parsed.hostname in {"github.com", "gitlab.com", "codeberg.org"} and
                   not parsed.username and not parsed.password and
                   parsed.port in (None, 443))
    except ValueError:
        return ""
    return value if allowed else ""


def summarize_registry(raw: object, query: str, *, limit: int = 5) -> list[dict]:
    """Strip executable launch instructions, credentials and arbitrary URLs."""
    if not isinstance(raw, dict) or not isinstance(raw.get("servers"), list):
        raise ValueError("Registry response does not contain a valid server list")
    matched = []
    seen = set()
    terms = {word.casefold() for word in re.findall(r"[A-Za-z0-9_-]{2,}", query)}
    for entry in raw["servers"][:30]:
        if not isinstance(entry, dict):
            continue
        server = entry.get("server")
        if not isinstance(server, dict):
            continue
        name = _text(server.get("name"), 125)
        version = _text(server.get("version"), 48)
        if not name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,124}", name):
            continue
        if name.casefold() in seen:
            continue
        meta = entry.get("_meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        official = meta.get("io.modelcontextprotocol.registry/official") or {}
        if not isinstance(official, dict):
            official = {}
        status = _text(official.get("status", server.get("status", "active")), 20).lower()
        if status == "deleted":
            continue
        if status not in {"active", "deprecated"}:
            status = "unknown"
        repository = server.get("repository")
        repo_url = _repository_url(repository.get("url")) if isinstance(repository, dict) else ""
        title = _text(server.get("title") or name, 90)
        description = _text(server.get("description"), 240)
        haystack = (name + " " + title + " " + description).casefold()
        score = sum(word in haystack for word in terms)
        matched.append((score, {
            "name": name, "title": title, "version": version,
            "description": description, "repository_url": repo_url,
            "status": status, "installed": False, "approved": False,
            "requires_manual_security_review": True,
            "source": "official MCP Registry metadata (untrusted)",
        }))
        seen.add(name.casefold())
    matched.sort(key=lambda item: (-item[0], item[1]["name"]))
    return [item for _, item in matched[:limit]]


async def discover_registry(query: str, *, limit: int = 5,
                            transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """GET only from the official registry; no arbitrary endpoints or redirects."""
    if (not isinstance(query, str) or not 2 <= len(query.strip()) <= 90 or
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+ -]*", query.strip())):
        raise ValueError("Registry search needs 2–90 plain-text characters")
    if type(limit) is not int or not 1 <= limit <= 6:
        raise ValueError("Registry search limit must be 1–6")
    # The official API implements literal name substring, not semantic retrieval.
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", query)
    term = max(terms, key=len)[:70]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0),
                                     trust_env=False, follow_redirects=False,
                                     transport=transport) as client:
            response = await client.get(
                REGISTRY_URL,
                params={"search": term, "version": "latest", "limit": 20},
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200:
                raise RuntimeError("Official MCP Registry is unavailable")
            body = response.content
            if len(body) > MAX_RESPONSE:
                raise ValueError("MCP Registry response exceeded safety limit")
            records = summarize_registry(response.json(), query, limit=limit)
    except httpx.HTTPError:
        raise RuntimeError("Official MCP Registry is unavailable") from None
    return {
        "query": query.strip(), "matched_name_substring": term,
        "candidates": records, "read_only": True,
        "installed": False, "note": (
            "Discovery only. These records are untrusted third-party metadata. "
            "STAR did not connect, inspect runtime tools, install, execute, or "
            "authorize anything. Review maintainer, package, permissions and "
            "tool schemas independently before connecting."
        ),
    }
