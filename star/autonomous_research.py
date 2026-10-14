"""Trusted research evidence broker, one bounded follow-up, and local run receipts.

The model can suggest a missing question; it cannot select an endpoint, execute a
tool, change permissions, or decide that its own statements are verified.
Receipts contain only counts and an objective digest, not source text or secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
from time import time
from uuid import uuid4

from .web_search import _safe_results, source_context
from .validation_messages import describe_invalid

MAX_EVIDENCE = 10
FOLLOWUP_LINE = re.compile(r"^FOLLOWUP_QUERY:\s*(.+?)\s*$", re.I | re.M)
TERMS = re.compile(r"[a-z][a-z0-9_-]{3,}", re.I)


def followup_question(critique: str, objective: str) -> str:
    """Accept one related question, never a URL, instruction batch or command."""
    if not isinstance(critique, str) or not isinstance(objective, str):
        return ""
    match = FOLLOWUP_LINE.search(critique[:4000])
    if not match:
        return ""
    candidate = match.group(1).strip()
    if (candidate.upper() in {"NONE", "NO", "N/A"} or
            not 12 <= len(candidate) <= 220 or
            any(ch in candidate for ch in ("<", ">", "{", "}", "\\", "\x60", "\x00")) or
            re.search(r"https?://|www\.|(?:^|\s)(?:file|data):", candidate, re.I)):
        return ""
    source_terms = set(TERMS.findall(objective.casefold()))
    query_terms = set(TERMS.findall(candidate.casefold()))
    noise = {"what", "about", "which", "with", "from", "more", "find",
             "this", "that", "your", "current", "latest", "research"}
    if not (source_terms - noise) & (query_terms - noise):
        return ""
    return candidate


@dataclass
class EvidenceBook:
    """Provenance-preserving search snippets. Never marks sources as verified."""
    sources: list[dict[str, str]] = field(default_factory=list)
    searches: int = 0
    failed_searches: int = 0

    def add(self, raw: list[dict], *, count_search: bool = True) -> int:
        if count_search:
            self.searches += 1
        if not isinstance(raw, list):
            if count_search:
                self.failed_searches += 1
            return 0
        safe = _safe_results(raw, text_field="snippet", limit=MAX_EVIDENCE)
        existing = {row["url"].split("#", 1)[0] for row in self.sources}
        accepted = 0
        for row in safe:
            key = row["url"].split("#", 1)[0]
            if key in existing or len(self.sources) == MAX_EVIDENCE:
                continue
            self.sources.append(row)
            existing.add(key)
            accepted += 1
        if count_search and not safe:
            self.failed_searches += 1
        return accepted

    def context(self, *, max_chars: int = 7500) -> str:
        return source_context(self.sources)[:max_chars]

    def citations(self) -> str:
        if not self.sources:
            return "No retrievable source snippets were available."
        return ("Search snippets retrieved (the pages were not opened or verified):\n" +
                "\n".join(f"- {item['url']}" for item in self.sources))


def _connect(home: Path) -> sqlite3.Connection:
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(home / "research-runs.sqlite3", timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS research_runs(
        id TEXT PRIMARY KEY, project TEXT NOT NULL, objective_sha256 TEXT NOT NULL,
        started_at INTEGER NOT NULL, status TEXT NOT NULL,
        searches INTEGER NOT NULL DEFAULT 0, failed_searches INTEGER NOT NULL DEFAULT 0,
        source_count INTEGER NOT NULL DEFAULT 0, elapsed_ms INTEGER NOT NULL DEFAULT 0,
        peak_concurrency INTEGER NOT NULL DEFAULT 0,
        CHECK(status IN ('running','completed','failed','cancelled'))
    )""")
    return db


def begin_research(home: Path, project: str, objective: str) -> str:
    """A small private audit record: no prompts, article excerpts or API keys."""
    if not isinstance(project, str) or not project.strip() or len(project) > 100:
        raise ValueError(f"Invalid research project: project must be nonblank text of 1-100 characters (got {describe_invalid(project)}). Choose a shorter label.")
    if not isinstance(objective, str) or not 2 <= len(objective.strip()) <= 12000:
        raise ValueError("Invalid research objective: objective must be 2-12000 nonblank text characters. Edit the question.")
    run_id = uuid4().hex
    with _connect(home) as db:
        db.execute("""INSERT INTO research_runs
            (id,project,objective_sha256,started_at,status) VALUES(?,?,?,?,?)""",
            (run_id, project, sha256(objective.encode("utf-8")).hexdigest(),
             int(time()), "running"))
        db.execute("""DELETE FROM research_runs WHERE id NOT IN
            (SELECT id FROM research_runs ORDER BY started_at DESC, rowid DESC LIMIT 500)""")
    return run_id


def finish_research(home: Path, run_id: str, *, status: str, book: EvidenceBook,
                    elapsed_ms: int, peak_concurrency: int) -> None:
    if status not in {"completed", "failed", "cancelled"}:
        raise ValueError("Invalid research completion status: status must be completed, failed or cancelled. Choose one of these values.")
    if not isinstance(book, EvidenceBook) or not 0 <= elapsed_ms <= 4_000_000:
        raise ValueError("Invalid research metric: book must be EvidenceBook and elapsed_ms must be between 0 and 4000000. Correct the metrics.")
    with _connect(home) as db:
        db.execute("""UPDATE research_runs SET status=?,searches=?,failed_searches=?,
            source_count=?,elapsed_ms=?,peak_concurrency=? WHERE id=? AND status='running'""",
            (status, book.searches, book.failed_searches, len(book.sources),
             elapsed_ms, peak_concurrency, run_id))
