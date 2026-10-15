"""Read-only command line view of STAR's business research hypotheses."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from .opportunities import load_catalog


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Browse unvalidated STAR business hypotheses; no stores or payments are accessed."
    )
    parser.add_argument("--category", default="", help="Filter by exact catalog category")
    parser.add_argument("--limit", type=int, default=12, help="Maximum ideas to display (1–66)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable text")
    args = parser.parse_args()
    if not 1 <= args.limit <= 66:
        parser.error("--limit must be between 1 and 66")
    catalog = load_catalog()
    selected = [o for o in catalog if not args.category or o.category == args.category]
    selected.sort(key=lambda o: ("ABC".index(o.priority), o.id))
    selected = selected[:args.limit]
    if args.json:
        print(json.dumps({"status": "unvalidated_research_only",
                          "opportunities": [asdict(o) for o in selected]}, indent=2))
    else:
        print("STAR opportunity research — unvalidated hypotheses; NOT real sales")
        for o in selected:
            print(f"{o.id:02} | [{o.priority}] {o.name} | {o.proposed_test_price} | {o.category}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
