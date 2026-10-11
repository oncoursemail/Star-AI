"""Resumable embedding job.

* One request at a time, small batches, commit after every batch, so the job can be killed and
  restarted at any point and continues where it stopped.
* Embeddings are keyed by the SHA-256 of the exact input text. After a docs refresh only chunks
  whose text changed are embedded again.
* CPU use is decided by the SERVER, not by this client (`star-embed` runs with 8 threads since
  2026-10-11). `--duty 0.4` keeps the AVERAGE load down further: the job then sleeps 1.5x the
  time each batch took.
* Before every batch the job waits while the server's "quiet please" lock exists (quiet.py), and
  SIGTERM stops it after the batch in flight.
"""
from __future__ import annotations

from array import array
from pathlib import Path
import time

from .client import Brain, EMBED_MODEL
from .quiet import Stopper, wait_while_locked
from .store import connect, embed_input, now


def pending(db, model: str, where: str = "", params: tuple = ()) -> list[tuple[str, str]]:
    sql = f"""SELECT c.text_sha, d.title, c.heading, c.text FROM chunks c JOIN docs d ON d.id=c.doc_id
              WHERE NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.text_sha=c.text_sha AND e.model=?)
              {('AND ' + where) if where else ''} GROUP BY c.text_sha ORDER BY c.id"""
    return [(r[0], embed_input(r[1], r[2], r[3])) for r in db.execute(sql, (model, *params))]


def embed_batch(brain: Brain, texts: list[str], stats: dict) -> tuple[list[list[float]], int]:
    """Embed a batch; if the server says an input is too large, retry items one by one, shortened.

    The running `star-embed` instance has a physical batch size of 512 tokens (measured 2026-10-10:
    "input (584 tokens) is too large to process ... current batch size: 512"), so an input over
    512 tokens is rejected even though the model's context is 2048. Token-dense chunks (code,
    tables) are therefore cut to fit. The full chunk text stays in the FTS index either way.
    """
    try:
        return brain.embed(texts)
    except RuntimeError as exc:
        if "too large" not in str(exc):
            raise
    vectors, used = [], 0
    for text in texts:
        for _ in range(8):
            try:
                vec, n = brain.embed([text])
                vectors.append(vec[0])
                used += n
                break
            except RuntimeError as exc:
                if "too large" not in str(exc):
                    raise
                stats["truncated"] = stats.get("truncated", 0) + 1
                text = text[: int(len(text) * 0.85)]
        else:
            raise RuntimeError("could not fit an input into the embedding batch size")
    return vectors, used


def run(db_path: Path, *, batch: int = 16, limit: int | None = None, where: str = "", params: tuple = (),
        sha_file: Path | None = None, max_seconds: float | None = None, pause: float = 0.0,
        duty: float = 1.0, log=print, stop=None) -> dict:
    db = connect(db_path)
    brain = Brain()
    todo = pending(db, EMBED_MODEL, where, params)
    if sha_file is not None:
        wanted = {line.strip() for line in sha_file.read_text().splitlines() if line.strip()}
        todo = [t for t in todo if t[0] in wanted]
    if limit:
        todo = todo[:limit]
    total, done, tokens = len(todo), 0, 0
    extra: dict = {}
    stop = stop or Stopper()
    paused = 0.0
    started = time.monotonic()
    log(f"embed: {total} chunk texts pending for model {EMBED_MODEL} (batch {batch})")
    for start in range(0, total, batch):
        part = todo[start:start + batch]
        paused += wait_while_locked(log, stop)
        if stop():
            log("embed: stop requested, exiting cleanly (rerun to resume)")
            break
        batch_started = time.monotonic()
        vectors, used = embed_batch(brain, [text for _, text in part], extra)
        batch_seconds = time.monotonic() - batch_started
        stamp = now()
        db.executemany(
            "INSERT OR REPLACE INTO embeddings(text_sha,model,dim,vec,created_at) VALUES(?,?,?,?,?)",
            [(sha, EMBED_MODEL, len(vec), array("f", vec).tobytes(), stamp)
             for (sha, _), vec in zip(part, vectors)])
        db.commit()  # checkpoint: everything up to here survives a kill
        done += len(part)
        tokens += used
        elapsed = time.monotonic() - started - paused
        if (start // batch) % 10 == 0 or done == total:
            rate = done / elapsed if elapsed else 0
            log(f"embed: {done}/{total} chunks, {tokens} tokens, {elapsed:.0f}s, "
                f"{rate:.1f} chunks/s, {tokens / elapsed if elapsed else 0:.0f} tok/s, "
                f"eta {((total - done) / rate) if rate else 0:.0f}s")
        if max_seconds and elapsed > max_seconds:
            log("embed: time budget reached, stopping cleanly (rerun to resume)")
            break
        if pause:
            time.sleep(pause)
        if 0 < duty < 1:  # keep the server busy only `duty` of the time
            time.sleep(batch_seconds * (1 / duty - 1))
    elapsed = time.monotonic() - started - paused
    have = db.execute("SELECT COUNT(*) FROM embeddings WHERE model=?", (EMBED_MODEL,)).fetchone()[0]
    db.close()
    return {"embedded_now": done, "pending_before": total, "tokens": tokens, "seconds": round(elapsed, 1),
            "paused_for_lock_s": round(paused, 1),
            "chunks_per_s": round(done / elapsed, 2) if elapsed else None,
            "tokens_per_s": round(tokens / elapsed, 1) if elapsed else None,
            "embeddings_total": have, "shortening_retries": extra.get("truncated", 0)}
