# SQL (PostgreSQL and SQLite) for STAR (research, checked 2026-10-13)

Status (verified 2026-10-13): **PostgreSQL 18** is the newest major release (GA 2025-09-25; current minor 18.6; supported until 2030-11-14). Supported majors: 18.6, 17.11, 16.15, 15.19, 14.24; **14 reaches end of life on 2026-11-12** [1]. **PostgreSQL 19 is in beta** (Beta 4 announced 2026-09-24), not released [1]. **SQLite 3.54.0** was released 2026-10-09; 3.53.0 (2026-04-09) fixed a WAL-reset corruption bug and added `ALTER TABLE ... ADD/DROP` of `NOT NULL` and `CHECK` constraints [2][3]. SQLite 3.52.0 was withdrawn and its features moved to 3.53.0 [3]. PostgreSQL 18 feature list below comes from the official announcement and release notes [4][5]; the release-notes page itself timed out during this check, so fine details such as exact GUC names should be confirmed there.

---

## 1. Mental model

- SQL is **declarative and set-based**: you describe the result, the planner chooses the algorithm. Think in sets and joins, not loops. One `UPDATE ... FROM` beats 10,000 single-row updates from application code.
- A table is an unordered multiset. **No `ORDER BY` means no guaranteed order**, even if it "always" came back sorted.
- Logical evaluation order of a `SELECT`: `FROM`/`JOIN` -> `WHERE` -> `GROUP BY` -> `HAVING` -> window functions -> `SELECT` list -> `DISTINCT` -> `ORDER BY` -> `LIMIT/OFFSET`. That is why a `SELECT` alias cannot be used in `WHERE` (but can in `ORDER BY`; PostgreSQL also allows output-column names in `GROUP BY`).
- **Three-valued logic**: `NULL` means unknown. `NULL = NULL` is `NULL` (not true); `WHERE x <> 5` drops rows where x is NULL; `NOT IN (subquery)` returns no rows if the subquery yields any NULL. Use `IS NULL`, `IS DISTINCT FROM`, `COALESCE`, `NOT EXISTS`.
- PostgreSQL is a **client/server** database with MVCC, roles, many types and extensions. SQLite is an **embedded library**: the database is one file, the "server" is your process, concurrency is one writer at a time.
- Schema is code: version it with migrations; constraints (PK, FK, UNIQUE, CHECK, NOT NULL) are the cheapest bug prevention you have.

## 2. Type system

### PostgreSQL

- Strong static typing per column: `integer`/`bigint`, `numeric(p,s)` (exact; use for money), `real`/`double precision` (inexact), `text`/`varchar(n)` (same performance; `text` + CHECK is idiomatic), `boolean`, `bytea`, `date`, `timestamp` vs **`timestamptz`** (use `timestamptz`; it stores UTC and converts on display), `interval`, `uuid`, `jsonb` (binary, indexable) vs `json` (text, keeps formatting), arrays (`int[]`), ranges/multiranges (`tstzrange`), enums, composite types, domains.
- Identity columns: `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY` (preferred over `serial`).
- **UUIDv7** (PG 18): `uuidv7()` returns time-ordered UUIDs, much friendlier to B-tree index locality than random v4; `uuidv4()` is an alias of `gen_random_uuid()` [4][5].
- **Generated columns**: `GENERATED ALWAYS AS (expr) STORED` (computed on write) and, new in PG 18, **VIRTUAL** (computed on read), which is the **default** when neither keyword is given [4][5].
- Casting: `'42'::int`, `CAST(x AS numeric)`. Implicit casts are limited; `integer / integer` is integer division (`5/2 = 2`); cast one side to `numeric`.

### SQLite

