"""Discord permissions, bounded ephemeral conversation memory, and safe formatting.

No Discord or GPU dependency here, so access-control tests can run offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import time
from typing import Callable

MAX_PROMPT = 1600
MAX_REPLY = 18000
MAX_EMBED_DESCRIPTION = 3500
MAX_AUDIO_TEXT = 500
MAX_ACTIVE_SESSIONS = 64
_MAX_SNOWFLAKE = 2**64 - 1


def _ids(raw: str, key: str) -> frozenset[int]:
    if not raw.strip():
        return frozenset()
    items = raw.split(",")
    if len(items) > 100 or any(not re.fullmatch(r"[0-9]{1,20}", item.strip()) for item in items):
        raise ValueError(f"{key} must contain comma-separated Discord numeric IDs")
    result = frozenset(int(item.strip()) for item in items)
    if any(value < 1 or value > _MAX_SNOWFLAKE for value in result):
        raise ValueError(f"{key} contains an invalid Discord ID")
    return result


@dataclass(frozen=True)
class AccessPolicy:
    """Discord IDs identify the owner, not any tools/files they may use.

    All Discord-originated model calls remain chat-only regardless of identity.
    """

    owners: frozenset[int]
    guilds: frozenset[int]
    channels: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        if not self.owners:
            raise ValueError("STAR_DISCORD_OWNER_IDS is required (fail-closed)")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "AccessPolicy":
        source = os.environ if env is None else env
        return cls(
            owners=_ids(source.get("STAR_DISCORD_OWNER_IDS", ""), "STAR_DISCORD_OWNER_IDS"),
            guilds=_ids(source.get("STAR_DISCORD_GUILD_IDS", ""), "STAR_DISCORD_GUILD_IDS"),
            channels=_ids(source.get("STAR_DISCORD_CHANNEL_IDS", ""), "STAR_DISCORD_CHANNEL_IDS"),
        )

    def require(self, user_id: int, guild_id: int | None, channel_id: int | None) -> None:
        if user_id not in self.owners:
            raise PermissionError("Only the configured STAR owner can use this bot")
        if guild_id is None:
            return  # Only owner DMs; no guild privileges and no automatic server tools.
        if guild_id not in self.guilds:
            raise PermissionError("This Discord server is not approved for STAR")
        if self.channels and channel_id not in self.channels:
            raise PermissionError("This channel is not on STAR's allowlist")


SessionKey = tuple[int | None, int, int]


@dataclass
class _Session:
    touched: float
    turns: list[tuple[str, str]] = field(default_factory=list)


class SessionMemory:
    """Owner-separated in-RAM context; never mixed with desktop knowledge/lessons."""

    def __init__(self, *, max_turns: int = 6, ttl_seconds: int = 3600,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not 1 <= max_turns <= 30 or ttl_seconds < 1:
            raise ValueError("Invalid Discord conversation memory budget")
        self._max_turns, self._ttl, self._clock = max_turns, ttl_seconds, clock
        self._sessions: dict[SessionKey, _Session] = {}

    def _expire(self) -> None:
        now = self._clock()
        for key, session in list(self._sessions.items()):
            if now - session.touched >= self._ttl:
                self._sessions.pop(key, None)

    def history(self, key: SessionKey) -> list[dict[str, str]]:
        self._expire()
        session = self._sessions.get(key)
        if session is None:
            return []
        session.touched = self._clock()
        return [{"role": role, "content": content} for role, content in session.turns]

    def remember(self, key: SessionKey, prompt: str, answer: str) -> None:
        self._expire()
        if key not in self._sessions and len(self._sessions) >= MAX_ACTIVE_SESSIONS:
            # Bound RAM use even if a single approved owner uses many channels.
            oldest = min(self._sessions, key=lambda item: self._sessions[item].touched)
            del self._sessions[oldest]
        session = self._sessions.setdefault(key, _Session(self._clock()))
        session.touched = self._clock()
        session.turns.extend((("user", prompt[:MAX_PROMPT]), ("assistant", answer[:MAX_REPLY])))
        session.turns = session.turns[-self._max_turns * 2:]

    def forget(self, key: SessionKey) -> None:
        self._sessions.pop(key, None)


def clean_text(value: str, *, max_chars: int) -> str:
    """Constrain Discord Markdown payloads and defang accidental mass mentions."""
    value = str(value).replace("\x00", "").strip()
    value = re.sub(r"@(everyone|here)\b", lambda m: "@\u200b" + m.group(1), value, flags=re.IGNORECASE)
    return value[:max_chars]


def embed_parts(text: str, limit: int = MAX_EMBED_DESCRIPTION) -> list[str]:
    """Split on readable boundaries without exceeding Discord's embed description limit."""
    if limit < 100 or limit > 4096:
        raise ValueError("Invalid embed size")
    source = clean_text(text, max_chars=MAX_REPLY)
    if not source:
        return ["(No text returned)"]
    parts = []
    while source:
        if len(source) <= limit:
            parts.append(source)
            break
        cut = max(source.rfind("\n", 0, limit), source.rfind(" ", 0, limit))
        if cut < limit // 2:
            cut = limit
        parts.append(source[:cut].strip())
        source = source[cut:].strip()
    return parts


