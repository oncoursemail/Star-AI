"""Opt-in, bounded activity rotation for STAR's real Discord bot account.

Runtime Gateway presence is not a profile biography, a message-of-the-day, or a
claim about what STAR is actually doing. No guild content, user names, model
output, user-supplied commands or credentials may become activity text.

Discord.py recommends initial activity in Client/Bot constructor, not in the
on_ready handler (which runs on reconnect). The only subsequent updates come
from this slow operator-opted-in task.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from typing import Awaitable, Callable, Mapping


MIN_INTERVAL_MINUTES = 10
MAX_INTERVAL_MINUTES = 120
DEFAULT_INTERVAL_MINUTES = 15

# These fixed strings are intentionally private-data-free and cannot be changed
# by messages, model answers, website text or tool results.
ACTIVITIES: tuple[tuple[str, str], ...] = (
    ("watching", "/star help"),
    ("playing", "STAR Intelligence"),
    ("watching", "for /ask"),
)


@dataclass(frozen=True)
class PresenceSettings:
    enabled: bool = False
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "PresenceSettings":
        source = os.environ if env is None else env
        enabled = str(source.get("STAR_DISCORD_PRESENCE", "0")).strip() or "0"
        if enabled not in {"0", "1"}:
            raise ValueError("STAR_DISCORD_PRESENCE must be 0 or 1")
        minutes = str(source.get("STAR_DISCORD_PRESENCE_MINUTES", str(DEFAULT_INTERVAL_MINUTES))).strip()
        if not minutes.isdecimal() or not MIN_INTERVAL_MINUTES <= int(minutes) <= MAX_INTERVAL_MINUTES:
            raise ValueError("STAR_DISCORD_PRESENCE_MINUTES must be from 10 to 120")
        return cls(enabled == "1", int(minutes))


def activity_at(index: int) -> tuple[str, str]:
    if type(index) is not int or index < 0:
        raise ValueError("Activity index must be a nonnegative integer")
    return ACTIVITIES[index % len(ACTIVITIES)]


async def rotate_presence(bot, settings: PresenceSettings, *,
                          activity_factory: Callable[[str, str], object],
                          sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
                          on_error: Callable[[str], None] | None = None) -> None:
    """Periodically rotate fixed bot activity only when an opted-in bot is ready.

    Caller owns cancellation on bot shutdown. Never calls change_presence in
    on_ready, never repeatedly sends updates on reconnect, and never attempts
    privileged guild-presence subscriptions. HTTP/network failures are logged by
    *type only* and reattempted after the next long interval, never a busy loop.
    """
    if not settings.enabled:
        return
    await bot.wait_until_ready()
    index = 0  # Initial constructor activity is index zero.
    while not bot.is_closed():
        await sleep(settings.interval_minutes * 60)
        if bot.is_closed():
            return
        if not bot.is_ready():
            await bot.wait_until_ready()
            if bot.is_closed():
                return
        index += 1
        kind, label = activity_at(index)
        try:
            await bot.change_presence(activity=activity_factory(kind, label))
        except Exception as exc:
            if on_error:
                on_error(type(exc).__name__)
