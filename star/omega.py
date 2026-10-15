"""STAR OMEGA: offline knowledge search entry point.

Usage:
  python -m star.omega search /path/to/knowledge PROJECT "DataStore retry" --limit 8

For opt-in failure prediction, use:
  python -m star.roblox_project_preflight /path/to/place --futuresight --module-requires

No model, hosted API, download, file mutation, or Studio session is started.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from .omega_hyperindex import HyperIndex


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STAR OMEGA verified knowledge search")
    actions = parser.add_subparsers(dest="action", required=True)
    search = actions.add_parser("search", help="search an existing reviewed, project-scoped STAR memory store")
    search.add_argument("knowledge_root", type=Path, help="folder containing knowledge.sqlite3")
    search.add_argument("project", help="exact project scope")
    search.add_argument("query", help="literal evidence search query")
    search.add_argument("--limit", type=int, default=8)
    args = parser.parse_args(argv)
    if args.action == "search":
        try:
            with HyperIndex(args.knowledge_root) as index:
                result = index.search(args.project, args.query, limit=args.limit)
            print(json.dumps(result, sort_keys=True, ensure_ascii=True))
            return 0
        except (OSError, sqlite3.DatabaseError, ValueError) as exc:
            print(json.dumps({"status": "invalid", "error": str(exc)[:240]},
                             sort_keys=True, ensure_ascii=True))
            return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
