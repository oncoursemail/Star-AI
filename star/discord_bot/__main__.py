"""Run: python -m star.discord_bot (with the owner's opt-in Discord env vars)."""
from __future__ import annotations

import logging
import sys

from .bot import BotConfig, create_bot


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
