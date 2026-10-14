"""Offline, no-token proof of STAR's default-off, privacy-safe Discord presence."""
import asyncio

import pytest

from star.discord_bot.presence import (
    ACTIVITIES, PresenceSettings, activity_at, rotate_presence,
)
from star.discord_bot.bot import BotConfig
from star.discord_bot.core import AccessPolicy
from star.discord_bot.local_config import parse_env_text


def test_presence_is_opt_in_and_strictly_bounded():
    assert PresenceSettings.from_env({}) == PresenceSettings(False, 15)
    assert PresenceSettings.from_env({"STAR_DISCORD_PRESENCE": "1",
                                      "STAR_DISCORD_PRESENCE_MINUTES": "60"}) == PresenceSettings(True, 60)
    for bad in ("yes", "True", "-1", "2", "on"):
        with pytest.raises(ValueError, match="PRESENCE must be"):
            PresenceSettings.from_env({"STAR_DISCORD_PRESENCE": bad})
    for bad in ("0", "1", "9", "121", "inf", "12.5", "", "-15"):
        with pytest.raises(ValueError, match="PRESENCE_MINUTES"):
            PresenceSettings.from_env({"STAR_DISCORD_PRESENCE_MINUTES": bad})
    settings = parse_env_text("STAR_DISCORD_PRESENCE=1\nSTAR_DISCORD_PRESENCE_MINUTES=15",
                              origin="test-settings")
    assert PresenceSettings.from_env(settings).enabled


def test_presence_labels_are_fixed_and_never_private_or_model_generated():
    assert activity_at(0) == ("watching", "/star help")
    assert activity_at(1) == ("playing", "STAR Intelligence")
    assert activity_at(2) == ("watching", "for /ask")
    assert activity_at(3) == activity_at(0)
    for kind, name in ACTIVITIES:
        assert kind in {"watching", "playing"}
        assert len(name) <= 64
        assert not any(x in name.lower() for x in ("training", "recording", "owner", "user", "http"))
    for bad in (-1, True, "0", None):
        with pytest.raises(ValueError, match="index"):
            activity_at(bad)


class FakeClient:
    def __init__(self, *, fail_first=False):
        self.events = []
        self._closed = False
        self._ready = True
        self.fail_first = fail_first
        self.wait_count = 0

    async def wait_until_ready(self):
        self.wait_count += 1
        self._ready = True

    def is_closed(self):
        return self._closed

    def is_ready(self):
        return self._ready

    async def change_presence(self, *, activity):
        self.events.append(activity)
        if self.fail_first and len(self.events) == 1:
            raise ConnectionError("secret-network-detail")
        if len(self.events) >= (2 if self.fail_first else 3):
            self._closed = True


def test_opt_out_never_touches_gateway():
    client = FakeClient()
    asyncio.run(rotate_presence(client, PresenceSettings(False, 15),
                                activity_factory=lambda kind, name: (kind, name)))
    assert client.wait_count == 0 and client.events == []


def test_rotation_is_slow_reconnect_safe_and_uses_fixed_activity():
    client = FakeClient()
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            client._ready = False  # transport changed since previous update

    asyncio.run(rotate_presence(client, PresenceSettings(True, 15),
                                activity_factory=lambda kind, name: (kind, name),
                                sleep=sleep))
    assert waits == [900, 900, 900]
    assert client.wait_count == 2  # startup + reconnect readiness; no immediate extra change
    assert client.events == [activity_at(1), activity_at(2), activity_at(3)]


def test_failed_gateway_update_never_busy_retries_or_logs_private_data():
    client = FakeClient(fail_first=True)
    log, waits = [], []

    async def sleep(seconds):
        waits.append(seconds)

    asyncio.run(rotate_presence(client, PresenceSettings(True, 10),
                                activity_factory=lambda kind, name: (kind, name),
                                sleep=sleep, on_error=log.append))
    assert log == ["ConnectionError"]  # error type only, no sensitive exception body
    assert waits == [600, 600] and len(client.events) == 2


def test_constructor_sets_initial_activity_without_privileged_intents():
    discord = pytest.importorskip("discord")
    from star.discord_bot.bot import create_bot

    policy = AccessPolicy(frozenset({123}), frozenset({456}))
    config = BotConfig(token="dummy-for-offline-test", policy=policy,
                       presence=PresenceSettings(True, 15))
    bot = create_bot(config)
    try:
        assert bot.activity is not None and bot.activity.name == "/star help"
        assert bot.activity.type == discord.ActivityType.watching
        assert not bot.intents.message_content
        assert not bot.intents.members
        assert not bot.intents.presences
        assert not bot.intents.guild_messages
    finally:
        asyncio.run(bot.close())

    off = create_bot(BotConfig(token="dummy", policy=policy))
    try:
        assert off.activity is None
    finally:
        asyncio.run(off.close())
