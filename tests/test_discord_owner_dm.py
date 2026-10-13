"""STAR Discord owner DM features: offline, no Discord gateway or model network."""
import asyncio
import base64
from io import BytesIO
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image

from star.discord_bot.bot import BotConfig
from star.discord_bot.core import AccessPolicy
from star.discord_bot.dm_mode import (
    DMSettings, DiscordVision, classify_owner_dm,
    prepare_discord_image, capture_discord_lesson_candidate,
)
from star.discord_bot.service import DiscordService


def owner_policy():
    return AccessPolicy(frozenset({123}), frozenset(), frozenset())


def test_dm_flags_default_to_disabled_and_reject_partial_enablement():
    assert DMSettings.from_env({}) == DMSettings()
    settings = BotConfig.from_env({
        "STAR_DISCORD_BOT_TOKEN": "dummy",
        "STAR_DISCORD_OWNER_IDS": "123",
    })
    assert not settings.dm.enabled
    for field in ("STAR_DISCORD_DM_IMAGES", "STAR_DISCORD_DM_LEARNING_CANDIDATES"):
        with pytest.raises(ValueError, match="Enable private DM"):
            DMSettings.from_env({field: "1"})
    with pytest.raises(ValueError, match="must be 0 or 1"):
        DMSettings.from_env({"STAR_DISCORD_DM_CHAT": "true"})
    with pytest.raises(ValueError, match="learning project"):
        DMSettings.from_env({"STAR_DISCORD_DM_PROJECT": "../workspace"})
    assert DMSettings.from_env({
        "STAR_DISCORD_DM_CHAT": "1",
        "STAR_DISCORD_DM_IMAGES": "1",
        "STAR_DISCORD_DM_LEARNING_CANDIDATES": "1",
    }) == DMSettings(True, True, True, "STAR")


def test_owner_dm_intake_never_trusts_arbitrary_chats_as_approved_learning():
    enabled = DMSettings(enabled=True, images=True, learning_candidates=True)
    assert classify_owner_dm("Hi STAR", attachments=0, options=enabled).kind == "text"
    assert classify_owner_dm("I prefer smaller buttons", attachments=0, options=enabled).kind == "text"
    proposal = classify_owner_dm(
        "remember preference: Use a compact, clean Roblox UI",
        attachments=0, options=enabled)
    assert proposal.kind == "remember"
    assert proposal.lesson_kind == "preference"
    assert proposal.prompt == "Use a compact, clean Roblox UI"
    correction = classify_owner_dm(
        "REMEMBER correction: DataStore failures must not overwrite saved data",
        attachments=0, options=enabled)
    assert correction.kind == "remember" and correction.lesson_kind == "correction"
    image = classify_owner_dm("Critique the HUD", attachments=1, options=enabled)
    assert image.kind == "image"
    assert image.prompt == "Critique the HUD"
    assert classify_owner_dm("anything", attachments=3, options=enabled).error
    assert classify_owner_dm("Hi", attachments=0, options=DMSettings()).kind == "ignored"
    assert classify_owner_dm("", attachments=0, options=enabled).kind == "ignored"
    assert classify_owner_dm(
        "remember: test", attachments=0, options=enabled).error


def test_discord_image_is_bounded_normalized_and_strips_metadata():
    image = Image.new("RGB", (28, 18), (150, 35, 70))
    data = BytesIO()
    image.save(data, format="PNG", pnginfo=None)
    payload = data.getvalue()
    normalized = prepare_discord_image(
        "interface.png", "image/png", len(payload), payload)
    assert normalized.startswith(b"\xff\xd8")
    with Image.open(BytesIO(normalized)) as result:
        assert result.format == "JPEG"
        assert result.size == (28, 18)
        assert "exif" not in result.info
    with pytest.raises(ValueError, match="decoded"):
        invalid = b"not-an-png"
        prepare_discord_image("ui.png", "image/png", len(invalid), invalid)
    with pytest.raises(ValueError, match="size|received"):
        prepare_discord_image("ui.png", "image/png", 5, payload)
    with pytest.raises(ValueError, match="PNG"):
        prepare_discord_image("ui.svg", "image/svg+xml", len(payload), payload)
    with pytest.raises(ValueError, match="does not match"):
        prepare_discord_image("ui.jpg", "image/jpeg", len(payload), payload)