- **Dynamic typing with type affinity** [6]: a column declared `INTEGER` can hold `'hello'`. The declared type only gives an affinity (INTEGER, REAL, NUMERIC, TEXT, BLOB) that **tries** to convert values. `VARCHAR(10)` does not limit length.
- **STRICT tables** (3.37+) [7]: `CREATE TABLE t (...) STRICT;` enforces `INT`, `INTEGER`, `REAL`, `TEXT`, `BLOB`, `ANY` and raises `SQLITE_CONSTRAINT_DATATYPE` on mismatch. Use STRICT for new schemas.
- `INTEGER PRIMARY KEY` is an alias of the 64-bit `rowid` (auto-assigned). `AUTOINCREMENT` only prevents reuse of deleted ids and costs extra; usually unnecessary.
- No native boolean (0/1), date/time stored as TEXT ISO-8601, REAL Julian day, or INTEGER Unix time; functions `datetime()`, `unixepoch()`, `strftime()`.
- JSON: `json_*` functions on TEXT, and **JSONB** (3.45+) binary format via `jsonb()` and `jsonb_*` functions; 3.53 adds `json_array_insert()`/`jsonb_array_insert()` [3].
- Generated columns: `VIRTUAL` (default) or `STORED` (3.31+).

## 3. Runtime: transactions, MVCC, locking and concurrency

### PostgreSQL

