1. **Cascade does nothing because foreign key enforcement is off by default.** SQLite parses the `REFERENCES ... ON DELETE CASCADE` clause, but only enforces it when `PRAGMA foreign_keys = ON` has been run, and that setting is **per connection** (it is not stored in the file and cannot be changed inside a transaction). Run it every time you open a connection.

2. **`database is locked`** means another connection holds the write lock. SQLite allows only one writer at a time, even in WAL mode. Make writers wait instead of failing with a busy timeout, use WAL so readers do not block the writer, keep write transactions short, and start transactions that will write with `BEGIN IMMEDIATE` so they take the write lock up front. Simplest robust design: send all writes through one connection or thread.

```python
def open_db(path):
    con = sqlite3.connect(path, timeout=5.0, isolation_level=None)  # timeout = busy timeout
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

con.execute("BEGIN IMMEDIATE")
try:
    con.execute("DELETE FROM players WHERE id = ?", (player_id,))
    con.execute("COMMIT")
except Exception:
    con.execute("ROLLBACK")
    raise
```

Existing orphan rows stay: clean them once with `DELETE FROM inventory WHERE player_id NOT IN (SELECT id FROM players)` and check with `PRAGMA foreign_key_check`.
