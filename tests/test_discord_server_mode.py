"""The Discord bot on a STAR server (STAR_DISCORD_HOST=server, server/discord/deploy.sh).

Drawing and /screen need the PC and say so; the brain key comes from the bot's settings folder; the PC refuses
to start a second copy while the server marker is present. Fakes only: no token, network, ComfyUI or model.
"""
import asyncio
import os
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from star.discord_bot import __main__ as bot_main
from star.discord_bot.bot import BotConfig
from star.discord_bot.brain import system_prompt
from star.discord_bot.core import RateLimiter
from star.discord_bot.draw import NEEDS_PC, NO_SUBJECT, Drawer, DrawSettings
from star.discord_bot.local_config import SERVER_MARKER, bot_host, load_merged_env, parse_env_text
from star.discord_bot.service import DiscordService
from star.server_key_file import read_key_file

OWNER, GUILD, CHANNEL = 111, 222, 333
TOKEN = "fake-token-never-sent"
ROOT = Path(__file__).resolve().parents[1]


def env(**extra):
    return {"STAR_DISCORD_BOT_TOKEN": TOKEN, "STAR_DISCORD_OWNER_IDS": str(OWNER),
            "STAR_DISCORD_GUILD_IDS": str(GUILD), "STAR_DISCORD_DM_CHAT": "1", **extra}


def test_host_setting_defaults_to_pc_and_is_checked():
    assert bot_host({}) == "pc"
    assert bot_host({"STAR_DISCORD_HOST": " Server "}) == "server"
    with pytest.raises(ValueError, match="pc or server"):
        bot_host({"STAR_DISCORD_HOST": "cloud"})
    assert parse_env_text("STAR_DISCORD_HOST=server", origin="x") == {"STAR_DISCORD_HOST": "server"}
    assert BotConfig.from_env(env()).host == "pc"
    config = BotConfig.from_env(env(STAR_DISCORD_HOST="server"))
    assert config.host == "server" and config.draw.on_pc is False
    assert DrawSettings.from_env({}).on_pc is True


def test_server_bot_never_starts_comfyui_and_says_drawing_needs_the_pc():
    calls = []
    drawer = Drawer(DrawSettings(on_pc=False), load_settings=lambda: calls.append("settings"),
                    generate=lambda *a, **k: calls.append("generate"))
    with pytest.raises(ValueError) as info:
        asyncio.run(drawer.draw("a dragon"))
    assert str(info.value) == NEEDS_PC and calls == []
    assert drawer.describe().startswith("needs the PC")


def test_server_system_prompt_says_pictures_are_made_on_the_pc():
    text = system_prompt(draw=True, vision=True, on_pc=False)
    assert "Making images: only on the PC" in text and "Making images: ON" not in text
    assert system_prompt() == system_prompt(draw=True, vision=True, on_pc=True)   # PC prompt unchanged


def test_brain_key_comes_from_the_bot_settings_folder(tmp_path, monkeypatch):
    (tmp_path / "server_api_key").write_text("abc123key\n", encoding="utf-8")
    assert read_key_file(path=tmp_path / "server_api_key") == "abc123key"
    monkeypatch.delenv("STAR_SERVER_API_KEY", raising=False)
    monkeypatch.setattr("star.providers.get_api_key", lambda name: None)
    bot_main._server_key_fallback(tmp_path)
    assert os.environ.pop("STAR_SERVER_API_KEY") == "abc123key"


def test_pc_refuses_a_second_copy_while_the_server_marker_is_there(tmp_path, monkeypatch, capsys):
    (tmp_path / SERVER_MARKER).write_text("brain 2\n", encoding="utf-8")
    settings = {**env(), "STAR_DISCORD_CONFIG_DIR": str(tmp_path)}
    config = BotConfig.from_env(settings)
    assert bot_main._run(config, settings) == bot_main.EXIT_CONFIG
    assert "runs on a STAR server now" in capsys.readouterr().err
    assert not (tmp_path / "discord-bot.lock").exists()        # stopped before taking the lock