- Every statement runs in a transaction (autocommit unless `BEGIN`). **MVCC**: readers never block writers and writers never block readers; old row versions are cleaned by **VACUUM** (autovacuum). Long-running transactions prevent cleanup and cause **bloat**.
- Isolation levels [8]: `READ COMMITTED` (default; each statement sees a fresh snapshot), `REPEATABLE READ` (snapshot for the whole transaction; concurrent update of the same row raises `could not serialize access due to concurrent update`), `SERIALIZABLE` (SSI; may raise `could not serialize access due to read/write dependencies among transactions`, SQLSTATE `40001`). Applications using RR/SERIALIZABLE **must retry** on 40001.
- Row locks: `SELECT ... FOR UPDATE` (lock for modification), `FOR NO KEY UPDATE`, `FOR SHARE`, `SKIP LOCKED` (job queues), `NOWAIT`. Deadlocks are detected and one transaction is aborted (`deadlock detected`, 40P01): lock rows in a consistent order.
- DDL takes strong locks: `ALTER TABLE` can block all traffic while waiting behind a long query. Use `SET lock_timeout = '3s'` in migrations, `CREATE INDEX CONCURRENTLY`, `ADD CONSTRAINT ... NOT VALID` then `VALIDATE CONSTRAINT`. PG 18 extends `NOT VALID` to `NOT NULL` constraints [10].
- **Asynchronous I/O** (PG 18) [4]: a new AIO subsystem (`io_method` setting: `worker` default on all platforms, `io_uring` on Linux, `sync` for the old behaviour) speeds up sequential scans, bitmap heap scans and VACUUM, reported up to 3x for storage reads.
- Connections are processes (expensive, ~MBs each): use a pool (PgBouncer, or the driver's pool) and keep `max_connections` modest.

### SQLite

- One writer at a time per database file; many readers. Locking modes [9]:
  - Default **rollback journal**: a writer blocks readers during commit.
  - **WAL mode** (`PRAGMA journal_mode=WAL;`, persistent): readers do not block the writer and the writer does not block readers; still **one writer**. Checkpoints copy WAL back into the db (`wal_autocheckpoint`). WAL does not work over network filesystems.
- `SQLITE_BUSY` / `database is locked`: another connection holds the write lock. Fix: `PRAGMA busy_timeout = 5000;` (wait instead of failing), keep write transactions short, use `BEGIN IMMEDIATE` for transactions that will write (acquires the write lock up front and avoids deadlock-style upgrade failures from `BEGIN DEFERRED`).
- **Foreign keys are OFF by default** and must be enabled **per connection**: `PRAGMA foreign_keys = ON;` [11]. It cannot be changed inside a transaction.
- Recommended connection setup: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;`.
- Transactions: wrap bulk inserts in one transaction; 10,000 autocommit inserts each fsync and are 100x slower.
- Isolation: SQLite transactions are serializable (single writer); in WAL mode readers see a snapshot as of their transaction start.

## 4. Tooling and package management

- PostgreSQL: `psql` (`\d table`, `\dt`, `\x`, `\timing`, `\i file.sql`, `\copy`), `pg_dump`/`pg_restore`, `pg_upgrade` (PG 18 keeps planner statistics across upgrade [10]), `EXPLAIN (ANALYZE, BUFFERS)`, extensions (`CREATE EXTENSION pg_stat_statements; pgcrypto; postgis; pgvector`). GUIs: pgAdmin, DBeaver. Containers: `postgres:18` image.
- SQLite: `sqlite3` CLI (`.schema`, `.tables`, `.mode box`, `.timer on`, `.import`, `.dump`, `.backup`); 3.53 changed CLI defaults (box output in interactive sessions, ignores trailing semicolons after dot-commands) [3]; 3.54 adds `SQLITE_PS1`/`SQLITE_PS2` prompts and more `.mode` options [2]. `sqldiff`, `sqlite3_rsync`, DB Browser for SQLite.
- Migrations: Flyway, Liquibase, sqitch, dbmate, Alembic (Python), Prisma/Drizzle/Knex (JS), Ecto (Elixir), golang-migrate. Keep migrations forward-only and idempotent where possible.
- Linters/formatters: sqlfluff (dialect-aware), pgFormatter, `squawk` (Postgres migration safety lints).
- Drivers: psycopg 3 / asyncpg (Python), node-postgres `pg` / postgres.js, Npgsql, pgx (Go); SQLite: built-in `sqlite3` (Python), better-sqlite3 / `node:sqlite` (Node 22.5+), `bun:sqlite`, Microsoft.Data.Sqlite, rusqlite.

## 5. Testing

- Test against the **same engine** as production. SQLite is not a faithful stand-in for PostgreSQL (types, locking, functions, `ON CONFLICT` details differ).
- PostgreSQL: Testcontainers or a disposable Docker Postgres; wrap each test in a transaction and roll back; or create a template database and `CREATE DATABASE test_x TEMPLATE app_template`. **pgTAP** for in-database unit tests (`SELECT plan(2); SELECT has_table('players'); SELECT results_eq(...)`).
- SQLite: `:memory:` databases are fast and isolated per connection; use a temp file when testing WAL/concurrency.
- Test migrations: apply all migrations to an empty DB in CI, plus up/down on a copy of production-shaped data.
- Property: assert constraints (try inserting invalid rows and expect the constraint error).
- Query plans: snapshot `EXPLAIN` for critical queries to catch missing-index regressions.

## 6. Idiomatic patterns (code)

### Schema (PostgreSQL 18)

```sql
CREATE TABLE players (
    id           uuid PRIMARY KEY DEFAULT uuidv7(),
    username     text NOT NULL UNIQUE CHECK (length(username) BETWEEN 3 AND 20),
    created_at   timestamptz NOT NULL DEFAULT now(),
    coins        bigint NOT NULL DEFAULT 0 CHECK (coins >= 0)
);

CREATE TABLE scores (
    player_id    uuid NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    level_id     int  NOT NULL,
    best_ms      int  NOT NULL CHECK (best_ms > 0),
    achieved_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, level_id)
);
CREATE INDEX scores_level_best_idx ON scores (level_id, best_ms, achieved_at);
```

### Upsert keeping the best score

```sql
-- PostgreSQL
INSERT INTO scores (player_id, level_id, best_ms)
VALUES ($1, $2, $3)
ON CONFLICT (player_id, level_id)
DO UPDATE SET best_ms = LEAST(scores.best_ms, EXCLUDED.best_ms),
              achieved_at = CASE WHEN EXCLUDED.best_ms < scores.best_ms
                                 THEN now() ELSE scores.achieved_at END
RETURNING best_ms;

