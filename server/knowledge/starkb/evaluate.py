"""Retrieval evaluation: recall@k, MRR@10 and latency for each search mode.

A question counts as answered at rank r when the r-th returned passage comes from one of the
question's expected source files. All modes use the same post-processing (max 2 passages per page).
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics

from .search import Searcher


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def load_questions(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            row = json.loads(line)
            if not row.get("id") or not row.get("question") or not row.get("expected"):
                raise ValueError("question needs id, question, expected")
            rows.append(row)
    return rows


def run_eval(db_path: Path, questions_path: Path, modes: list[str], *, scope_embedded: bool = False,
             rerank_n: int = 15) -> dict:
    questions = load_questions(questions_path)
    searcher = Searcher(db_path, scope_embedded=scope_embedded)
    known = {r[0] for r in searcher.db.execute("SELECT path FROM docs")}
    for q in questions:  # a typo in an expected path must fail loudly, not look like a miss
        for path in q["expected"]:
            if path not in known:
                raise ValueError(f"{q['id']}: expected path not in index: {path}")
    summary, details = {}, {}
    for mode in modes:
        ranks, totals, stages = [], [], {}
        rows = []
        for q in questions:
            # "vector+fallback" is what the service serves by default on a partly embedded index
            real, fallback = (mode[:-9], True) if mode.endswith("+fallback") else (mode, False)
            passages, timing = searcher.search(q["question"], mode=real, top=10, per_doc=2, rerank_n=rerank_n,
                                               fallback=fallback)
            rank = next((p.rank for p in passages if p.path in q["expected"]), None)
            ranks.append(rank)
            totals.append(timing["total_ms"])
            for key, value in timing.items():
                stages.setdefault(key, []).append(value)
            rows.append({"id": q["id"], "type": q.get("type"), "rank": rank, "timing_ms": timing,
                         "top5": [f"{p.path}#{p.heading}" for p in passages[:5]]})
        n = len(questions)
        by_type: dict[str, list] = {}
        for q, rank in zip(questions, ranks):
            by_type.setdefault(q.get("type") or "untyped", []).append(rank)
        summary[mode] = {
            "n": n,
            "recall@1": round(sum(1 for r in ranks if r and r <= 1) / n, 4),
            "recall@3": round(sum(1 for r in ranks if r and r <= 3) / n, 4),
            "recall@5": round(sum(1 for r in ranks if r and r <= 5) / n, 4),
            "recall@10": round(sum(1 for r in ranks if r and r <= 10) / n, 4),
            "mrr@10": round(sum(1.0 / r for r in ranks if r) / n, 4),
            "hits@5": sum(1 for r in ranks if r and r <= 5),
            "recall@5_by_type": {t: f"{sum(1 for r in rs if r and r <= 5)}/{len(rs)}" for t, rs in sorted(by_type.items())},
            "latency_ms": {"mean": round(statistics.fmean(totals), 1), "median": round(statistics.median(totals), 1),
                           "p95": round(_pct(totals, 0.95), 1), "max": round(max(totals), 1)},
            "stage_mean_ms": {k: round(statistics.fmean(v), 1) for k, v in stages.items() if k != "total_ms"},
            "missed@5": [q["id"] for q, r in zip(questions, ranks) if not r or r > 5],
        }
        details[mode] = rows
    out = {
        "questions_file": str(questions_path), "scope_embedded": scope_embedded,
        "chunks_total": searcher.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
        "chunks_embedded": searcher.embedded_count(),
        "sources": {n: {"commit": s["commit_sha"], "commit_date": s["commit_date"]} for n, s in searcher.sources.items()},
        "rerank_n": rerank_n, "summary": summary, "details": details,
    }
    searcher.close()
    return out
