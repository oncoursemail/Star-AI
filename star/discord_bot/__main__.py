"""Run: python -m star.discord_bot [--log-file PATH] [doctor | smoke]

Exit codes: 0 stopped normally, 2 configuration problem (do not retry), 3 Discord library missing
(do not retry), 4 another STAR Discord bot is already running (do not start a second one).

Settings come from the process environment, then ~/.star/discord.env (the bot token,
written by the owner) and ~/.star/discord-settings.env (IDs and opt-in switches).
Nothing here prints the token or the owner's IDs.
"""
from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from .bot import BotConfig, create_bot
from .local_config import SERVER_MARKER, bot_host, config_dir, ensure_settings_file, load_merged_env

EXIT_CONFIG, EXIT_MISSING_LIBRARY, EXIT_ALREADY_RUNNING = 2, 3, 4
LOG_BYTES, LOG_BACKUPS = 1_000_000, 3


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


def _take_log_file(args: list[str]) -> tuple[list[str], str]:
    """Split ``--log-file PATH`` off the arguments."""
    if "--log-file" not in args:
        return args, ""
    index = args.index("--log-file")
    if index + 1 >= len(args):
        return args, ""
    return args[:index] + args[index + 2:], args[index + 1]


def _setup_logging(log_file: str) -> None:
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    if not log_file:
        logging.basicConfig(level=logging.INFO, format=fmt)
        return
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=LOG_BYTES, backupCount=LOG_BACKUPS,
                                                   encoding="utf-8")
    handler.setFormatter(logging.Formatter(fmt))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _fail(message: str, code: int) -> int:
    """Say it on the console and in the log file (a windowless start has no console)."""
    print(message, file=sys.stderr)
    logging.getLogger(__name__).error("%s", message)
    return code


def _server_key_fallback(folder: Path) -> None:
    """Use server_api_key in the bot's settings folder (~/.star on the PC, STAR_DISCORD_CONFIG_DIR on a
    server) when neither the environment nor the keyring holds the brain key.

    The key stays in this process's memory; it is not printed or logged.
    """
    try:
        from ..providers import STAR_SERVER, get_api_key
        if get_api_key(STAR_SERVER):
            return
        from ..server_key_file import read_key_file
        os.environ["STAR_SERVER_API_KEY"] = read_key_file(path=folder / "server_api_key")
    except Exception:
        return  # no key file: the bot still starts and says so when a model answer needs it


def main() -> int:
    args, log_file = _take_log_file(sys.argv[1:])
    _setup_logging(log_file)
    if args not in ([], ["doctor"], ["smoke"]):
        print("Usage: python -m star.discord_bot [--log-file PATH] [doctor | smoke]", file=sys.stderr)
        return 2
    if ensure_settings_file():
        print("Created a settings template (discord-settings.env) in your .star folder; fill in your IDs.")
    try:
        env = load_merged_env()
    except ValueError as exc:
        return _fail(f"STAR Discord configuration error: {exc}", EXIT_CONFIG)
    if args == ["doctor"]:
        from .health import doctor_snapshot, format_checks
        checks = doctor_snapshot(env)
        print(format_checks(checks, ascii_only=True))
        # Optional voice/research capabilities do not block chat-only startup.
        return 2 if any(c.status == "setup" for c in checks) else 0
    try:
        config = BotConfig.from_env(env)
    except (ValueError, PermissionError) as exc:
        return _fail(f"STAR Discord configuration error: {exc}", EXIT_CONFIG)
    try:
        if args == ["smoke"]:
            return asyncio.run(smoke(config))
        return _run(config, env)
    except ImportError:
        return _fail("Install requirements-discord.txt before running the Discord bot", EXIT_MISSING_LIBRARY)


def _run(config: BotConfig, env: dict) -> int:
    from .instance_lock import InstanceLock
    from .runtime_status import StatusReporter
    folder = config_dir(env)
    if bot_host(env) == "pc" and (folder / SERVER_MARKER).is_file():
        return _fail(f"STAR's Discord bot runs on a STAR server now ({SERVER_MARKER} is in {folder}); not "
                     "starting a second copy on this PC. To move it back: stop the server copy, delete that file "
                     "(docs/STAR_DISCORD_SETUP.md, 'Run it on a STAR server').", EXIT_CONFIG)
    lock = InstanceLock(folder)
    if not lock.acquire():
        return _fail("Another STAR Discord bot is already running for this account; not starting a second one.",
                     EXIT_ALREADY_RUNNING)
    status = StatusReporter(folder)
    try:
        _server_key_fallback(folder)
        status.write("starting")
        create_bot(config, reporter=status).run(config.token, log_handler=None)
        return 0
    finally:
        status.write("stopped")
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