-- SQLite (3.24+ upsert; 3.35+ RETURNING)
INSERT INTO scores (player_id, level_id, best_ms) VALUES (?, ?, ?)
ON CONFLICT (player_id, level_id)
DO UPDATE SET best_ms = min(best_ms, excluded.best_ms)
RETURNING best_ms;
```

PostgreSQL 18 `RETURNING` can name `old` and `new` row versions: `UPDATE players SET coins = coins - 50 WHERE id = $1 AND coins >= 50 RETURNING old.coins AS before, new.coins AS after;` [10].

### MERGE (PostgreSQL 15+; RETURNING on MERGE since 17)

```sql
MERGE INTO inventory AS i
USING (VALUES ($1::uuid, $2::text, $3::int)) AS s(player_id, item, qty)
   ON i.player_id = s.player_id AND i.item = s.item
WHEN MATCHED AND i.qty + s.qty <= 0 THEN DELETE
WHEN MATCHED THEN UPDATE SET qty = i.qty + s.qty
WHEN NOT MATCHED AND s.qty > 0 THEN INSERT (player_id, item, qty) VALUES (s.player_id, s.item, s.qty)
RETURNING merge_action(), i.*;
```

### Leaderboard with window functions and keyset pagination

```sql
SELECT player_id, best_ms,
       rank()       OVER (ORDER BY best_ms)            AS rank,
       percent_rank() OVER (ORDER BY best_ms)          AS pct
FROM scores
WHERE level_id = $1
ORDER BY best_ms, player_id
LIMIT 50;

-- next page: keyset instead of OFFSET (OFFSET 100000 scans 100000 rows)
SELECT player_id, best_ms FROM scores
WHERE level_id = $1 AND (best_ms, player_id) > ($2, $3)
ORDER BY best_ms, player_id
LIMIT 50;
```

### Atomic currency transfer (no lost update)

```sql
BEGIN;
UPDATE players SET coins = coins - 100 WHERE id = $1 AND coins >= 100;   -- check affected rows = 1
UPDATE players SET coins = coins + 100 WHERE id = $2;
COMMIT;
```

The conditional `UPDATE` is atomic; never `SELECT coins`, compute in the app, then `UPDATE SET coins = <value>` (lost update under concurrency).

### Job queue (PostgreSQL)

```sql
WITH next AS (
  SELECT id FROM jobs WHERE state = 'queued'
  ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1
)
UPDATE jobs SET state = 'running', started_at = now()
FROM next WHERE jobs.id = next.id
RETURNING jobs.*;
```

### JSON

```sql
-- PostgreSQL
SELECT data->>'class' AS class, (data->'stats'->>'hp')::int AS hp
FROM saves WHERE data @> '{"class":"mage"}';
CREATE INDEX saves_data_gin ON saves USING gin (data jsonb_path_ops);

