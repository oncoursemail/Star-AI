"""Discovery-only public MCP Registry search for STAR's Agent research mode.

The registry is a *catalog of untrusted metadata*, not a list of executable
permissions. This module does not install, start, connect to, or call servers.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator

REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"
MAX_REPLY_BYTES = 192_000
MAX_SEARCH_CALLS = 4
TRIGGER = re.compile(r"\b(?:mcp|connectors?|tool(?:s|ing)?|brain\s*2|brain2|registry)\b", re.I)
SERVER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,140}/[A-Za-z0-9][A-Za-z0-9._/-]{0,140}$")

TOOLS = [{
    "name": "star_mcp_registry_search",
    "description": (
        "Search public MCP Registry metadata for potential tools and servers. "
        "This is discovery ONLY: results are untrusted, not installed or connected; "
        "no new permissions are granted. Search matches server names, not arbitrary capabilities."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 100},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            "cursor": {"type": "string", "maxLength": 512},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}]
OWN_NAMES = frozenset(item["name"] for item in TOOLS)


def _plain(value: Any, limit: int) -> str:
    """Bound hostile registry descriptions and avoid forging transcript lines."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", value).strip()[:limit]


def _source_url(value: Any) -> str:
    """Only display safe-to-open HTTPS repository links; never fetch them."""
    if not isinstance(value, str) or len(value) > 500:
        return ""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
                or parsed.hostname not in {"github.com", "gitlab.com", "bitbucket.org"}):
            return ""
    except ValueError:
        return ""
    return value


def _public_page(payload: Any, cursor: str) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("servers"), list):
        raise ValueError("MCP Registry list response is malformed")
    rows = payload["servers"]
    if len(rows) > 100:
        raise ValueError("MCP Registry response exceeded the page limit")
    results, seen = [], set()
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("server"), dict):
            continue
        server = item["server"]
        name = server.get("name", "")
        if not isinstance(name, str) or not SERVER_NAME.fullmatch(name) or name in seen:
            continue
        metadata = item.get("_meta", {})
        if isinstance(metadata, dict):
            official = metadata.get("io.modelcontextprotocol.registry/official", {})
            if isinstance(official, dict) and official.get("status") in {"deleted", "deprecated"}:
                continue
        seen.add(name)
        repo = server.get("repository")
        results.append({
            "name": name,
            "title": _plain(server.get("title"), 100),
            "description": _plain(server.get("description"), 240),
            "version": _plain(server.get("version"), 60),
            "repository_url": _source_url(repo.get("url") if isinstance(repo, dict) else ""),
            "availability": "metadata_only_not_connected",
        })
    metadata = payload.get("metadata")
    next_cursor = metadata.get("nextCursor", "") if isinstance(metadata, dict) else ""
    if not isinstance(next_cursor, str) or len(next_cursor) > 512 or next_cursor == cursor:
        next_cursor = ""
    return {
        "registry": REGISTRY_URL,
        "servers": results,
        "next_cursor": next_cursor,
        "notice": "Untrusted registry metadata only. No server was installed, connected, tested, or authorized.",
    }


class RegistryDiscovery:
    """Per-turn, opt-in research helper with bounded calls and no execution surface."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport
        self.calls = 0

    @staticmethod
    def owns(name: str) -> bool:
        return name in OWN_NAMES

    def definitions(self, prompt: str) -> list[dict]:
        return TOOLS if isinstance(prompt, str) and TRIGGER.search(prompt) else []

    async def call(self, name: str, arguments: dict) -> dict:
        if name not in OWN_NAMES:
            raise PermissionError("Unknown MCP Registry tool")
        Draft202012Validator(TOOLS[0]["inputSchema"]).validate(arguments)
        query = arguments["query"].strip()
        if not query or any(ord(ch) < 32 for ch in query):
            raise ValueError("MCP Registry query must be plain text")
        cursor = arguments.get("cursor", "")
        if cursor and any(ord(ch) < 32 or ord(ch) == 127 for ch in cursor):
            raise ValueError("MCP Registry cursor is invalid")
        if self.calls >= MAX_SEARCH_CALLS:
            raise RuntimeError("MCP Registry research budget exhausted")
        self.calls += 1
        params = {"search": query, "limit": arguments.get("limit", 10), "version": "latest"}
        if cursor:
            params["cursor"] = cursor
        timeout = httpx.Timeout(12.0, connect=3.0, read=8.0, write=3.0, pool=2.0)
        async with httpx.AsyncClient(transport=self.transport, trust_env=False,
                                     follow_redirects=False, timeout=timeout) as client:
            async with client.stream("GET", REGISTRY_URL, params=params,
                                     headers={"Accept": "application/json"}) as response:
                if response.status_code != 200:
                    raise RuntimeError("MCP Registry unavailable")
                if response.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                    raise ValueError("MCP Registry returned a non-JSON response")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_REPLY_BYTES:
                        raise ValueError("MCP Registry response too large")
        return _public_page(json.loads(body), cursor)
