"""Nonsecret readiness checks for STAR's optional Discord gateway.

No network, credential reads, hardware tests or model loading occur here.
The diagnostic contract deliberately excludes tokens, Discord IDs, paths and prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import os
import re
import shutil


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # ready | setup | optional
    detail: str


def is_dave_compatible(version: str | None) -> bool:
    """discord.py added encrypted voice support in v2.7, and fixed it in v2.7.1."""
    if not version:
        return False
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:\.post\d+)?", version)
    return bool(match and tuple(map(int, match.groups())) >= (2, 7, 1))


def evaluate_readiness(*, bot_token: bool, owner_ids: bool, guild_ids: bool,
                       discord_version: str | None, davey: bool, ffmpeg: bool,
                       model: bool, tts: bool, asr: bool) -> list[Check]:
    """Pure diagnostic logic; messages describe capability rather than leaked config."""
    return [
        Check("Bot token", "ready" if bot_token else "setup",
              "Configured outside the repository" if bot_token
              else "Put DISCORD_BOT_TOKEN=... in ~/.star/discord.env"),
        Check("Owner allowlist", "ready" if owner_ids else "setup",
              "Configured" if owner_ids else "Put DISCORD_OWNER_ID=... in ~/.star/discord-settings.env"),
        Check("Guild allowlist", "ready" if guild_ids else "optional",
              "Configured" if guild_ids else "Guilds disabled; owner DMs only"),
        Check("Discord gateway", "ready" if is_dave_compatible(discord_version) else "setup",
              "discord.py supports DAVE voice" if is_dave_compatible(discord_version)
              else "Install discord.py[voice]>=2.7.1"),
        Check("Voice encryption", "ready" if davey else "optional",
              "DAVE dependency present" if davey else "Install Discord voice extras (davey)"),
        Check("STAR Brain", "ready" if model else "setup",
              "Model selected (not contacted)" if model else "Choose a model in STAR desktop Settings"),
        Check("FFmpeg", "ready" if ffmpeg else "optional",
              "Executable found (not run)" if ffmpeg else "Install FFmpeg for Discord audio"),
        Check("Speech synthesis", "ready" if tts else "optional",
              "Kokoro package/models present (not loaded)" if tts else "Install STAR voice dependencies/models"),
        Check("Transcription", "ready" if asr else "optional",
              "Whisper package present (not loaded)" if asr else "Install requirements-voice.txt"),
        Check("Live voice listening", "optional", "Disabled; DAVE voice receive is not validated"),
    ]


def _installed(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _vision_configured() -> bool:
    try:
        from ..desktop_core import Settings, app_data
        settings = Settings.load(app_data() / "settings.json")
        return bool(str(getattr(settings, "vision_model", "") or "").strip())
    except (ImportError, OSError, ValueError, TypeError, AttributeError):
        return False


def feature_checks(source) -> list[Check]:
    """Opt-in switches; reports on/off and obvious gaps, never IDs or paths."""
    try:
        from .dm_mode import DMSettings
        dm = DMSettings.from_env(source)
    except ValueError as exc:
        return [Check("DM chat", "setup", str(exc))]
    checks = [Check("DM chat", "ready" if dm.enabled else "optional",
                    "On: DM the bot like a normal chat" if dm.enabled else "Off (STAR_DISCORD_DM_CHAT=1)")]
    if dm.images:
        vision = _vision_configured()
        checks.append(Check("Image analysis", "ready" if vision else "setup",
                            "On; vision model selected (not contacted)" if vision
                            else "On, but choose a vision model in STAR desktop Settings"))
    else:
        checks.append(Check("Image analysis", "optional", "Off (STAR_DISCORD_DM_IMAGES=1)"))
    screen = str(source.get("STAR_DISCORD_SCREEN_CAPTURE", "0")).strip() == "1"
    checks.append(Check("PC screenshots", "ready" if screen else "optional",
                        "On; every capture needs a button press" if screen
                        else "Off (STAR_DISCORD_SCREEN_CAPTURE=1)"))
    try:
        from .digest_task import DigestConfig
        digest = DigestConfig.from_env(source)
        checks.append(Check("Night School digests", "ready" if digest.enabled else "optional",
                            digest.describe()))
    except (ValueError, PermissionError) as exc:
        checks.append(Check("Night School digests", "setup", str(exc)))
    return checks


def _model_configured() -> bool:
    try:
        from ..desktop_core import Settings, app_data
        settings = Settings.load(app_data() / "settings.json")
        return bool(settings.model and settings.model.strip())
    except (ImportError, OSError, ValueError, TypeError, AttributeError):
        return False


def _voice_models_present() -> bool:
    try:
        from ..voice.engines import model_file
        return all(model_file(name).is_file() for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"))
    except (ImportError, FileNotFoundError, OSError, ValueError):
        return False


def doctor_snapshot(env=None) -> list[Check]:
    """Build a privacy-filtered offline report; it never contacts the Discord API."""
    from .core import AccessPolicy
    source = os.environ if env is None else env
    try:
        policy = AccessPolicy.from_env(source)
        owners = bool(policy.owners)
        guilds = bool(policy.guilds)
    except (ValueError, TypeError):
        owners, guilds = False, False
    token = str(source.get("STAR_DISCORD_BOT_TOKEN", "")).strip()
    return evaluate_readiness(
        bot_token=bool(token and not any(c.isspace() for c in token)),
        owner_ids=owners,
        guild_ids=guilds,
        discord_version=_installed("discord.py"),
        davey=_installed("davey") is not None,
        ffmpeg=shutil.which("ffmpeg") is not None,
        model=_model_configured(),
        tts=(_installed("kokoro-onnx") is not None
             and _installed("onnxruntime") is not None and _voice_models_present()),
        asr=_installed("faster-whisper") is not None,
    ) + feature_checks(source)


def format_checks(checks: list[Check], *, ascii_only: bool = False) -> str:
    """Render rich Discord labels or a Windows-console-safe ASCII doctor.

    Legacy Windows shells commonly use CP1252; printing the rich ✓/✗/•
    symbols from a CLI under that encoding raises UnicodeEncodeError.
    Keep the rich formatting for Discord embeds, but make terminal
    diagnostics usable even before the user has configured Python UTF-8.
    """
    symbols = ({"ready": "[OK]", "setup": "[SETUP]", "optional": "[OPTIONAL]"}
               if ascii_only else
               {"ready": "✓", "setup": "✗", "optional": "•"})
    return "\n".join(f"{symbols[check.status]} **{check.name}:** {check.detail}" for check in checks)