-- SQLite
SELECT json_extract(data, '$.stats.hp') FROM saves WHERE data ->> '$.class' = 'mage';
```

### Recursive CTE

```sql
WITH RECURSIVE tree(id, parent_id, depth) AS (
  SELECT id, parent_id, 0 FROM quests WHERE parent_id IS NULL
  UNION ALL
  SELECT q.id, q.parent_id, t.depth + 1 FROM quests q JOIN tree t ON q.parent_id = t.id
)
SELECT * FROM tree;
```

### Parameterized queries from code

```python
# psycopg 3
cur.execute("SELECT * FROM players WHERE username = %s", (name,))
# sqlite3
con.execute("SELECT * FROM players WHERE username = ?", (name,))
```

```js
// node-postgres
await pool.query('SELECT * FROM players WHERE username = $1', [name]);
```

## 7. Top pitfalls and error-message fixes

| Error text (exact or typical) | Cause | Fix |
|---|---|---|
| `database is locked` (SQLite, `SQLITE_BUSY`) | Another connection holds the write lock; no busy timeout; long write transaction; reader upgrading to writer | `PRAGMA busy_timeout=5000`, WAL mode, short transactions, `BEGIN IMMEDIATE` for writers, one writer connection/queue |
| Foreign key rows deleted/orphaned without error (SQLite) | `PRAGMA foreign_keys` is OFF by default per connection [11] | Run `PRAGMA foreign_keys = ON;` on every new connection |
| `FOREIGN KEY constraint failed` (SQLite) | Parent row missing, or wrong delete order | Insert parents first, `ON DELETE CASCADE`, or `PRAGMA defer_foreign_keys` within a transaction |
| `cannot store TEXT value in INTEGER column t.x` (SQLite STRICT) | Wrong type into STRICT table | Convert in app; this is the point of STRICT |
| `UNIQUE constraint failed: players.username` (SQLite) / `duplicate key value violates unique constraint "players_username_key"` (PG, 23505) | Duplicate insert | `ON CONFLICT DO NOTHING/UPDATE`, or handle the error |
| `column "x" does not exist` (PG) | Unquoted identifiers fold to lower case; `"PlayerId"` was created quoted; or used `"..."` for a string literal | Use snake_case unquoted identifiers; strings take single quotes |
| `column "x" must appear in the GROUP BY clause or be used in an aggregate function` (PG) | Non-aggregated column in grouped query | Add it to `GROUP BY`, aggregate it, or use `DISTINCT ON` / window functions. (SQLite silently picks an arbitrary row: a hidden bug) |
| `operator does not exist: integer = text` (PG) | Comparing mismatched types (often parameter typed as text) | Cast explicitly `$1::int` or fix the parameter type |
| `invalid input syntax for type integer: ""` (PG) | Empty string where a number is expected | Send NULL or validate |
| `division by zero` (PG) | Integer/numeric divide by 0 | `NULLIF(denominator, 0)` |
| `could not serialize access due to concurrent update` / `... read/write dependencies among transactions` (PG, 40001) | REPEATABLE READ / SERIALIZABLE conflict | Retry the whole transaction with backoff |
| `deadlock detected` (PG, 40P01) | Two transactions lock rows in opposite order | Consistent lock order, shorter transactions, retry |
| `canceling statement due to lock timeout` (PG) | Migration DDL waited for a lock | Retry off-peak; `CREATE INDEX CONCURRENTLY`; split migrations |
| `current transaction is aborted, commands ignored until end of transaction block` (PG, 25P02) | An earlier statement in the transaction failed | `ROLLBACK` (or use `SAVEPOINT`), then fix the first error |
| `remaining connection slots are reserved` / `too many clients already` (PG) | Connection leak or no pool | Pool connections, close them, PgBouncer |
| `NOT IN` returns zero rows | Subquery contains a NULL | Use `NOT EXISTS` |
| `WHERE x = NULL` never matches | NULL comparison is unknown | `WHERE x IS NULL` |
| Integer division gives 0 (`1/3`) | Both operands integer | `1.0/3` or cast to `numeric` |

## 8. Performance

- **Index what you filter, join and sort by**; composite index column order matters: equality columns first, then range/sort columns. `(level_id, best_ms)` serves `WHERE level_id = ? ORDER BY best_ms`.
- PG 18 adds **B-tree skip scan**, so a multicolumn index can sometimes be used when the leading column is not constrained [5]; do not rely on it instead of correct index design.
- Read plans: PostgreSQL `EXPLAIN (ANALYZE, BUFFERS) <query>` (look for `Seq Scan` on big tables, estimate vs actual row mismatch, `Sort Method: external merge`); SQLite `EXPLAIN QUERY PLAN <query>` (look for `SCAN table` vs `SEARCH table USING INDEX`).
- Functions on indexed columns disable the index (`WHERE lower(username) = ?`) unless you create an expression index `CREATE INDEX ON players (lower(username))`.
- `LIKE '%term'` cannot use a B-tree; use `pg_trgm` GIN indexes or SQLite FTS5.
- Avoid N+1 queries: join or batch with `WHERE id = ANY($1)` (PG) / `IN (...)` / `carray`.
- Keyset pagination instead of large `OFFSET`.
- Bulk load: PostgreSQL `COPY`; SQLite one transaction with a prepared statement reused.
- Keep statistics fresh: `ANALYZE` (PG autovacuum does it; SQLite `PRAGMA optimize` before closing long-lived connections).
- SQLite `PRAGMA synchronous=NORMAL` with WAL is durable against application crashes, and may lose the last transactions on power loss (an accepted trade-off for game saves; use FULL where needed).
- Partial indexes: `CREATE INDEX ON jobs (id) WHERE state = 'queued';`.
- Covering indexes: PG `INCLUDE (cols)`; SQLite automatically covers if all columns are in the index.

## 9. Security

- **SQL injection**: never build SQL with string concatenation, f-strings or template literals containing user input. Use **bound parameters** (`$1`, `?`, `%s` as a driver placeholder, `:name`). Parameters cannot replace identifiers (table/column names) or keywords: for dynamic `ORDER BY` choose from an allow-list in code; in PL/pgSQL use `format('%I', ident)` and `quote_ident`, and `EXECUTE ... USING` for values [12].
- `LIKE` patterns from users: escape `%` and `_` or use `ESCAPE`.
- Least privilege (PG): application role without superuser, without DDL rights; `GRANT SELECT, INSERT, UPDATE` on needed tables; **Row-Level Security** (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY; CREATE POLICY ...`) for multi-tenant data. `SECURITY DEFINER` functions must set `search_path`.
- Authentication (PG): use `scram-sha-256`; **MD5 password authentication is deprecated in PG 18** and emits warnings [10]. PG 18 also adds OAuth 2.0 authentication support [5]. Require TLS (`sslmode=verify-full` from clients).
- SQLite: the file is the database: protect file permissions; it has no users. Do not open untrusted database files with defensive settings off (`SQLITE_DBCONFIG_DEFENSIVE`, `PRAGMA trusted_schema=OFF`) because a crafted schema can run triggers/views. Encryption requires SQLCipher or the SEE extension.
- Secrets in databases: hash passwords with Argon2id/bcrypt in the application; never store plaintext.
- Backups are part of security: `pg_dump`/PITR for PG; SQLite `VACUUM INTO 'backup.db'` or the online backup API (never copy a live WAL database file without its `-wal` file).

