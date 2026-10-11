"""Offline candidate commands. No service defaults, network, embedding or activation."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.parse import quote

from .corpus_manifest import CorpusError
from .corpus_plan import build_candidate, plan, readonly_index


def preview(db_path: Path, query: str, *, sources: list[str], top: int = 5,
            budget_chars: int = 8000) -> dict:
    if not sources or not 1 <= len(query.strip()) <= 800 or not 1 <= top <= 10 or not 2000 <= budget_chars <= 20000:
        raise CorpusError("preview requires sources, query 1..800, top 1..10 and budget 2000..20000")
    terms = re.findall(r"[^\W_]+", query, re.UNICODE)[:32]
    if not terms:
        raise CorpusError("query has no searchable terms")
    fts = " OR ".join('"' + term + '"' for term in terms)
    with closing(readonly_index(db_path)) as db:
        marker = db.execute("SELECT value FROM meta WHERE name='candidate_only'").fetchone()
        if marker is None or marker[0] != "true":
            raise CorpusError("preview accepts only explicitly marked candidate indexes")
        known = {r[0] for r in db.execute("SELECT name FROM sources")}
        if len(set(sources)) != len(sources) or not set(sources) <= known:
            raise CorpusError("unknown or duplicate preview source")
        placeholders = ",".join("?" for _ in sources)
        rows = db.execute(f"""SELECT c.id,c.kind,c.heading,c.text,d.path,d.url,d.source,
                      s.repo,s.commit_sha,s.licence,s.attribution,p.metadata,
                      bm25(chunks_fts) AS score FROM chunks_fts
                      JOIN chunks c ON c.id=chunks_fts.rowid JOIN docs d ON d.id=c.doc_id
                      JOIN sources s ON s.name=d.source LEFT JOIN candidate_chunks p ON p.chunk_id=c.id
                      WHERE chunks_fts MATCH ? AND d.source IN ({placeholders})
                      ORDER BY score,c.id LIMIT ?""", (fts, *sources, top)).fetchall()
        passages = []
        used = 0
        for row in rows:
            item = {k: row[k] for k in ("source", "path", "url", "kind", "heading", "text", "licence", "attribution")}
            item["commit"] = row["commit_sha"]
            item["permalink"] = row["repo"].removesuffix(".git") + "/blob/" + row["commit_sha"] + "/" + quote(row["path"], safe="/")
            item["provenance"] = json.loads(row["metadata"]) if row["metadata"] else {
                "warnings": ["preserved baseline source; raw line spans unavailable"]}
            size = len(json.dumps(item, ensure_ascii=True))
            if used + size > budget_chars:
                break
            passages.append(item)
            used += size
    return {"candidate_only": True, "activated": False, "untrusted_reference": True,
            "sources": sources, "passages": passages, "omitted_by_budget": len(rows) - len(passages)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "corpus-candidates.json")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "build-candidate"):
        child = sub.add_parser(command)
        child.add_argument("--sources-dir", type=Path, required=True)
        child.add_argument("--previous", type=Path)
        child.add_argument("--source", action="append")
        if command == "build-candidate":
            child.add_argument("--output", type=Path, required=True)
    child = sub.add_parser("preview")
    child.add_argument("query")
    child.add_argument("--db", type=Path, required=True)
    child.add_argument("--source", action="append", required=True)
    child.add_argument("--top", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = plan(args.manifest, args.sources_dir, previous=args.previous, selected=args.source)
        elif args.command == "build-candidate":
            result = build_candidate(args.manifest, args.sources_dir, args.output,
                                     previous=args.previous, selected=args.source or [])
        else:
            result = preview(args.db, args.query, sources=args.source, top=args.top)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (CorpusError, OSError, sqlite3.Error, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"isError": True, "candidate_only": True, "error": str(exc)[:600]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