def session_key(guild_id: int | None, channel_id: int, user_id: int) -> SessionKey:
    return guild_id, channel_id, user_id


MAX_MESSAGE = 2000


class RateLimited(PermissionError):
    """The owner is sending faster than the configured budget."""


class RateLimiter:
    """Sliding-window budget per Discord user; protects the local model and Discord's API."""

    def __init__(self, *, limit: int = 30, window_seconds: float = 600.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if type(limit) is not int or not 1 <= limit <= 1000 or window_seconds <= 0:
            raise ValueError("Invalid Discord rate limit")
        self.limit, self.window, self._clock = limit, float(window_seconds), clock
        self._hits: dict[int, list[float]] = {}

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "RateLimiter":
        source = os.environ if env is None else env
        raw = str(source.get("STAR_DISCORD_RATE_LIMIT", "30")).strip() or "30"
        if not raw.isdecimal() or not 1 <= int(raw) <= 1000:
            raise ValueError("STAR_DISCORD_RATE_LIMIT must be a number from 1 to 1000")
        return cls(limit=int(raw))

    def hit(self, user_id: int) -> None:
        now = self._clock()
        recent = [t for t in self._hits.get(user_id, []) if now - t < self.window]
        if len(recent) >= self.limit:
            wait = int(self.window - (now - recent[0])) + 1
            self._hits[user_id] = recent
            raise RateLimited(f"Slow down a little: STAR takes {self.limit} requests per "
                              f"{int(self.window // 60)} minutes. Try again in about {wait} s.")
        recent.append(now)
        self._hits[user_id] = recent


def split_message(text: str, limit: int = 1990, *, max_parts: int = 6) -> tuple[list[str], str]:
    """Split a reply into Discord-sized messages, keeping ``` code blocks valid.

    Returns (parts, overflow). ``overflow`` is the untouched remainder when more than
    ``max_parts`` messages would be needed; the caller attaches the full text as a file.
    """
    if not 200 <= limit <= MAX_MESSAGE or max_parts < 1:
        raise ValueError("Invalid message split")
    source = clean_text(text, max_chars=MAX_REPLY)
    if not source:
        return ["(No text returned)"], ""
    parts: list[str] = []
    fence = ""  # the opening fence line (e.g. "```lua") when a code block is open
    while source:
        if len(parts) == max_parts:
            return parts, source
        prefix = fence + "\n" if fence else ""
        room = limit - len(prefix) - 4  # leave room to close an open fence
        if len(source) <= room:
            chunk, source = source, ""
        else:
            cut = source.rfind("\n", 0, room)
            if cut < room // 2:
                cut = source.rfind(" ", 0, room)
            if cut < room // 2:
                cut = room
            chunk, source = source[:cut], source[cut:].lstrip("\n")
        body = prefix + chunk
        # Track whether this chunk leaves a code block open.
        for line in chunk.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                fence = "" if fence else stripped
        if fence and source:
            body = body.rstrip() + "\n```"
        parts.append(body.strip() or "​")
    return parts, ""
