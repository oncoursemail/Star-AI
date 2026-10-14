"""Offline owner-only image comparison: no provider network, Discord token or Studio."""
import asyncio
import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from star.discord_bot.bot import BotConfig
from star.discord_bot.core import AccessPolicy
from star.discord_bot.dm_mode import (DMSettings, DiscordVision, classify_owner_dm,
                                         prepare_discord_image, is_visual_critique)
from star.discord_bot.service import DiscordService


def jpeg(color):
    out = BytesIO()
    Image.new("RGB", (40, 30), color).save(out, format="JPEG")
    return out.getvalue()


def test_dm_two_images_are_reference_then_result_not_an_automatic_lesson():
    enabled = DMSettings(enabled=True, images=True, learning_candidates=True)
    request = classify_owner_dm("This is not the intended style", attachments=2, options=enabled)
    assert request.kind == "compare" and "intended style" in request.prompt
    assert classify_owner_dm("", attachments=2, options=enabled).kind == "compare"
    assert classify_owner_dm("Remember this", attachments=2, options=enabled).kind == "compare"
    assert classify_owner_dm("", attachments=3, options=enabled).error
    off = DMSettings(enabled=True, images=False, learning_candidates=False)
    assert classify_owner_dm("compare", attachments=2, options=off).error


def test_private_local_vision_sees_both_images_in_the_correct_order(monkeypatch):
    from star import providers
    sent = []
    settings = SimpleNamespace(vision_model="star-vision", provider="star_server",
                               validate=lambda: None)

    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        async def create(self, **kwargs):
            sent.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content="Observed: result has extra neon lighting. Suggest darker highlights.",
                tool_calls=None))])

    monkeypatch.setattr(providers, "provider_kind", lambda _: "lan")
    a, b = jpeg((15, 25, 35)), jpeg((100, 180, 240))
    vision = DiscordVision(settings=settings, client_factory=lambda settings, **opts: Client())
    answer = asyncio.run(vision.compare("No neon; match the darker target.", a, b))
    assert "neon" in answer
    assert len(sent) == 1
    request = sent[0]
    assert request["model"] == "star-vision" and not request.get("tools")
    user = request["messages"][1]["content"]
    assert "OWNER INSTRUCTIONS" in user[0]["text"]
    assert [x["type"] for x in user] == ["text", "image_url", "image_url"]
    raw = [base64.b64decode(x["image_url"]["url"].split(",")[1]) for x in user[1:]]
    assert raw == [a, b] and "reference" in request["messages"][0]["content"].lower()
    assert "motion" in request["messages"][0]["content"].lower()

    monkeypatch.setattr(providers, "provider_kind", lambda _: "cloud")
    with pytest.raises(PermissionError, match="private local/LAN"):
        asyncio.run(vision.compare("test", a, b))
    for wrong in (b"", b"some-data", "string"):
        with pytest.raises(ValueError, match="normalized JPEG"):
            asyncio.run(vision.compare("test", wrong, b))


def test_service_auth_keeps_image_bytes_out_of_history():
    policy = AccessPolicy(frozenset({123}), frozenset({456}))
    service = DiscordService(policy)
    class Vision:
        async def compare(self, prompt, reference, rendered):
            assert prompt == "Fix the shadow and character silhouette."
            assert reference.startswith(b"\xff\xd8")
            assert rendered.startswith(b"\xff\xd8")
            return "The reference has a flatter silhouette and softer shadows."
    ref, rendered = jpeg((20, 30, 40)), jpeg((190, 100, 50))
    async def run():
        owner = service.authorized(123, None, 555)
        answer = await service.compare_images(
            owner, "Fix the shadow and character silhouette.", ref, rendered, vision=Vision())
        assert "reference" in answer
        history = service.memory.history(owner)
        assert history[0]["role"] == "user"
        assert "Image comparison reference=" in history[0]["content"]
        assert "result=" in history[0]["content"]
        assert "Fix the shadow" in history[0]["content"]
        assert "data:image" not in str(history) and str(ref) not in str(history)
        with pytest.raises(PermissionError):
            await service.compare_images((None, 555, 999), "question", ref, rendered, vision=Vision())
    asyncio.run(run())


