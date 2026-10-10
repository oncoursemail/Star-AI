"""On-device, project-scoped operational analytics for STAR.

No web analytics, telemetry network calls, or invented performance numbers.
Every chart value is read from SQLite task events or conversation records.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import time

VALID_EVENTS = frozenset({'run_started', 'run_succeeded', 'run_failed', 'tool_completed', 'tool_rejected', 'first_token'})


class AnalyticsStore:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=15)
        self.connection.execute('PRAGMA busy_timeout=15000')
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            kind TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            elapsed_ms INTEGER,
            detail TEXT NOT NULL DEFAULT ''
        )''')
        self.connection.execute('CREATE INDEX IF NOT EXISTS analytics_events_by_project ON events (project, recorded_at)')
        self.connection.commit()

    def record(self, project: str, kind: str, *, elapsed_ms: int | None = None,
               detail: str = '', at: datetime | None = None):
        if kind not in VALID_EVENTS:
            raise ValueError('Unsupported analytics event')
        if not project or len(project) > 100 or '\x00' in project:
            raise ValueError('Invalid analytics project')
        if elapsed_ms is not None and (elapsed_ms < 0 or elapsed_ms > 7 * 24 * 3600 * 1000):
            raise ValueError('Invalid elapsed time')
        stamp = (at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec='seconds')
        # Errors are intentionally truncated; never store prompts, tokens, or secrets.
        message = detail[:180].replace('\n', ' ')
        self.connection.execute(
            'INSERT INTO events (project,kind,recorded_at,elapsed_ms,detail) VALUES(?,?,?,?,?)',
            (project, kind, stamp, elapsed_ms, message))
        self.connection.commit()

    def summary(self, project: str, days: int = 14, *, now: datetime | None = None) -> dict:
        if days not in range(1, 91):
            raise ValueError('days out of range')
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        start = (now.date() - timedelta(days=days - 1)).isoformat()
        rows = self.connection.execute(
            'SELECT kind,recorded_at,elapsed_ms,detail FROM events WHERE project=? AND recorded_at>=? ORDER BY id DESC',
            (project, start)).fetchall()
        counts = Counter(kind for kind, _, _, _ in rows)
        daily = Counter(stamp[:10] for kind, stamp, _, _ in rows if kind == 'run_started')
        trend = [{'date': (now.date() - timedelta(days=days - 1 - i)).isoformat(),
                  'runs': daily.get((now.date() - timedelta(days=days - 1 - i)).isoformat(), 0)}
                 for i in range(days)]
        durations = [elapsed for kind, _, elapsed, _ in rows
                     if kind == 'run_succeeded' and elapsed is not None]
        return {
            'started': counts['run_started'],
            'succeeded': counts['run_succeeded'],
            'failed': counts['run_failed'],
            'tools': counts['tool_completed'],
            'rejected': counts['tool_rejected'],
            'median_ms': sorted(durations)[len(durations) // 2] if durations else None,
            'trend': trend,
            'recent': [{'type': kind, 'at': stamp, 'duration_ms': elapsed, 'detail': detail}
                       for kind, stamp, elapsed, detail in rows[:12]],
            'period_days': days,
        }

    def close(self):
        self.connection.close()


def get_dashboard(app_home: Path, project: str, days: int = 14) -> dict:
    home = Path(app_home)
    with sqlite3.connect(str(home / 'conversations.sqlite3'), timeout=8) if (home / 'conversations.sqlite3').exists() else sqlite3.connect(':memory:') as c:
        try:
            messages = c.execute('SELECT COUNT(*) FROM messages WHERE project=? AND role=?', (project, 'user')).fetchone()[0]
        except sqlite3.OperationalError:
            messages = 0
    store = AnalyticsStore(home / 'analytics.sqlite3')
    try:
        snapshot = store.summary(project, days)
    finally:
        store.close()
    snapshot['messages'] = messages
    snapshot['project'] = project
    return snapshot
