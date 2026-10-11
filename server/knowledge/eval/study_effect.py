"""Measure what the generated questions (study job) change, on the three question sets.

Run in the container as user `star`:

    cd /opt/star/knowledge/app && /opt/star/knowledge/venv/bin/python eval/study_effect.py [--scales 0.7,0.8,0.9]

Two views, because only part of the index has questions while the job is running:

  whole index   what a user gets today. Chunks WITH questions get an extra chance, chunks without
                do not, so this view flatters or hurts depending on where the answers are.
  studied only  every mode searches only the chunks that were studied, and only the questions with
                an expected page among them are counted. Every candidate has questions, so "with"
                and "without" are compared fairly. This is the view to decide on.

Modes without `+q` ignore the generated questions completely. `--scales` adds a tuning table for
the question-vector scale on the DEVELOPMENT set only (never tune on heldout.jsonl).
Sends one embedding request per query, one at a time; waits while the server lock exists.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from starkb.evaluate import run_eval  # noqa: E402
from starkb.quiet import wait_while_locked  # noqa: E402
from starkb.store import connect  # noqa: E402

SETS = {"dev30": "questions.jsonl", "heldout40": "heldout.jsonl", "golden25": "golden-task-queries.jsonl"}
MODES = ["bm25", "bm25+q", "vector", "vector+q", "hybrid", "hybrid+q"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/opt/star/knowledge/data/kb.sqlite3"))
    parser.add_argument("--out", type=Path, default=Path("/opt/star/knowledge/data/eval/study-effect.json"))
    parser.add_argument("--scales", default="", help="comma list: tune the question scale on the development set")
    parser.add_argument("--modes", default=",".join(MODES))
    args = parser.parse_args()
    modes = [m for m in args.modes.split(",") if m]
    db = connect(args.db)
    studied = [r[0] for r in db.execute("""SELECT s.text_sha FROM study_log s WHERE s.status IN ('ok','empty')
                                           AND EXISTS (SELECT 1 FROM chunks c WHERE c.text_sha=s.text_sha)""")]
    counts = {"chunks": db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0], "studied_texts": len(studied),
              "questions": db.execute("SELECT COUNT(*) FROM chunk_questions").fetchone()[0]}
    db.close()
    scope = args.out.parent / "studied.txt"
    scope.parent.mkdir(parents=True, exist_ok=True)
    scope.write_text("\n".join(studied) + "\n", encoding="utf-8")
    print(json.dumps(counts))
    out: dict = {"counts": counts, "views": {}}
    print(f"{'set':<10} {'view':<13} {'mode':<10} {'n':>3} {'hit@5':>6} {'r@5':>6} {'mrr@10':>7}")
    for name, file in SETS.items():
        for view, scope_file in (("whole index", None), ("studied only", scope)):
            wait_while_locked()
            result = run_eval(args.db, APP / "eval" / file, modes, scope_file=scope_file, details=False, reuse_query_vectors=True)
            out["views"][f"{name} / {view}"] = result
            for mode, s in result["summary"].items():
                print(f"{name:<10} {view:<13} {mode:<10} {s['n']:>3} {s['hits@5']:>6} {s['recall@5'] or 0:>6.3f} {s['mrr@10'] or 0:>7.3f}")
    if args.scales:
        print("question scale, development set only:")
        out["scales"] = {}
        for scale in [float(x) for x in args.scales.split(",")]:
            for view, scope_file in (("whole index", None), ("studied only", scope)):
                wait_while_locked()
                s = run_eval(args.db, APP / "eval" / SETS["dev30"], ["vector+q"], scope_file=scope_file,
                             question_scale=scale, details=False, reuse_query_vectors=True)["summary"]["vector+q"]
                out["scales"][f"{scale} / {view}"] = s
                print(f"  scale {scale:<5} {view:<13} n={s['n']:>3} hit@5={s['hits@5']:>3} mrr={s['mrr@10']}")
    args.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