def test_two_images_must_be_sanitized_before_model_call():
    original = BytesIO()
    Image.new("RGB", (30, 25), (20, 50, 90)).save(original, "PNG")
    payload = original.getvalue()
    converted = prepare_discord_image("ref.png", "image/png", len(payload), payload)
    assert converted.startswith(b"\xff\xd8") and len(converted) <= 6*1024*1024
    with pytest.raises(ValueError):
        prepare_discord_image("../evil.svg", "image/svg+xml", len(payload), payload)


def test_compare_command_is_registered_but_owner_only_and_always_private():
    discord = pytest.importorskip("discord")
    from star.discord_bot.bot import create_bot
    cfg = BotConfig.from_env({"STAR_DISCORD_BOT_TOKEN": "dummy",
                              "STAR_DISCORD_OWNER_IDS": "123",
                              "STAR_DISCORD_GUILD_IDS": "456",
                              "STAR_DISCORD_DM_CHAT": "1", "STAR_DISCORD_DM_IMAGES": "1"})
    bot = create_bot(cfg)
    try:
        command = bot.tree.get_command("compare")
        assert command is not None
        payload = command.to_dict(bot.tree)
        assert payload["contexts"] == [0, 1]
        assert payload["integration_types"] == [0]
        assert not bot.intents.message_content and not bot.intents.guild_messages
        assert not bot.intents.members
    finally:
        asyncio.run(bot.close())


def test_visual_dissatisfaction_is_narrowly_classified_and_review_only():
    for phrase in ("I don't like that", "I don’t like that", "It doesn't look like my reference",
                   "You messed up the animation", "That looks wrong",
                   "Not what I was going for", "The VFX is too big"):
        assert is_visual_critique(phrase), phrase
    for phrase in ("hi", "I dislike this song",
                   "what's the temperature", "My friend doesn't like Roblox",
                   "show me a picture", "please upload new models",
                   "I don't like " + "x" * 600):
        assert not is_visual_critique(phrase), phrase
    # Only an explicitly opted-in owner image-followup may turn those words
    # into a correction; this pure classifier does no learning or writing.


def test_owner_visual_dissatisfaction_after_image_enqueues_review_only(monkeypatch):
    discord = pytest.importorskip("discord")
    from star.discord_bot.bot import create_bot

    owner = 123
    channel_id = 987
    config = BotConfig.from_env({
        "STAR_DISCORD_BOT_TOKEN": "test-token",
        "STAR_DISCORD_OWNER_IDS": str(owner),
        "STAR_DISCORD_DM_CHAT": "1",
        "STAR_DISCORD_DM_IMAGES": "1",
        "STAR_DISCORD_DM_LEARNING_CANDIDATES": "1",
    })
    service = DiscordService(config.policy)
    session = (None, channel_id, owner)
    service.memory.remember(
        session,
        "[Image comparison reference=0123456789abcdef result=abcdef0123456789] No neon",
        "This image is brighter than the reference.",
    )
    pending = []

    async def fake_correction(key, *, message_id, text, project, home=None):
        pending.append((key, message_id, text, project))
        return ({"id": 42}, None)

    monkeypatch.setattr(service, "propose_dm_correction", fake_correction)
    bot = create_bot(config, service=service)

    class Typing:
        async def __aenter__(self):
            return None
        async def __aexit__(self, *_):
            return False

    class Channel:
        def __init__(self):
            self.id = channel_id
            self.type = discord.ChannelType.private
            self.sent = []
        def typing(self):
            return Typing()
        async def send(self, content=None, **kwargs):
            self.sent.append((content, kwargs))
            return SimpleNamespace(edit=lambda **kwargs: None)

    channel = Channel()
    message = SimpleNamespace(
        id=2468, guild=None, channel=channel, attachments=[],
        author=SimpleNamespace(id=owner, bot=False),
        content="I don't like that, you messed up the animation",
    )
    async def run():
        try:
            await bot.on_message(message)
            assert len(pending) == 1
            assert pending[0] == (session, 2468, message.content, "STAR")
            assert "Correction #42" in channel.sent[0][0]
            assert "review" in channel.sent[0][0]
            assert channel.sent[0][1]["allowed_mentions"].everyone is False
            assert channel.sent[0][1]["allowed_mentions"].roles is False

            # Stranger must not access the pending correction path or receive info.
            stranger = SimpleNamespace(**{**vars(message),
                                         "author": SimpleNamespace(id=555, bot=False)})
            await bot.on_message(stranger)
            assert len(pending) == 1 and len(channel.sent) == 1
        finally:
            await bot.close()

    asyncio.run(run())
