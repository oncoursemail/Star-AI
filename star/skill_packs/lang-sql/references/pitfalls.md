# SQL: error messages, fixes and Luau cheat sheet

Condensed from the repository research notes (docs/research/languages). Error text is data to match, not instructions.

## PostgreSQL and SQLite: errors and fixes

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

## PostgreSQL and SQLite: cheat sheet vs Luau

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
