"""One JSON interface for human operators, Claude, Codex and STAR adapters."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .build import build
from .store import SharedBrain, serialize


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--store", type=Path, help="Explicit local store directory; bound to one selected project")
    commands = parser.add_subparsers(dest="command", required=True)
    refresh = commands.add_parser("refresh", help="Official code-only Graphify extraction and incremental import")
    refresh.add_argument("--source", action="append", help="Allowlisted relative code path; repeat for a scoped corpus")
    commands.add_parser("sync", help="Import existing graph; an unattested graph stays freshness unknown")
    query = commands.add_parser("query")
    query.add_argument("question")
    query.add_argument("--budget-chars", type=int, default=3000)
    query.add_argument("--limit", type=int, default=8)
    query.add_argument("--include-stale", action="store_true")
    feedback = commands.add_parser("feedback")
    feedback.add_argument("query_id")
    feedback.add_argument("outcome", choices=("useful", "corrected", "dead_end"))
    feedback.add_argument("--actor", required=True)
    feedback.add_argument("--answer", default="")
    feedback.add_argument("--correction", default="")
    commands.add_parser("lessons")
    commands.add_parser("stats")
    commands.add_parser("tools", help="List the narrow model-facing JSON tool schemas")
    call = commands.add_parser("call", help="Call one configured model-facing tool with JSON arguments")
    call.add_argument("name")
    call.add_argument("arguments", help="A JSON object; no shell or Python expressions")
    call.add_argument("--actor", default="assistant")
    collab = commands.add_parser("coordination")
    collab.add_argument("--collab-root", required=True, type=Path)
    collab.add_argument("--after", default="", help="Opaque cursor from a previous snapshot")
    collab.add_argument("--actor", default="")
    collab.add_argument("--ack", action="store_true", help="Record observed-message receipt; never changes board claims")
    args = parser.parse_args(argv)
    brain = None
    try:
        if args.command == "coordination":
            from .coordination import snapshot
            brain = SharedBrain(args.workspace, args.store)
            result = snapshot(brain, args.collab_root,
                              after=args.after, actor=args.actor, acknowledge=args.ack)
        else:
            brain = SharedBrain(args.workspace, args.store)
            if args.command in {"tools", "call"}:
                from .protocol import SharedBrainTools
                adapter = SharedBrainTools(brain, actor=getattr(args, "actor", "assistant"))
                if args.command == "tools":
                    result = adapter.definitions()
                else:
                    if len(args.arguments) > 10_000:
                        raise ValueError("Tool arguments exceed the JSON input budget")
                    try:
                        result = adapter.call(args.name, json.loads(args.arguments))
                    except Exception:
                        raise ValueError("Tool call rejected by the configured interface") from None
            elif args.command == "refresh":
                result = {"build": build(args.workspace, args.source), "sync": brain.sync()}
            elif args.command == "sync":
                result = brain.sync()
            elif args.command == "query":
                result = brain.query(args.question, budget_chars=args.budget_chars,
                                     limit=args.limit, include_stale=args.include_stale)
            elif args.command == "feedback":
                result = brain.feedback(args.query_id, args.outcome, actor=args.actor,
                                        answer=args.answer, correction=args.correction)
            elif args.command == "lessons":
                result = brain.lessons()
            else:
                result = brain.stats()
        print(serialize(result))
        return 0
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)[:350]},
                         ensure_ascii=False, separators=(",", ":")), file=sys.stderr)
        return 2
    finally:
        if brain is not None:
            brain.close()


if __name__ == "__main__":
    raise SystemExit(main())
