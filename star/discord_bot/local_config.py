"""Owner-local Discord configuration files (never part of the repository).

Two plain files in the owner's ``~/.star`` folder, both optional:

* ``discord.env``           the secret: ``DISCORD_BOT_TOKEN=...`` (the owner writes it himself)
* ``discord-settings.env``  nonsecret IDs and opt-in switches (``DISCORD_OWNER_ID=...`` etc.)

Process environment variables always win, so CI and the PowerShell helper keep working.
Only a fixed allowlist of keys is read; values are never logged or printed, and a
malformed line is reported by line number only.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

TOKEN_FILE = "discord.env"
SETTINGS_FILE = "discord-settings.env"
MAX_FILE_BYTES = 16 * 1024

# Friendly owner-facing names -> the STAR_DISCORD_* names the bot uses internally.
ALIASES = {
    "DISCORD_BOT_TOKEN": "STAR_DISCORD_BOT_TOKEN",
    "DISCORD_TOKEN": "STAR_DISCORD_BOT_TOKEN",
    "DISCORD_OWNER_ID": "STAR_DISCORD_OWNER_IDS",
    "DISCORD_OWNER_IDS": "STAR_DISCORD_OWNER_IDS",
    "DISCORD_USER_ID": "STAR_DISCORD_OWNER_IDS",
    "DISCORD_GUILD_ID": "STAR_DISCORD_GUILD_IDS",
    "DISCORD_GUILD_IDS": "STAR_DISCORD_GUILD_IDS",
    "DISCORD_SERVER_ID": "STAR_DISCORD_GUILD_IDS",
    "DISCORD_CHANNEL_IDS": "STAR_DISCORD_CHANNEL_IDS",
}
ALLOWED = frozenset({
    "STAR_DISCORD_BOT_TOKEN", "STAR_DISCORD_OWNER_IDS", "STAR_DISCORD_GUILD_IDS",
    "STAR_DISCORD_CHANNEL_IDS", "STAR_DISCORD_SYNC_COMMANDS", "STAR_DISCORD_SYNC_GUILD_ID",
    "STAR_DISCORD_DM_CHAT", "STAR_DISCORD_DM_IMAGES", "STAR_DISCORD_DM_LEARNING_CANDIDATES",
    "STAR_DISCORD_DM_PROJECT", "STAR_DISCORD_SCREEN_CAPTURE", "STAR_DISCORD_RATE_LIMIT",
    "STAR_DISCORD_LEARNING_DM_OPT_IN", "STAR_DISCORD_LEARNING_DM_OWNER_ID",
    "STAR_DISCORD_LEARNING_REPORT", "STAR_DISCORD_LEARNING_REPORT_SSH",
    "STAR_DISCORD_LEARNING_STATE", "STAR_DISCORD_LEARNING_DM_COOLDOWN_HOURS",
    "STAR_DISCORD_LEARNING_CHECK_MINUTES",
    "STAR_DISCORD_LEARNING_VISUAL_MANIFEST", "STAR_DISCORD_LEARNING_VISUAL_DIRECTORY",
})
# The token may only come from the secret file or the process environment.
_SECRET_KEYS = frozenset({"STAR_DISCORD_BOT_TOKEN"})


def config_dir(env: Mapping[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    override = str(source.get("STAR_DISCORD_CONFIG_DIR", "")).strip()
    return Path(override) if override else Path.home() / ".star"


def parse_env_text(text: str, *, origin: str) -> dict[str, str]:
    """KEY=VALUE lines; '#' comments; optional matching quotes. Unknown keys are refused."""
    values: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().lstrip("﻿")
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ValueError(f"{origin} line {number}: expected NAME=value")
        name, value = line.split("=", 1)
        name = name.strip().upper()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        name = ALIASES.get(name, name)
        if name not in ALLOWED:
            raise ValueError(f"{origin} line {number}: unknown setting name")
        values[name] = value
    return values


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} is unexpectedly large")
    return path.read_text(encoding="utf-8-sig")


def load_merged_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return process env overlaid on the local files (process env wins).

    The returned mapping holds the token in memory only; callers must not print it.
    """
    source = dict(os.environ if env is None else env)
    folder = config_dir(source)
    merged: dict[str, str] = {}
    settings = parse_env_text(_read(folder / SETTINGS_FILE), origin=SETTINGS_FILE)
    if any(key in _SECRET_KEYS for key in settings):
        raise ValueError(f"Keep the bot token in {TOKEN_FILE}, not {SETTINGS_FILE}")
    merged.update(settings)
    secret = parse_env_text(_read(folder / TOKEN_FILE), origin=TOKEN_FILE)
    merged.update(secret)
    for key, value in source.items():
        if key in ALLOWED and str(value).strip():
            merged[key] = str(value)
    # Keep unrelated process variables (APPDATA, PATH...) for the rest of STAR.
    for key, value in source.items():
        merged.setdefault(key, value)
    return merged


def token_file_present(env: Mapping[str, str] | None = None) -> bool:
    """Existence only; the file content is not read here."""
    return (config_dir(env) / TOKEN_FILE).is_file()


SETTINGS_TEMPLATE = """# STAR Discord bot: nonsecret local settings (never commit; the bot token goes in discord.env).
# Discord: User Settings > Advanced > Developer Mode, then right-click yourself / your server > Copy ID.
DISCORD_OWNER_ID=
DISCORD_GUILD_ID=
# Optional: only these text channels in your server (comma-separated). Empty = any channel in that server.
DISCORD_CHANNEL_IDS=
# 1 = register the slash commands in DISCORD_GUILD_ID on the next start (do it once, then set back to 0).
STAR_DISCORD_SYNC_COMMANDS=0
# Opt-in features (1 = on). Image/lesson switches need DM chat on.
STAR_DISCORD_DM_CHAT=1
STAR_DISCORD_DM_IMAGES=1
STAR_DISCORD_DM_LEARNING_CANDIDATES=0
# PC screenshots via /screen: each capture still needs a button press in Discord.
STAR_DISCORD_SCREEN_CAPTURE=0
# Requests per 10 minutes from the owner before STAR asks to slow down.
STAR_DISCORD_RATE_LIMIT=30
# Night School digest DMs: 1 = send a short DM when practice numbers really change.
STAR_DISCORD_LEARNING_DM_OPT_IN=0
# Where the report comes from: an ssh login that can run 'lxc exec starai' (key login), or a local file path.
STAR_DISCORD_LEARNING_REPORT_SSH=
STAR_DISCORD_LEARNING_REPORT=
"""


def ensure_settings_file(env: Mapping[str, str] | None = None) -> bool:
    """Write SETTINGS_TEMPLATE if discord-settings.env is missing; never overwrite.

    Returns True only when a file was created. Holds no secrets; the token is never written here.
    """
    path = config_dir(env) / SETTINGS_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(SETTINGS_TEMPLATE)
    except FileExistsError:
        return False
    except OSError:
        return False
    return True
