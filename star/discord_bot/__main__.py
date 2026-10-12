"""Run: python -m star.discord_bot (with the owner's opt-in Discord env vars)."""
from __future__ import annotations

import logging
import sys

from .bot import BotConfig, create_bot


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if len(sys.argv) > 1:
        if sys.argv[1:] != ["doctor"]:
            print("Usage: python -m star.discord_bot [doctor]", file=sys.stderr)
            return 2
        from .health import doctor_snapshot, format_checks
        checks = doctor_snapshot()
        print(format_checks(checks))
        # Optional voice/research capabilities do not block chat-only startup.
        return 2 if any(c.status == "setup" for c in checks) else 0
    try:
        config = BotConfig.from_env()
    except ValueError as exc:
        print(f"STAR Discord configuration error: {exc}", file=sys.stderr)
        return 2
    try:
        create_bot(config).run(config.token, log_handler=None)
    except ImportError:
        print("Install requirements-discord.txt before running the Discord bot", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
