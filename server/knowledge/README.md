# STAR Knowledge service (server side)

The documentation index STAR's Roblox tools use: search over the official Roblox Creator Docs and the Luau site,
exact engine-API lookup, and a Luau compile + type check. It runs on the STAR server next to the model server
(STAR Brain) and is reached by the desktop app through `star/knowledge_client.py`.

This folder is the source of truth. Nothing in it names a server: the address comes from the environment.

## Layout

| Path | What |
|---|---|
| `starkb/` | the package: `chunking`, `store` (SQLite + FTS5), `embed`, `search`, `serve` (HTTP), `luaucheck`, `study` (doc2query), `refresh` (nightly), `coverage`, `evaluate`, `quiet` (server lock + clean stop) |
| `corpora.json` | the indexed repositories with licence and attribution |
| `fetch.sh` | first clone of the repositories (inside the container) |
| `deploy.sh` | copy this folder to the server; `--install` also installs the units |
| `install-service.sh` | runs as root in the container: Luau tools, systemd units |
| `star-knowledge.service` | the HTTP service on port 8091 |
| `star-knowledge-study.service` | the study job (started by hand, resumable) |
| `star-knowledge-refresh.service` / `.timer` | the nightly refresh (10:00 UTC) |
| `eval/questions.jsonl` | 30 development questions (tune on these) |
| `eval/heldout.jsonl` | 40 held-out questions (never tune on these) |
| `eval/golden-task-queries.jsonl` | the 25 golden-task prompts as raw queries |
| `tests/` | unit tests (PC, no server needed) and `live_hardening.py` (against a running service) |

On the server everything lives under `/opt/star/knowledge`: `app/` (this folder), `venv/`, `sources/` (git checkouts),
`data/kb.sqlite3` (the index), `data/refresh-report.log`, `tools/` (Luau binaries).

## Deploy

```bash
# once: server/knowledge/.env (ignored by git)
#   STAR_SERVER_SSH=user@192.168.1.20      the LXD host, key authentication
#   STAR_LXC_CONTAINER=<container name>
bash server/knowledge/deploy.sh             # copy the code
bash server/knowledge/deploy.sh --install   # copy, install units, restart star-knowledge (a few seconds of downtime)
bash server/knowledge/deploy.sh --run x.sh  # run a script as root inside the container
```

## Commands (in the container, as user `star`, in `/opt/star/knowledge/app`, `PY=/opt/star/knowledge/venv/bin/python`)

```bash
$PY -m starkb stats                    # documents, chunks, vectors, generated questions
$PY -m starkb build                    # re-chunk the checkouts; one transaction, the old index stays if it fails
$PY -m starkb embed --batch 8          # embed chunks that have no vector (resumable)
$PY -m starkb eval --questions eval/heldout.jsonl --modes bm25,vector,hybrid,vector+q
$PY -m starkb study-plan --size 1500   # first study subset: most-mentioned API, most-linked guides
$PY -m starkb study --order-file ../data/study-subset.txt --only-listed
$PY -m starkb study-status
$PY -m starkb refresh                  # what the nightly timer runs
$PY -m starkb api-coverage             # every reference symbol through api-lookup
```

Units: `systemctl start --no-block star-knowledge-study`, `systemctl stop star-knowledge-study` (finishes the chunk in
flight), `systemctl start star-knowledge-refresh`, `systemctl list-timers star-knowledge-refresh.timer`.

## Rules the background jobs keep

- One request to the model server at a time.
- Before every request or batch they wait while `/opt/star/lock` exists (someone is measuring timings). A lock older
  than 20 minutes is treated as left behind and ignored; it is never removed by a job.
- A commit after every chunk or batch; SIGTERM finishes the request in flight and exits 0.
- The index is rebuilt in one transaction. A failed fetch, a parse error or a result with under 80 % of the previous
  chunks leaves the working index untouched.

## HTTP service limits

48 connections at once, 16 per client address; 5 s for the request line and headers, 10 s more for the body
(absolute deadlines); bodies up to 16 kB (96 kB for `/luau/check`). Repeated searches come from a 512-entry cache
that is dropped when the index is rebuilt or new vectors are loaded.

## Tests

```bash
python -m pytest -q server/knowledge/tests                                    # needs numpy; no server
python server/knowledge/tests/live_hardening.py http://192.168.1.20:8091      # against a running service
```
