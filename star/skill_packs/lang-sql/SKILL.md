---
name: lang-sql
description: SQL for PostgreSQL 17/18 and SQLite 3.5x - schema design, upserts, transactions and locking, indexes and EXPLAIN, injection-safe parameters, and game backends (saves, leaderboards, economies). Use when writing, reviewing or debugging SQL or database errors.
---
# SQL: PostgreSQL and SQLite
- Always pass user values as bound parameters ($1, ?, :name, or the driver's %s placeholder). Never concatenate or interpolate input into SQL text. Parameters cannot be identifiers: pick table/column names and ORDER BY directions from an allow-list (PL/pgSQL: format('%I') and EXECUTE ... USING).
- NULL is unknown: use IS NULL / IS DISTINCT FROM; `x = NULL` never matches; NOT IN with a NULL in the subquery returns nothing, so prefer NOT EXISTS. COALESCE for defaults.
- No ORDER BY means no order. Paginate with keyset (WHERE (score, id) > ($1, $2) ORDER BY score, id LIMIT n), not large OFFSET.
- Name the engine and version before answering; dialects differ.
## PostgreSQL
- Types: bigint identity keys (GENERATED ALWAYS AS IDENTITY), timestamptz not timestamp, numeric for money, text plus CHECK instead of varchar(n), jsonb not json. PG 18 has uuidv7() for time-ordered keys; generated columns default to VIRTUAL in 18 (say STORED to persist).
- Default isolation is READ COMMITTED. REPEATABLE READ and SERIALIZABLE can fail with SQLSTATE 40001; the application must retry the whole transaction.
- Prevent lost updates with one conditional statement: UPDATE players SET coins = coins - $2 WHERE id = $1 AND coins >= $2, then check the row count. Never read, compute in the app, and write back an absolute value.
- Upsert: INSERT ... ON CONFLICT (cols) DO UPDATE SET x = EXCLUDED.x RETURNING ...; MERGE exists (15+, RETURNING since 17, merge_action()). PG 18 RETURNING can read old.* and new.*.
- Queues: SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1. Lock rows in a consistent order to avoid `deadlock detected`.
- `current transaction is aborted, commands ignored until end of transaction block` means an earlier statement failed: ROLLBACK (or use a SAVEPOINT) and fix the first error.
- Unquoted identifiers fold to lower case; `column "x" does not exist` often means a quoted mixed-case name. Single quotes are strings, double quotes are identifiers.
- Integer division truncates (5/2 = 2); cast to numeric. Use NULLIF(d, 0) to avoid division by zero.
- Migrations: SET lock_timeout, CREATE INDEX CONCURRENTLY, ADD CONSTRAINT ... NOT VALID then VALIDATE CONSTRAINT.
- Use a connection pool; each connection is a server process.
- Read plans with EXPLAIN (ANALYZE, BUFFERS). Index filter/join/sort columns, equality columns first. Expression indexes for lower(col); pg_trgm for '%term' searches; GIN on jsonb.
- Use scram-sha-256 (MD5 auth is deprecated in 18), TLS, a least-privilege app role, and row-level security for tenant data.
## SQLite
- Typing is by affinity: an INTEGER column accepts 'abc'. Create new tables with STRICT. INTEGER PRIMARY KEY is the rowid; AUTOINCREMENT is rarely needed.
- Foreign keys are OFF by default and are set per connection: run PRAGMA foreign_keys = ON on every connection.
- Connection setup: PRAGMA journal_mode = WAL; synchronous = NORMAL; foreign_keys = ON; busy_timeout = 5000.
- One writer at a time even in WAL. `database is locked` (SQLITE_BUSY): set busy_timeout, keep write transactions short, start writing transactions with BEGIN IMMEDIATE, funnel writes through one connection or thread.
- Batch inserts inside one transaction with one prepared statement; autocommit per row is very slow.
- Read plans with EXPLAIN QUERY PLAN (SCAN = full table, SEARCH ... USING INDEX = good).
- Upsert: INSERT ... ON CONFLICT DO UPDATE (3.24+), RETURNING (3.35+). JSON via json_extract and ->>, binary JSONB since 3.45. 3.53 can ALTER TABLE to add or drop NOT NULL and CHECK, and fixed a WAL-reset corruption bug: upgrade older WAL deployments.
- Track schema versions with PRAGMA user_version; back up with VACUUM INTO or the backup API, never by copying a live file without its -wal file.
- Do not substitute SQLite for PostgreSQL in tests of PostgreSQL behavior.
## Game backends
- Saves and settings: SQLite. Accounts, inventories, economies and leaderboards: PostgreSQL, with a ledger table and UNIQUE idempotency keys for purchases.
- Roblox has no SQL: use DataStores, or call your own web API through HttpService; never put database credentials in a place.
