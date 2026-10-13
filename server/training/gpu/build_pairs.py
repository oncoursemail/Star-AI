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
# Only the indexed documentation sources and known local model families are
# eligible. Metadata is an unverified declaration, never an attestation.
_ALLOWED_LICENCES = frozenset({"CC-BY-4.0", "MIT"})
_LOCAL_GENERATORS = ("qwen", "mellum", "star-quick", "local-open-model")
_FORBIDDEN_GENERATORS = ("chatgpt", "claude", "codex", "openai", "anthropic", "gemini", "gpt-")


def _trusted_source(source: dict | None) -> bool:
    return (isinstance(source, dict)
            and source.get("licence") in _ALLOWED_LICENCES
            and all(isinstance(source.get(field), str) and source[field].strip()
                    for field in ("repo", "commit")))


def _trusted_generator(name: object) -> bool:
    if not isinstance(name, str) or not name.strip():
        return False
    lowered = name.lower()
    return (not any(blocked in lowered for blocked in _FORBIDDEN_GENERATORS)
            and any(allowed in lowered for allowed in _LOCAL_GENERATORS))


def _trusted_provenance(prov: object, source: dict, *, model: object = None) -> bool:
    if not isinstance(prov, dict) or prov.get("claude_or_chatgpt_involved") is not False:
        return False
    if "doc_source" in prov and prov["doc_source"] != source:
        return False
    return _trusted_generator(model if model is not None else prov.get("generator"))


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
    # GROUP BY text_sha picks an arbitrary document path and silently discards
    # conflicting lineage. Keep every alias for evaluation and licence checks,
    # choosing the first indexed chunk only for deterministic positive text.
    chunk: dict[str, dict] = {}
    lineage: dict[str, list[tuple[str, str]]] = {}
    for sha, path, source, title, heading, body in db.execute(
            """SELECT c.text_sha, d.path, d.source, d.title, c.heading, c.text
               FROM chunks c JOIN docs d ON d.id=c.doc_id ORDER BY c.id, d.id"""):
        if sha not in chunk:
            chunk[sha] = {"path": path, "source": source, "input": embed_input(title, heading, body)}
        lineage.setdefault(sha, []).append((path, source))
    sources = {r[0]: {"repo": r[1], "commit": r[2], "licence": r[3]} for r in
               db.execute("SELECT name, repo, commit_sha, licence FROM sources")}
    evals = load_eval()
    eval_words = [words(e["question"]) for e in evals]
    eval_grams = set().union(*(ngrams(e["question"]) for e in evals))
    eval_pages = {p for e in evals for p in e["expected"]}
    # Strict page exclusion applies to the *content hash*, not the path
    # arbitrarily selected to represent that hash.
    excluded_shas = {sha for sha, entries in lineage.items()
                     if any(path in eval_pages for path, _ in entries)}
    untrusted_shas = {sha for sha, entries in lineage.items()
                      if any(not _trusted_source(sources.get(source))
                             for _, source in entries)}

    candidates = []  # (query, text_sha, origin, provenance, raw model)
    for path in args.queries:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if not row.get("ok"):
                continue
            for field in ("question", "task"):
                candidates.append((row.get(field), row.get("text_sha"), f"synthetic-{field}",
                                   row.get("provenance"), None))
    for sha, question, model, created in db.execute(
            "SELECT text_sha, question, model, created_at FROM chunk_questions ORDER BY id"):
        candidates.append((question, sha, "doc2query-index", {
            "generator": f"{model} (STAR star-quick on server 1 = JetBrains/Mellum2.1-12B-A2.5B-Thinking Q4_K_M, Apache-2.0)",
            "generated_at": created, "claude_or_chatgpt_involved": False}, model))

    dropped = Counter()
    seen, pairs = set(), []
    for query, sha, origin, prov, model in candidates:
        if not isinstance(query, str) or not query.strip():
            dropped["invalid query"] += 1
            continue
        query = " ".join(query.split())
        info = chunk.get(sha)
        if info is None:
            dropped["chunk no longer in index"] += 1
            continue
        if args.exclude_eval_pages and sha in excluded_shas:
            dropped["page is an evaluation answer (strict variant)"] += 1
            continue
        if sha in untrusted_shas:
            dropped["untrusted document source"] += 1
            continue
        if not _trusted_provenance(prov, sources[info["source"]], model=model):
            dropped["untrusted query provenance"] += 1
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
