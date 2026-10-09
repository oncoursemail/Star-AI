"""Local project-scoped memories and loss-aware checkpoints (not unlimited context)."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Memory:
    def __init__(self, db: Path):
        db.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db)
        self.db.execute("CREATE TABLE IF NOT EXISTS checkpoints (project TEXT PRIMARY KEY, summary TEXT NOT NULL, updated TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, project TEXT, event TEXT NOT NULL, at TEXT NOT NULL)")
        self.db.commit()

    def get(self, project: str) -> str:
        row = self.db.execute("SELECT summary FROM checkpoints WHERE project=?", (project,)).fetchone()
        return row[0] if row else ""

    def put(self, project: str, summary: str):
        if not summary.strip():
            raise ValueError("Refusing empty checkpoint")
        self.db.execute("INSERT INTO checkpoints(project,summary,updated) VALUES(?,?,?) ON CONFLICT(project) DO UPDATE SET summary=excluded.summary,updated=excluded.updated", (project, summary, utc_now()))
        self.db.commit()

    def event(self, project: str, event: dict):
        self.db.execute("INSERT INTO events(project,event,at) VALUES(?,?,?)", (project, json.dumps(event, ensure_ascii=False), utc_now()))
        self.db.commit()

    def close(self):
        self.db.close()


async def compact(client, model: str, project: str, prior: str, messages: list[dict]) -> str:
    """Compact context and keep raw session archives for retrieving omitted facts."""
    def redacted(obj):
        if isinstance(obj, dict):
            if obj.get("type") == "image_url":
                return {"type": "image_url", "image_url": "[original image retained separately in active context]"}
            return {str(k): redacted(v) for k,v in obj.items()}
        if isinstance(obj, list):
            return [redacted(v) for v in obj]
        return obj
    text = json.dumps(redacted(messages), ensure_ascii=False, default=str)
    result = await client.chat.completions.create(
        model=model, temperature=0,
        messages=[
            {"role": "system", "content": "Create a factual project checkpoint. Record requirements, approved decisions, exact files, completed changes, failures, unresolved questions and next actions. Never invent outcomes. Keep source IDs, caveats and tests. This is a lossy summary; exact details remain in archived logs."},
            {"role": "user", "content": f"PROJECT: {project}\nEARLIER CHECKPOINT:\n{prior}\nNEW TRANSCRIPT:\n{text[-18000:]}"},
        ], max_tokens=1300,
    )
    summary = result.choices[0].message.content or ""
    if not summary.strip():
        raise RuntimeError("Compaction returned an empty checkpoint; original history is unchanged")
    return summary