## 10. Game-dev usage

- **SQLite** is the standard embedded store for single-player saves, settings, content databases, mod data, and editor tools (Godot, Unity, Unreal plugins; Android/iOS native). WAL + one writer thread + short transactions. Store blobs (thumbnails) sparingly; keep large assets on disk and paths in the DB.
- **PostgreSQL** backs online services: accounts, inventories, economies, matchmaking history, leaderboards, telemetry (with partitioning by time, or TimescaleDB).
- Leaderboards: B-tree `(level_id, score)` index with window functions for rank on modest sizes; for very large, high-write global boards, a Redis sorted set in front with periodic persistence to PostgreSQL is common.
- Economy integrity: currency changes as conditional `UPDATE ... WHERE coins >= cost` inside transactions, idempotency keys for purchase receipts (`UNIQUE (receipt_id)`), and an append-only ledger table for audits.
- Save-data schema versioning: a `schema_version` table or `PRAGMA user_version` (SQLite) checked at startup; migrate forward in a transaction.
- Roblox does **not** expose SQL; its persistence is DataStoreService/MemoryStoreService. An external SQL backend is reachable only via `HttpService` to your own web API (never put database credentials in a Roblox place).

## 11. Cheat sheet vs Luau

| Concept | Luau | SQL |
|---|---|---|
| Collection | table/array | table (unordered set of rows) |
| Filter | `for _, r in rows do if r.hp > 0 then ... end end` | `SELECT * FROM t WHERE hp > 0` |
| Map | build a new table | `SELECT hp * 2 AS double_hp FROM t` |
| Count | `#t` | `SELECT count(*) FROM t` |
| Group | manual dictionary of lists | `GROUP BY` + aggregates |
| Sort | `table.sort(t, fn)` | `ORDER BY col` (only way to get order) |
| Lookup by key | `t[key]` | `WHERE pk = $1` (with an index) |
| nil | `nil` | `NULL` (three-valued logic; `IS NULL`) |
| Equality | `a == b` | `a = b` (`IS NOT DISTINCT FROM` for NULL-safe) |
| String concat | `a .. b` | `a \|\| b` |
| String length | `#s` | `length(s)` |
| Default | `x or d` | `COALESCE(x, d)` |
| Conditional | `if c then a else b end` | `CASE WHEN c THEN a ELSE b END` |
| Join tables | nested loops over two tables | `JOIN ... ON ...` |
| Atomic update | single-threaded script | transaction + conditional `UPDATE` |
| Error handling | `pcall` | transaction `ROLLBACK`, SQLSTATE codes |
| Persistence (Roblox) | DataStore `UpdateAsync` | `INSERT ... ON CONFLICT DO UPDATE` |
| Indexes | none (tables are hash maps) | `CREATE INDEX` |
| Comments | `-- x` | `-- x` (same) |
| Indexing base | 1 | `row_number()` starts at 1; arrays in PG are 1-based |

