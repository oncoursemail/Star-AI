"""Usage: python -m star.commerce path/to/offer.json (offline, no credentials)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .planning import inspect_offer

_MAX_BYTES = 256 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect an Etsy or Fiverr offer without contacting a marketplace.")
    parser.add_argument("brief", help="A local JSON offer brief, not an API key or exported customer data.")
    args = parser.parse_args(argv)
    try:
        path = Path(args.brief)
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            raise ValueError("Offer JSON file must exist and be no larger than 256 KiB")
        data = json.loads(path.read_text(encoding="utf-8"))
        result = inspect_offer(data)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"STAR commerce planning failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
