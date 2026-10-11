"""Versioned research watcher for STAR's autonomous evolution experiments.

Source locations are built into trusted code, never supplied by a model.
Retrieved pages and diffs are UNTRUSTED candidate evidence, not approved lessons,
executable instructions, policy changes, or permission to publish software.
This module performs no GitHub writes, self-build, model calls, or releases.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3

import httpx


# Fixed, reviewed URL allowlist. Adding a source requires normal code review.
SOURCES = {
    "roblox-studio-mcp": "https://create.roblox.com/docs/studio/mcp",
    "roblox-external-tools": "https://create.roblox.com/docs/projects/external-tools",
    "luau-typechecking": "https://luau.org/typecheck",
    "github-actions-security": "https://docs.github.com/en/actions/reference/security/secure-use",
    "github-build-attestations": "https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations",
}
MAX_DOCUMENT_BYTES = 1_000_000
MAX_EVIDENCE_CHARS = 16_000
MAX_SOURCES_PER_CHECK = 5
_MEDIA_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain", "text/markdown"})


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ArticleText(HTMLParser):
    """Discard script/style and navigation text before comparing HTML revisions."""

    _SKIP = frozenset({"script", "style", "noscript", "svg", "iframe",
                       "head", "nav", "aside", "footer", "header"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs):
        if tag in self._SKIP:
            self.ignored += 1

    def handle_endtag(self, tag: str):
        if tag in self._SKIP and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str):
        if not self.ignored:
            self.parts.append(data)


def extract_evidence(raw: bytes, media_type: str) -> tuple[str, str]:
    """Return a content fingerprint and bounded plain-text *untrusted* excerpt.

    The fingerprint covers all normalized text, not just the stored excerpt, so a
    changed paragraph beyond the excerpt is still detected.
    """
    media_type = media_type.split(";", 1)[0].strip().lower()
    if media_type not in _MEDIA_TYPES:
        raise ValueError("unsupported-media-type")
    text = raw.decode("utf-8", errors="replace")
    if media_type in {"text/html", "application/xhtml+xml"}:
        parser = _ArticleText()
        parser.feed(text)
        parser.close()
        text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 24:
        raise ValueError("empty-or-insufficient-document")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest, text[:MAX_EVIDENCE_CHARS]


def _header(value: str | None) -> str:
    """Keep validators safe to replay in outbound headers."""
    if not value or len(value) > 200 or not re.fullmatch(r"[\x20-\x7e]+", value):
        return ""
    return value


class ResearchWatcher:
    """Small, synchronous, replay-safe local research ledger.

    Only known HTTPS documents may be fetched, one at a time. Network I/O is
    outside SQLite transactions; an IMMEDIATE transaction reconciles concurrent
    observations. External content is never promoted to a reviewed memory.
    """

    def __init__(self, database: Path):
        self.path = Path(database).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS research_sources (
                source_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                last_digest TEXT,
                etag TEXT NOT NULL DEFAULT '',
                last_modified TEXT NOT NULL DEFAULT '',
                checked_at TEXT,
                last_outcome TEXT NOT NULL DEFAULT 'never',
                error_code TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS research_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL REFERENCES research_sources(source_id),
                previous_digest TEXT,
                digest TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate'
                  CHECK (status = 'candidate')
            );
            CREATE INDEX IF NOT EXISTS idx_research_observations
                ON research_observations(source_id, id DESC);
        """)
        with self.db:
            for source_id, url in SOURCES.items():
                self.db.execute(
                    "INSERT OR IGNORE INTO research_sources(source_id,url) VALUES(?,?)",
                    (source_id, url),
                )
                existing = self.db.execute(
                    "SELECT url FROM research_sources WHERE source_id=?", (source_id,)
                ).fetchone()
                if existing["url"] != url:
                    raise ValueError("Source definition changed; migrate it in reviewed code")

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def status(self, *, limit: int = 20) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("Status limit must be 1..50")
        sources = [dict(row) for row in self.db.execute(
            "SELECT source_id,url,last_digest,checked_at,last_outcome,error_code "
            "FROM research_sources ORDER BY source_id"
        )]
        observations = [dict(row) for row in self.db.execute(
            "SELECT id,source_id,previous_digest,digest,observed_at,status "
            "FROM research_observations ORDER BY id DESC LIMIT ?", (limit,)
        )]
        return {
            "sources": sources,
            "observations": observations,
            "candidate_count": self.db.execute(
                "SELECT COUNT(*) FROM research_observations"
            ).fetchone()[0],
            "trusted_automatically": 0,
            "can_publish": False,
        }

    def evidence(self, observation_id: int) -> dict:
        if isinstance(observation_id, bool) or not isinstance(observation_id, int) or observation_id < 1:
            raise ValueError("Observation ID must be a positive integer")
        row = self.db.execute(
            "SELECT o.id,o.source_id,s.url,o.previous_digest,o.digest,o.excerpt,"
            "o.observed_at,o.status FROM research_observations o "
            "JOIN research_sources s ON s.source_id=o.source_id WHERE o.id=?",
            (observation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("No research observation with that ID")
        return {**dict(row), "untrusted_reference_only": True, "can_grant_permissions": False}

    def nominate(self, observation_id: int, *, home: Path, project: str) -> dict:
        """Send one documented excerpt to the existing human-reviewed lesson queue.

        This never approves a note. The document cannot select the project,
        author its own permissions, or supply code to execute. Repeated attempts
        rely on LessonStore's duplicate detection. The owner must still review
        the candidate in STAR's Projects -> Learning page.
        """
        observation = self.evidence(observation_id)
        from .lessons import LessonStore
        text = observation["excerpt"][:500].strip()
        source = "research:" + observation["source_id"] + ":" + observation["digest"]
        detail = "Untrusted official documentation candidate: " + observation["url"]
        store = LessonStore(Path(home))
        try:
            result = store.capture_inferred(
                project=project, kind="fact", text=text, source_type="doc",
                source=source, evidence=detail[:900],
            )
        finally:
            store.close()
        return {
            "source_id": observation["source_id"],
            "digest": observation["digest"],
            "lesson_id": result.lesson_id,
            "status": result.status,
            "reason": result.reason,
            "automatically_trusted": False,
        }

    def _mark(self, source_id: str, outcome: str, error_code: str = "") -> None:
        with self.db:
            self.db.execute(
                "UPDATE research_sources SET checked_at=?,last_outcome=?,error_code=? "
                "WHERE source_id=?",
                (_utc(), outcome, error_code, source_id),
            )

    def check(self, source_id: str, *, client: httpx.Client | None = None) -> dict:
        """Check one trusted URL using HTTP validators and a bounded response.

        Redirects, authentication, proxies, non-text content, oversized bodies
        and URL substitutions are refused. No network access occurs on import.
        """
        if source_id not in SOURCES:
            raise ValueError("Unknown research source; source URLs are code-controlled")
        spec_url = SOURCES[source_id]
        row = self.db.execute(
            "SELECT last_digest,etag,last_modified FROM research_sources WHERE source_id=?",
            (source_id,),
        ).fetchone()
        headers = {"Accept": "text/html, text/plain;q=0.9",
                   "User-Agent": "STAR-Evolution-Research/1.0"}
        if row["last_digest"]:
            if row["etag"]:
                headers["If-None-Match"] = row["etag"]
            if row["last_modified"]:
                headers["If-Modified-Since"] = row["last_modified"]

        owned = client is None
        client = client or httpx.Client(
            timeout=httpx.Timeout(15, read=20), follow_redirects=False, trust_env=False
        )
        try:
            with client.stream("GET", spec_url, headers=headers, follow_redirects=False) as response:
                if str(response.url) != spec_url:
                    raise ValueError("unexpected-url")
                if response.status_code == 304:
                    if not row["last_digest"]:
                        raise ValueError("not-modified-without-baseline")
                    self._mark(source_id, "unchanged")
                    return {"source_id": source_id, "outcome": "unchanged",
                            "digest": row["last_digest"], "http_status": 304}
                if response.status_code != 200:
                    raise ValueError("http-" + str(response.status_code))
                media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media_type not in _MEDIA_TYPES:
                    raise ValueError("unsupported-media-type")
                declared = response.headers.get("content-length")
                if declared is not None:
                    try:
                        size = int(declared)
                    except ValueError:
                        raise ValueError("invalid-content-length") from None
                    if size < 0 or size > MAX_DOCUMENT_BYTES:
                        raise ValueError("oversized-document")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes(16384):
                    size += len(chunk)
                    if size > MAX_DOCUMENT_BYTES:
                        raise ValueError("oversized-document")
                    chunks.append(chunk)
                digest, excerpt = extract_evidence(b"".join(chunks), media_type)
                etag = _header(response.headers.get("etag"))
                last_modified = _header(response.headers.get("last-modified"))
        except (httpx.HTTPError, ValueError, OSError) as exc:
            # Never copy a remote error body, URL, credential, or traceback to the ledger.
            code = str(exc) if isinstance(exc, ValueError) else "source-unavailable"
            if not re.fullmatch(r"[a-z0-9-]{1,50}", code):
                code = "source-unavailable"
            self._mark(source_id, "error", code)
            return {"source_id": source_id, "outcome": "error", "error_code": code}
        finally:
            if owned:
                client.close()

        # Another STAR process may have checked this URL during the fetch.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            latest = self.db.execute(
                "SELECT last_digest FROM research_sources WHERE source_id=?", (source_id,)
            ).fetchone()["last_digest"]
            outcome = "baseline" if latest is None else ("unchanged" if latest == digest else "changed")
            self.db.execute(
                "UPDATE research_sources SET last_digest=?,etag=?,last_modified=?,"
                "checked_at=?,last_outcome=?,error_code='' WHERE source_id=?",
                (digest, etag, last_modified, _utc(), outcome, source_id),
            )
            observation_id = None
            if outcome != "unchanged":
                cursor = self.db.execute(
                    "INSERT INTO research_observations"
                    "(source_id,previous_digest,digest,excerpt,observed_at,status)"
                    " VALUES(?,?,?,?,?,'candidate')",
                    (source_id, latest, digest, excerpt, _utc()),
                )
                observation_id = cursor.lastrowid
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return {"source_id": source_id, "outcome": outcome,
                "digest": digest, "observation_id": observation_id}

    def check_many(self, source_ids: list[str] | None = None,
                   *, client: httpx.Client | None = None) -> list[dict]:
        """Sequential by design: avoid GitHub/Roblox secondary rate-limit bursts."""
        source_ids = list(SOURCES) if source_ids is None else source_ids
        if (not isinstance(source_ids, list) or not source_ids
                or len(source_ids) > MAX_SOURCES_PER_CHECK
                or any(name not in SOURCES for name in source_ids)
                or len(source_ids) != len(set(source_ids))):
            raise ValueError("Use 1..5 distinct, approved research source IDs")
        return [self.check(source_id, client=client) for source_id in source_ids]


def _default_database() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home() / ".local" / "share")
    return base / "STAR" / "research-watch.sqlite3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only STAR evolution research watcher")
    parser.add_argument("command", choices=("status", "check", "evidence"))
    parser.add_argument("--database", type=Path, default=_default_database())
    parser.add_argument("--sources", nargs="+", choices=list(SOURCES))
    parser.add_argument("--observation", type=int)
    args = parser.parse_args(argv)
    with ResearchWatcher(args.database) as watcher:
        if args.command == "status":
            result = watcher.status()
        elif args.command == "evidence":
            if args.observation is None:
                parser.error("evidence requires --observation ID")
            result = watcher.evidence(args.observation)
        else:
            result = watcher.check_many(args.sources)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