## 12. Recent changes and version notes

- **PostgreSQL 18 (2025-09-25)** [4][5][10]: asynchronous I/O subsystem (`io_method`); `uuidv7()`; virtual generated columns (default kind); `OLD`/`NEW` in `RETURNING` for INSERT/UPDATE/DELETE/MERGE; temporal constraints `WITHOUT OVERLAPS` on PRIMARY KEY/UNIQUE and `PERIOD` on foreign keys; B-tree skip scan; `pg_upgrade` keeps planner statistics; `NOT NULL ... NOT VALID`; OAuth authentication; MD5 password auth deprecated; `initdb` enables data checksums by default.
- **PostgreSQL 17 (2024-09)**: `MERGE ... RETURNING` and `merge_action()`, `JSON_TABLE` and SQL/JSON constructors, incremental backup (`pg_basebackup --incremental`), improved VACUUM memory use, `COPY ... ON_ERROR ignore`.
- **PostgreSQL 19**: beta only as of 2026-10-13 [1].
- **SQLite 3.54.0 (2026-10-09)** [2]: CLI prompt customization (`SQLITE_PS1`/`SQLITE_PS2`), more `.mode` options, `diskused()` extension, query-planner improvements, Windows XP support removed.
- **SQLite 3.53.0 (2026-04-09)** [3]: fixes a WAL-reset database corruption bug (upgrade if on an older WAL deployment); `ALTER TABLE` can add/remove `NOT NULL` and `CHECK` constraints; `REINDEX EXPRESSIONS` and self-healing of stale expression indexes; `json_array_insert()`/`jsonb_array_insert()`; floating-point to text now rounds to 17 significant digits (was 15; behaviour change); CLI uses the Query Result Formatter with box output interactively; `opfs-wl` VFS for WASM.
- SQLite 3.45 (2024): JSONB. 3.37 (2021): STRICT tables. 3.35: `RETURNING`, `DROP COLUMN`. 3.24: UPSERT.

## Sources

1. https://www.postgresql.org/support/versioning/
2. https://sqlite.org/changes.html
3. https://sqlite.org/releaselog/3_53_0.html
4. https://www.postgresql.org/about/news/postgresql-18-released-3142/
5. https://www.postgresql.org/docs/18/release-18.html
6. https://sqlite.org/datatype3.html
7. https://sqlite.org/stricttables.html
8. https://www.postgresql.org/docs/current/transaction-iso.html
9. https://sqlite.org/wal.html and https://sqlite.org/lockingv3.html
10. https://www.bytebase.com/blog/what-is-new-in-postgres-18/ (secondary summary of the PG 18 release notes)
11. https://sqlite.org/foreignkeys.html
12. https://www.postgresql.org/docs/current/plpgsql-statements.html#PLPGSQL-STATEMENTS-EXECUTING-DYN
13. https://www.postgresql.org/docs/current/using-explain.html
14. https://sqlite.org/eqp.html
15. https://sqlite.org/lang_upsert.html
16. https://www.postgresql.org/docs/current/sql-merge.html
17. https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
