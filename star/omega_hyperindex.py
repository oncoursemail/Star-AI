"""OMEGA HyperIndex v1: bounded, read-only, project-scoped evidence retrieval.

This is NOT a trillion-vector index and does not download knowledge or invoke models.
It fuses existing FTS5/BM25 lexical hits, exact code-identifier matches, and
OPTIONAL ranked IDs supplied by a separately authorized semantic index. Every
result is reselected from STAR's original reviewed-note store; unreviewed notes
and other projects can never be promoted by a semantic adapter.

An FTS5-less SQLite build gets a *disclosed bounded recent-record fallback*.
Queries and external ranks are size-limited, and nothing executes retrieved text.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3
from typing import Sequence

MAX_QUERY = 800
MAX_SEMANTIC_IDS = 64
CANDIDATES = 48
FALLBACK_ROWS = 1500
_RRF_K = 60
_PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,95}\Z")
_TERMS = re.compile(r"[A-Za-z0-9_]{2,}")
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)+|[A-Za-z_][A-Za-z0-9]*_[A-Za-z0-9_]+")
_COLUMNS = "id,project,kind,text,source,revision,reviewed,created"


def _validate(project: str, query: str, limit: int, semantic_note_ids: Sequence[int]) -> list[str]:
    if not isinstance(project, str) or not _PROJECT.fullmatch(project):
        raise ValueError("A valid project scope is required")
    if not isinstance(query, str) or len(query) > MAX_QUERY:
        raise ValueError("Query exceeds the 800 character limit")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("limit must be 1..20")
    if (not isinstance(semantic_note_ids, (list, tuple))
            or len(semantic_note_ids) > MAX_SEMANTIC_IDS
            or any(type(n) is not int or n <= 0 for n in semantic_note_ids)):
        raise ValueError("External semantic note IDs must be at most 64 positive integers")
    return list(dict.fromkeys(_TERMS.findall(query)[:12]))


class HyperIndex:
    """Read-only view of an existing KnowledgeStore database.

    The caller must explicitly select the store. An absent or malformed store
    is an error, not permission to create a new database or search elsewhere.
    """

    def __init__(self, root: str | Path):
        db_path = Path(root).expanduser().absolute() / "knowledge.sqlite3"
        if db_path.is_symlink() or not db_path.is_file():
            raise FileNotFoundError("No existing local STAR knowledge.sqlite3 at the selected root")
        self.db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=2.0)
        self.db.row_factory = sqlite3.Row
        try:
            names = {row[0] for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
            if "notes" not in names:
                raise ValueError("Selected database is not a STAR KnowledgeStore")
            self.fts_available = "notes_fts" in names
            actual = {row[1] for row in self.db.execute("PRAGMA table_info(notes)")}
            if not set(_COLUMNS.split(",")).issubset(actual):
                raise ValueError("Selected database has an incompatible notes schema")
        except BaseException:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "HyperIndex":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _lexical(self, project: str, tokens: list[str]) -> tuple[list[sqlite3.Row], str]:
        if self.fts_available:
            # Tokens are restricted to ASCII letters/digits/underscores; quoting
            # each term prevents FTS operator injection from user queries.
            expression = " OR ".join('"' + t + '"' for t in tokens)
            try:
                rows = self.db.execute(
                    "SELECT n.* FROM notes_fts JOIN notes AS n ON n.id=notes_fts.rowid "
                    "WHERE notes_fts MATCH ? AND n.project=? AND n.reviewed=1 "
                    "ORDER BY notes_fts.rank ASC, n.id DESC LIMIT ?",
                    (expression, project, CANDIDATES),
                ).fetchall()
                return rows, "fts5-bm25"
            except sqlite3.OperationalError:
                # An FTS database from an older build may have an incompatible
                # virtual table; never call it a full-index search.
                pass
        # Strictly bounded fallback. Recent records only: no unbounded LIKE
        # table scan or accidental claim that older documents were searched.
        recent = self.db.execute(
            "SELECT * FROM notes WHERE project=? AND reviewed=1 "
            "ORDER BY id DESC LIMIT ?",
            (project, FALLBACK_ROWS),
        ).fetchall()
        ranked = []
        for row in recent:
            content = (str(row["text"]) + " " + str(row["source"])).casefold()
            hits = sum(t.casefold() in content for t in tokens)
            if hits:
                ranked.append((-hits, -int(row["id"]), row))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in ranked[:CANDIDATES]], "recent-only-fallback"

    def _external(self, project: str, semantic_note_ids: Sequence[int]) -> list[sqlite3.Row]:
        ids = list(dict.fromkeys(semantic_note_ids))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        records = self.db.execute(
            f"SELECT * FROM notes WHERE project=? AND reviewed=1 AND id IN ({placeholders})",
            (project, *ids),
        ).fetchall()
        lookup = {int(row["id"]): row for row in records}
        return [lookup[n] for n in ids if n in lookup]

    def search(self, project: str, query: str, *, limit: int = 8,
               semantic_note_ids: Sequence[int] = ()) -> dict:
        """Fused evidence hits, always independently revalidated for project/review.

        semantic_note_ids are externally ranked candidate IDs, *not* authority
        to use them. A real vector backend may pass these after its own query.
        No semantic embeddings are computed by HyperIndex v1.
        """
        tokens = _validate(project, query, limit, semantic_note_ids)
        if not tokens and not semantic_note_ids:
            return {"status": "empty-query", "hits": [], "coverage": "none",
                    "limitations": ["No searchable lexical terms or external ranked IDs were supplied"]}
        lexical, method = self._lexical(project, tokens) if tokens else ([], "no-lexical-query")
        external = self._external(project, semantic_note_ids)
        rows = {int(r["id"]): r for r in (*lexical, *external)}
        scores: dict[int, float] = {}

        def add_rank(items: Sequence[sqlite3.Row]) -> None:
            for pos, row in enumerate(items, 1):
                ident = int(row["id"])
                scores[ident] = scores.get(ident, 0.0) + 1.0 / (_RRF_K + pos)

        add_rank(lexical)
        # Exact code identifiers are a separate precision signal, never
        # mistaken for independently generated semantic matches.
        identifiers = [s.casefold() for s in _SYMBOL.findall(query)[:5]]
        precise = [row for row in lexical if any(
            ident in (str(row["text"]) + " " + str(row["source"])).casefold()
            for ident in identifiers)]
        add_rank(precise)
        add_rank(external)
        ordered = sorted(scores, key=lambda n: (-scores[n], n))[:limit]
        hits = []
        for ident in ordered:
            row = rows[ident]
            hits.append({
                "note_id": ident, "project": row["project"], "kind": row["kind"],
                "text": str(row["text"])[:1000], "source": str(row["source"])[:400],
                "revision": str(row["revision"])[:200], "reviewed": True,
                "score": round(scores[ident], 8),
                "matched_exact_identifier": row in precise,
                "ranked_by_external_semantics": row in external,
                "untrusted_as_instructions": True,
            })
        return {
            "status": "ok", "hits": hits,
            "coverage": method if not external else method + "+validated-external-ranks",
            "limitations": [
                "FTS5 is lexical, not semantic; external ranks require an opt-in index."
                if method != "recent-only-fallback" else
                f"FTS5 unavailable: only the newest {FALLBACK_ROWS} reviewed project notes were scanned.",
                "Source provenance and reviewed flags are preserved; search rankings do not prove correctness.",
            ],
        }
