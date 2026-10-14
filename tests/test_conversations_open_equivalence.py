"""Opening conversations.sqlite3 no longer reads every message, with the same stored result.

`Conversations.__init__` runs the legacy-chat migration on every open. It used to be
`INSERT OR IGNORE ... SELECT ... FROM messages WHERE chat_id='legacy' GROUP BY project`, a scan
of the whole messages table. `LEGACY_CHAT_MIGRATION` walks the project index instead. These
tests apply both statements to the same random databases and compare the chats tables, and
check that source_digest still produces the original bytes.
"""
import hashlib
import json
import random
import sqlite3

from star import conversation_memory
from star.desktop_core import LEGACY_CHAT_MIGRATION, Conversations

OLD_MIGRATION = ("INSERT OR IGNORE INTO chats (project,id,title,created,updated) "
                 "SELECT project,'legacy','Previous conversation',MIN(created),MAX(created) "
                 "FROM messages WHERE chat_id='legacy' GROUP BY project")

PROJECTS = ("STAR", "Obby", "", " ", "a", "A", "été", "名字", "Tycoon::chat::x", "z" * 90)


def _random_database(path, rng: random.Random):
    chats = Conversations(path)          # creates the schema (and migrates an empty table)
    db = chats.connection
    for _ in range(rng.randint(0, 120)):
        project = rng.choice(PROJECTS)
        chat = "legacy" if rng.random() < 0.4 else f"c{rng.randint(0, 5)}"
        stamp = f"2026-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}T0{rng.randint(0, 9)}:00:00+00:00"
        db.execute("INSERT INTO messages(project,role,body,created,chat_id) VALUES (?,?,?,?,?)",
                   (project, rng.choice(("user", "assistant", "event")), "body", stamp, chat))
    # Some projects already have their legacy row (possibly with other dates or a renamed title).
    for project in rng.sample(PROJECTS, rng.randint(0, 4)):
        db.execute("INSERT OR IGNORE INTO chats(project,id,title,created,updated) VALUES (?,?,?,?,?)",
                   (project, "legacy", rng.choice(("Previous conversation", "Renamed")), "2025", "2025"))
    for project in rng.sample(PROJECTS, rng.randint(0, 3)):
        db.execute("INSERT OR IGNORE INTO chats(project,id,title,created,updated) VALUES (?,?,?,?,?)",
                   (project, "c1", "New chat", "2026", "2026"))
    db.commit()
    chats.close()


def _chats_after(path, statement):
    db = sqlite3.connect(path)
    try:
        with db:
            db.execute(statement)
        return sorted(db.execute("SELECT project,id,title,created,updated FROM chats").fetchall())
    finally:
        db.close()


def test_legacy_migration_inserts_exactly_what_the_full_scan_inserted(tmp_path):
    rng = random.Random(1013)
    for index in range(150):
        source = tmp_path / f"db{index}.sqlite3"
        _random_database(source, rng)
        copy = tmp_path / f"db{index}-copy.sqlite3"
        copy.write_bytes(source.read_bytes())
        assert _chats_after(source, OLD_MIGRATION) == _chats_after(copy, LEGACY_CHAT_MIGRATION), index


def test_open_still_creates_the_previous_conversation_for_pre_upgrade_messages(tmp_path):
    path = tmp_path / "conversations.sqlite3"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, "
               "role TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL)")
    db.executemany("INSERT INTO messages(project,role,body,created) VALUES (?,?,?,?)",
                   [("STAR", "user", "old question", "2025-01-02"), ("STAR", "assistant", "old answer", "2025-01-03"),
                    ("Obby", "user", "q", "2025-02-01")])
    db.commit()
    db.close()
    chats = Conversations(path)
    try:
        assert chats.list_chats("STAR") == [{"id": "legacy", "title": "Previous conversation",
                                            "created": "2025-01-02", "updated": "2025-01-03"}]
        assert [c["id"] for c in chats.list_chats("Obby")] == ["legacy"]
        assert chats.recent("STAR", chat_id="legacy") == [("user", "old question", "2025-01-02"),
                                                          ("assistant", "old answer", "2025-01-03")]
    finally:
        chats.close()


def test_migration_reads_the_index_not_the_table(tmp_path):
    chats = Conversations(tmp_path / "conversations.sqlite3")
    try:
        plan = " | ".join(row[-1] for row in chats.connection.execute("EXPLAIN QUERY PLAN " + LEGACY_CHAT_MIGRATION))
    finally:
        chats.close()
    assert "SCAN messages" not in plan
    assert "idx_chat_messages" in plan


def _reference_digest(records):
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps({key: record[key] for key in conversation_memory._FIELDS}, ensure_ascii=False,
                                 sort_keys=True, separators=(',', ':')).encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def test_source_digest_bytes_are_unchanged():
    rng = random.Random(7)
    texts = ("", "plain", "quote \" and \\ backslash", "line\nbreak\ttab", "é名\U0001f600", "\x00\x1f",
             "</script>", "퟿")
    for _ in range(300):
        records = [{"id": i + 1, "role": rng.choice(("user", "assistant", "event")), "body": rng.choice(texts) * 3,
                    "created": "2026-10-13T00:00:00+00:00", "status": rng.choice(("complete", "failed")),
                    "reply_to": rng.choice((None, i))} for i in range(rng.randint(0, 12))]
        assert conversation_memory.source_digest(records) == _reference_digest(records)