def test_vision_calls_only_configured_local_model_without_tools(monkeypatch):
    image = Image.new("RGB", (20, 20), (100, 100, 100))
    stream = BytesIO()
    image.save(stream, format="JPEG")
    jpeg = stream.getvalue()
    sent = []
    settings = SimpleNamespace(
        vision_model="star-vision", provider="server", validate=lambda: None)

    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        async def create(self, **request):
            sent.append(request)
            return SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(
                    content="The HUD is aligned.", tool_calls=None))])

    from star import providers as stub
    monkeypatch.setattr(stub, "provider_kind", lambda settings: "lan")
    monkeypatch.setattr(stub, "open_client", lambda settings, **kwargs: Client())
    answer = asyncio.run(DiscordVision(settings=settings).reply("Review alignment", jpeg))
    assert "aligned" in answer
    req = sent[0]
    assert req["model"] == "star-vision" and "tools" not in req
    content = req["messages"][-1]["content"]
    assert content[0]["text"] == "Review alignment"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(content[1]["image_url"]["url"].split(",")[1]) == jpeg
    stub.provider_kind = lambda settings: "cloud"
    with pytest.raises(PermissionError, match="local-only"):
        asyncio.run(DiscordVision(settings=settings).reply("Review alignment", jpeg))
    with pytest.raises(ValueError, match="vision-capable"):
        asyncio.run(DiscordVision(settings=SimpleNamespace(
            vision_model="", provider="server", validate=lambda: None
        )).reply("review", jpeg))


def test_owner_remember_creates_only_an_unapproved_candidate(tmp_path):
    result = capture_discord_lesson_candidate(
        owner_id=123, allowed_owners=frozenset({123}),
        message_id=987654321, text="Use clean, minimal UI for this Roblox game",
        kind="preference", project="STAR", home=tmp_path)
    assert result.status == "candidate"
    assert result.lesson_id is not None
    from star.lessons import LessonStore
    store = LessonStore(tmp_path)
    try:
        lesson = store.get("STAR", result.lesson_id)
        assert not store.knowledge.db.execute(
            "SELECT reviewed FROM notes WHERE id=?", (result.lesson_id,)).fetchone()[0]
        assert lesson.status == "candidate" and lesson.source_type == "user"
        assert lesson.source == "discord-owner-dm:987654321"
    finally:
        store.close()
    again = capture_discord_lesson_candidate(
        owner_id=123, allowed_owners=frozenset({123}),
        message_id=987654321, text="Use clean, minimal UI for this Roblox game",
        kind="preference", project="STAR", home=tmp_path)
    assert again.status == "duplicate"
    with pytest.raises(PermissionError):
        capture_discord_lesson_candidate(
            owner_id=999, allowed_owners=frozenset({123}),
            message_id=1, text="Always use tests to verify code",
            kind="preference", project="STAR", home=tmp_path)


def test_discord_service_handles_vision_as_ephemeral_owner_dm_only(tmp_path):
    service = DiscordService(owner_policy())
    key = service.authorized(123, None, 789)

    class Vision:
        async def reply(self, prompt, data):
            assert prompt == "Check the HUD" and data == b"\xff\xd8data"
            return "UI may overlap at narrow widths"

    async def work():
        response = await service.inspect_image(
            key, "Check the HUD", b"\xff\xd8data", vision=Vision())
        assert "overlap" in response
        history = service.memory.history(key)
        assert len(history) == 2
        assert history[0]["content"] == "[Image discussed] Check the HUD"
        with pytest.raises(PermissionError):
            await service.inspect_image((456, 789, 123), "Hi", b"\xff\xd8data", vision=Vision())
        candidate = await service.propose_dm_lesson(
            key, message_id=123456, text="Always use compact layouts",
            kind="preference", project="STAR", home=tmp_path)
        assert candidate.status == "candidate"

    asyncio.run(work())
