"""Offline retrieval evaluation of an embedding model with the knowledge service's own eval code.

    python eval_retrieval.py --model <hf id or dir> --db kb.sqlite3 --work <dir> --tag base
    python eval_retrieval.py --compare <dir>/eval-base.json <dir>/eval-ft.json

Writes <work>/eval-<tag>.json with recall@k / MRR for the 30 development, 40 held-out and 25 golden-prompt
questions (server/knowledge/eval/*.jsonl) in `vector` and `hybrid` modes. `--compare` prints per-question
paired changes at rank 5 (wins / losses) and an exact one-sided sign test on the discordant questions.
"""
from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path
import sys

from common import KNOWLEDGE, LocalBrain, http_encoder, load_model, reembed_copy, st_encoder

SETS = {"dev": "questions.jsonl", "heldout": "heldout.jsonl", "golden": "golden-task-queries.jsonl"}


def evaluate(model_name: str, src_db: Path, work: Path, tag: str, modes: list[str], sets: list[str]) -> dict:
    import starkb.search as search
    from starkb.evaluate import run_eval
    if model_name.startswith("http://"):   # an exported GGUF served by llama.cpp on this PC
        encode = http_encoder(model_name)
    else:
        encode = st_encoder(load_model(model_name))
    db = work / f"kb-{tag}.sqlite3"
    if not db.exists():
        info = reembed_copy(src_db, db, encode, log=lambda m: print(m, file=sys.stderr))
        print(f"re-embedded {info}", file=sys.stderr)
    search.Brain = lambda *a, **k: LocalBrain(encode)  # the eval builds its own Searcher
    out = {"model": model_name, "tag": tag, "sets": {}}
    for name in sets:
        res = run_eval(db, KNOWLEDGE / "eval" / SETS[name], modes, details=True)
        out["sets"][name] = {"summary": res["summary"],
                             "ranks": {m: {r["id"]: r["rank"] for r in rows} for m, rows in res["details"].items()}}
        print(name, " | ".join(f"{m} r@5={s['hits@5']}/{s['n']} r@10={round(s['recall@10'] * s['n'])} "
                               f"mrr={s['mrr@10']}" for m, s in res["summary"].items()))
    return out


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(comb(n, i) for i in range(wins, n + 1)) / 2 ** n


def compare(a_path: Path, b_path: Path, k: int = 5) -> dict:
    a, b = json.loads(a_path.read_text()), json.loads(b_path.read_text())
    report = {}
    for name, sa in a["sets"].items():
        sb = b["sets"].get(name)
        if not sb:
            continue
        for mode, ranks_a in sa["ranks"].items():
            ranks_b = sb["ranks"].get(mode, {})
            hit = lambda r: r is not None and r <= k  # noqa: E731
            wins = [q for q in ranks_a if not hit(ranks_a[q]) and hit(ranks_b.get(q))]
            losses = [q for q in ranks_a if hit(ranks_a[q]) and not hit(ranks_b.get(q))]
            row = {"a": sum(hit(r) for r in ranks_a.values()), "b": sum(hit(r) for r in ranks_b.values()),
                   "n": len(ranks_a), "wins": wins, "losses": losses,
                   "p_one_sided": round(sign_test(len(wins), len(losses)), 4)}
            report[f"{name}/{mode}"] = row
            print(f"{name:8s} {mode:8s} r@{k} {row['a']}/{row['n']} -> {row['b']}/{row['n']}  "
                  f"+{len(wins)} -{len(losses)}  p={row['p_one_sided']}  wins={wins} losses={losses}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="HF id / local dir, or http://host:port of a llama.cpp embedding server")
    ap.add_argument("--db", type=Path)
    ap.add_argument("--work", type=Path, default=Path("."))
    ap.add_argument("--tag", default="base")
    ap.add_argument("--modes", default="vector,hybrid")
    ap.add_argument("--sets", default="dev,heldout,golden")
    ap.add_argument("--compare", nargs=2, type=Path)
    args = ap.parse_args()
    if args.compare:
        compare(*args.compare)
        return
    out = evaluate(args.model, args.db, args.work, args.tag, args.modes.split(","), args.sets.split(","))
    path = args.work / f"eval-{args.tag}.json"
    path.write_text(json.dumps(out, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
