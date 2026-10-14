It is not safe: both values are pasted into the SQL text, so this is **SQL injection**. `name` can close the string (`' OR 1=1 --`), and `sort` can inject anything after `ORDER BY`.

Fix it in two different ways because the two inputs are different kinds of SQL:

- `name` is a **value**: send it as a bound parameter with a `%s` placeholder, and build the `%...%` pattern in Python. Escape `%` and `_` in the user's text if they should be literal.
- `sort` is an **identifier** (a column name). Placeholders only work for values, never for identifiers, so map the request to a fixed allow-list of known columns (or compose it with `psycopg.sql.Identifier` after checking it against that list).

```python
from psycopg import sql

SORTS = {"score": "score", "wins": "wins", "name": "username"}
column = SORTS.get(request.args.get("sort", "score"), "score")
literal = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
query = sql.SQL("SELECT username, score, wins FROM leaderboard "
                "WHERE username LIKE %s ORDER BY {} DESC LIMIT 50").format(sql.Identifier(column))
cur.execute(query, ("%" + literal + "%",))
```

Also connect with a database role that can only read this table.
