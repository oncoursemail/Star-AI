"""Benchmark: chat persistence in conversations.sqlite3 (the SQLite file behind every chat).

STAR opens `desktop_core.Conversations` many times per turn and per interface action (history
window, saving each message, after-turn learning, the chat list). This measures, on a database
of --messages stored messages spread over several projects and chats:

  open_close_ms      Conversations(path) then close(): schema checks and the legacy migration
  add_ms             saving one message (one write transaction)
  snapshot_ms        desktop_core.chat_history_snapshot for a 200-message chat (window + checkpoint)
  digest_ms          conversation_memory.source_digest over those 200 records

    python benchmarks/bench_persistence.py [--messages 20000] [--repeat 40]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def timed(fn, repeat: int) -> float:
    samples = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(samples), 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", type=int, default=20000)
    parser.add_argument("--repeat", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    tmp = tempfile.mkdtemp(prefix="star-bench-")
    os.environ["APPDATA"] = tmp
    os.environ["XDG_DATA_HOME"] = tmp

    from star import conversation_memory
    from star.desktop_core import Conversations, Settings, app_data, chat_history_snapshot

    home = app_data()
    home.mkdir(parents=True, exist_ok=True)
    db = home / "conversations.sqlite3"
    chats = Conversations(db)
    chat = chats.new_chat("STAR")
    for index in range(200):
        chats.add("STAR", "user" if index % 2 == 0 else "assistant", f"message {index} " + "lorem ipsum " * 30,
                  chat_id=chat)
    # The rest of the history: other projects and chats, plus some pre-upgrade ('legacy') rows.
    rows = [(f"Project{i % 6}", "user" if i % 2 else "assistant", "x" * 400, "2026-10-01T12:00:00+00:00",
             f"chat{i % 150}" if i % 40 else "legacy") for i in range(max(0, args.messages - 200))]
    chats.connection.executemany(
        "INSERT INTO messages(project,role,body,created,chat_id) VALUES (?,?,?,?,?)", rows)
    chats.connection.commit()
    chats.close()
    Conversations(db).close()  # migrate the legacy rows once, as the first start of a new version does

    settings = Settings(model="qwen-test")
    chats = Conversations(db)
    records = chats.raw_history_records("STAR", chat)
    result = {
        "messages": args.messages,
        "open_close_ms": timed(lambda: Conversations(db).close(), args.repeat),
        "add_ms": timed(lambda: chats.add("STAR", "event", "benchmark event", chat_id=chat), args.repeat),
        "snapshot_ms": timed(lambda: chat_history_snapshot(settings, home, chat), max(5, args.repeat // 4)),
        "digest_ms": timed(lambda: conversation_memory.source_digest(records), args.repeat),
    }
    chats.close()
    print(json.dumps(result) if args.json else "\n".join(f"{k}: {v}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