def test_settings_folder_override_reads_the_server_secrets(tmp_path):
    (tmp_path / "discord.env").write_text(f"DISCORD_BOT_TOKEN={TOKEN}\n", encoding="utf-8")
    (tmp_path / "discord-settings.env").write_text(f"DISCORD_OWNER_ID={OWNER}\n", encoding="utf-8")
    merged = load_merged_env({"STAR_DISCORD_CONFIG_DIR": str(tmp_path), "STAR_DISCORD_HOST": "server"})
    assert merged["STAR_DISCORD_BOT_TOKEN"] == TOKEN and merged["STAR_DISCORD_HOST"] == "server"


def interaction():
    log = []

    async def send_message(content=None, **kwargs):
        log.append(("send_message", {"content": content, **kwargs}))

    async def edit_original_response(**kwargs):
        log.append(("edit", kwargs))

    response = SimpleNamespace(send_message=send_message, is_done=lambda: False)

    async def defer(**kwargs):
        log.append(("defer", kwargs))
    response.defer = defer
    return SimpleNamespace(user=SimpleNamespace(id=OWNER, voice=None), guild_id=GUILD, channel_id=CHANNEL,
                           guild=None, response=response, log=log, edit_original_response=edit_original_response,
                           followup=SimpleNamespace(send=send_message))


class Channel:
    def __init__(self, kind):
        self.type, self.id, self.sent = kind, CHANNEL, []

    async def send(self, content=None, **kwargs):
        sent = SimpleNamespace(content=content, kwargs=kwargs)

        async def edit(content=None, **kw):
            sent.content = content
        sent.edit = edit
        self.sent.append(sent)
        return sent


def server_bot():
    pytest.importorskip("discord")
    from star.discord_bot.bot import create_bot
    config = BotConfig.from_env(env(STAR_DISCORD_HOST="server", STAR_DISCORD_SCREEN_CAPTURE="1"))
    service = DiscordService(config.policy, brain=SimpleNamespace(), rate_limiter=RateLimiter(limit=30))
    return create_bot(config, service=service)


def test_server_bot_slash_commands_say_screen_and_draw_need_the_pc():
    bot = server_bot()

    async def run():
        try:
            screen = interaction()
            await bot.tree.get_command("screen").callback(screen, question="what is open?")
            sent = screen.log[0][1]
            assert "needs the STAR app on your PC" in sent["embed"].description and "view" not in sent
            draw = interaction()
            await bot.tree.get_command("draw").callback(draw, prompt="a dragon", private=False)
            assert draw.log[-1][1]["content"] == "⚠️ " + NEEDS_PC
        finally:
            await bot.close()
    asyncio.run(run())


def test_server_bot_dm_draw_request_gets_the_needs_pc_answer():
    discord = pytest.importorskip("discord")
    bot = server_bot()

    async def run():
        try:
            dm = Channel(discord.ChannelType.private)
            msg = SimpleNamespace(guild=None, author=SimpleNamespace(id=OWNER, bot=False), channel=dm,
                                  attachments=[], content="Generate me a image", id=42, mentions=[])
            await bot.on_message(msg)
            assert dm.sent[-1].content == "⚠️ " + NEEDS_PC and NO_SUBJECT not in [m.content for m in dm.sent]
        finally:
            await bot.close()
    asyncio.run(run())


def test_unit_and_deploy_script_keep_the_bot_light_and_hold_no_addresses():
    unit = (ROOT / "server/discord/star-discord.service").read_text(encoding="utf-8")
    for line in ("Restart=on-failure", "MemoryMax=512M", "User=star-discord", "WantedBy=multi-user.target",
                 "KillSignal=SIGINT", "STAR_DISCORD_HOST=server", "STAR_DISCORD_CONFIG_DIR=/opt/star/discord/secrets"):
        assert line in unit
    script = (ROOT / "server/discord/deploy.sh").read_text(encoding="utf-8")
    for text in (unit, script):
        assert not re.search(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+", text)
    assert "chmod 600" in script and "-m 700" in script
