"""Run: python -m star.discord_bot [doctor | smoke]

Settings come from the process environment, then ~/.star/discord.env (the bot token,
written by the owner) and ~/.star/discord-settings.env (IDs and opt-in switches).
Nothing here prints the token or the owner's IDs.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from .bot import BotConfig, create_bot
from .local_config import ensure_settings_file, load_merged_env


async def smoke(config: BotConfig) -> int:
    """Live, read-only check: log in over REST, confirm the bot identity and server membership.

    Sends no messages and changes nothing on Discord.
    """
    import discord
    client = discord.Client(intents=discord.Intents.none())
    try:
        await client.login(config.token)
        app = await client.application_info()
        me = client.user
        print(f"[OK] Logged in as bot '{me.name}' (application '{app.name}')")
        print(f"[OK] Bot is {'public' if app.bot_public else 'private (only the owner can invite it)'}")
        guilds = [g.id async for g in client.fetch_guilds(limit=50)]
        if config.policy.guilds:
            joined = sum(1 for g in config.policy.guilds if g in guilds)
            print(f"[{'OK' if joined else 'SETUP'}] In {joined} of {len(config.policy.guilds)} approved server(s)"
                  + ("" if joined else ": invite the bot with the link in docs/STAR_DISCORD_SETUP.md"))
        else:
            print(f"[OK] DM-only mode (bot is in {len(guilds)} server(s); none approved for commands)")
        for owner in config.policy.owners:
            try:
                await client.fetch_user(owner)
                print("[OK] Owner account found")
            except discord.NotFound:
                print("[SETUP] DISCORD_OWNER_ID does not match a Discord user")
        return 0
    except discord.LoginFailure:
        print("[SETUP] Discord rejected the bot token (reset it in the Developer Portal and update discord.env)")
        return 2
    finally:
        await client.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = sys.argv[1:]
    if args not in ([], ["doctor"], ["smoke"]):
        print("Usage: python -m star.discord_bot [doctor | smoke]", file=sys.stderr)
        return 2
    if ensure_settings_file():
        print("Created a settings template (discord-settings.env) in your .star folder; fill in your IDs.")
    try:
        env = load_merged_env()
    except ValueError as exc:
        print(f"STAR Discord configuration error: {exc}", file=sys.stderr)
        return 2
    if args == ["doctor"]:
        from .health import doctor_snapshot, format_checks
        checks = doctor_snapshot(env)
        print(format_checks(checks, ascii_only=True))
        # Optional voice/research capabilities do not block chat-only startup.
        return 2 if any(c.status == "setup" for c in checks) else 0
    try:
        config = BotConfig.from_env(env)
    except (ValueError, PermissionError) as exc:
        print(f"STAR Discord configuration error: {exc}", file=sys.stderr)
        return 2
    try:
        if args == ["smoke"]:
            return asyncio.run(smoke(config))
        create_bot(config).run(config.token, log_handler=None)
    except ImportError:
        print("Install requirements-discord.txt before running the Discord bot", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
