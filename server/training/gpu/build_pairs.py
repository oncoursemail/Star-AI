"""Build (query, passage) training pairs for the embedding fine-tune, with a provenance manifest.

Sources (all rights-clean, see docs/agents/gpu-training-pilot.md):
  * synthetic queries from gen_queries.py (STAR's local open-weight models; JSONL with per-row provenance);
  * the index's own `chunk_questions` (doc2query questions written by STAR's star-quick model on server 1);
  * the passages themselves: Roblox Creator Docs (CC-BY-4.0 prose, MIT code) and Luau docs (MIT).
Never used: any Claude or ChatGPT output, and the evaluation questions (they are only used to FILTER: a
generated query too similar to an evaluation question is dropped, so nothing leaks by accident).

    python build_pairs.py --db kb.sqlite3 --queries q1.jsonl q2.jsonl --out pairs.jsonl [--exclude-eval-pages]
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from common import KNOWLEDGE, QUERY_PREFIX, embed_input

EVAL_FILES = ["questions.jsonl", "heldout.jsonl", "golden-task-queries.jsonl"]
WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def ngrams(text: str, n: int = 6) -> set[tuple]:
    toks = WORD.findall(text.lower())
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def load_eval() -> list[dict]:
    rows = []
    for name in EVAL_FILES:
        for line in (KNOWLEDGE / "eval" / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("//"):
                rows.append(json.loads(line))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--queries", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--exclude-eval-pages", action="store_true",
                    help="leave out every page that is an expected answer of an evaluation question (strict variant)")
    ap.add_argument("--max-jaccard", type=float, default=0.5)
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    chunk = {r[0]: {"path": r[1], "source": r[2], "input": embed_input(r[3], r[4], r[5])} for r in db.execute(
        """SELECT c.text_sha, d.path, d.source, d.title, c.heading, c.text FROM chunks c JOIN docs d ON d.id=c.doc_id
           GROUP BY c.text_sha""")}
    sources = {r[0]: {"repo": r[1], "commit": r[2], "licence": r[3]} for r in
               db.execute("SELECT name, repo, commit_sha, licence FROM sources")}
    evals = load_eval()
    eval_words = [words(e["question"]) for e in evals]
    eval_grams = set().union(*(ngrams(e["question"]) for e in evals))
    eval_pages = {p for e in evals for p in e["expected"]}

    candidates = []  # (query, text_sha, origin, provenance)
    for path in args.queries:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if not row.get("ok"):
                continue
            for field in ("question", "task"):
                candidates.append((row[field], row["text_sha"], f"synthetic-{field}", row["provenance"]))
    for sha, question, model, created in db.execute(
            "SELECT text_sha, question, model, created_at FROM chunk_questions ORDER BY id"):
        candidates.append((question, sha, "doc2query-index", {
            "generator": f"{model} (STAR star-quick on server 1 = JetBrains/Mellum2.1-12B-A2.5B-Thinking Q4_K_M, Apache-2.0)",
            "generated_at": created, "claude_or_chatgpt_involved": False}))

    dropped = Counter()
    seen, pairs = set(), []
    for query, sha, origin, prov in candidates:
        query = " ".join(query.split())
        info = chunk.get(sha)
        if info is None:
            dropped["chunk no longer in index"] += 1
            continue
        if args.exclude_eval_pages and info["path"] in eval_pages:
            dropped["page is an evaluation answer (strict variant)"] += 1
            continue
        qw = words(query)
        if any(len(qw & ew) / max(1, len(qw | ew)) >= args.max_jaccard for ew in eval_words) or (ngrams(query) & eval_grams):
            dropped["too similar to an evaluation question"] += 1
            continue
        key = (query.lower(), sha)
        if key in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(key)
        pairs.append({"anchor": QUERY_PREFIX + query, "positive": info["input"], "text_sha": sha,
                      "path": info["path"], "origin": origin,
                      "provenance": {**prov, "doc_source": sources.get(info["source"], {})}})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    manifest = {
        "pairs": len(pairs), "chunks": len({p["text_sha"] for p in pairs}), "pages": len({p["path"] for p in pairs}),
        "by_origin": Counter(p["origin"] for p in pairs),
        "by_generator": Counter(p["provenance"].get("generator", "?") for p in pairs),
        "eval_pages_in_training": len({p["path"] for p in pairs} & eval_pages), "eval_pages_total": len(eval_pages),
        "dropped": dropped, "strict_variant": args.exclude_eval_pages,
        "claude_or_chatgpt_outputs_used": False,
        "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1, default=dict))
    print(json.dumps(manifest, indent=1, default=dict))


if __name__ == "__main__":
    main()
