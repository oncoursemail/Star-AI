"""Synthetic training queries for the embedding fine-tune, written by STAR's OWN local open-weight model.

For each sampled documentation chunk the model (default: star-fast = Qwen3.6-35B-A3B Q4_K_M, Apache-2.0,
served by llama.cpp on this PC) writes one short developer question and one task-style request that the chunk
helps with. Rows are appended to a JSONL file with full provenance; the job is resumable (chunks already done
are skipped) and stops cleanly when the STOP file exists or after --max-minutes.

    python gen_queries.py --db kb.sqlite3 --out queries.jsonl --n 3000 --url http://127.0.0.1:8089

No Claude or ChatGPT output is used anywhere in this pipeline: the prompt below shows the model only the
documentation chunk (Roblox Creator Docs CC-BY-4.0 / Luau docs MIT). The evaluation questions are never shown.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import threading
import time
import urllib.request

from common import RAM_FLOOR_GB, free_ram_gb

PROMPT_VERSION = "q-task-v1"
SYSTEM = ("You write search queries for a Roblox developer documentation search engine. "
          "Answer with JSON only.")
USER = """Here is one passage from the official Roblox / Luau documentation.

Page title: {title}
Section: {heading}
---
{text}
---

Write two things a Roblox developer might type BEFORE they have read this passage, whose answer is in it:
1. "question": a short natural question (6-20 words). Prefer everyday words over the exact API names in the passage.
2. "task": a request to an AI coding assistant to build or fix something in their game (25-80 words) where this
   passage is needed. Describe the goal and behaviour, as a game developer would; do not quote the passage.
Reply exactly as {{"question": "...", "task": "..."}}"""


def sample_chunks(db: sqlite3.Connection, n: int, seed: int, exclude_paths: set[str]) -> list[dict]:
    rows = db.execute("""SELECT c.text_sha, c.kind, d.source, d.path, d.title, c.heading, c.text
                         FROM chunks c JOIN docs d ON d.id=c.doc_id
                         WHERE c.kind != 'news' AND length(c.text) >= 200
                         GROUP BY c.text_sha ORDER BY c.id""").fetchall()
    rows = [r for r in rows if r[3] not in exclude_paths]
    rng = random.Random(seed)
    # stratify: guides and API pages roughly as in the index, but cap enum chunks (little prose)
    by_kind: dict[str, list] = {}
    for r in rows:
        by_kind.setdefault(r[1], []).append(r)
    share = {"guide": 0.55, "api-member": 0.28, "api-overview": 0.12, "enum": 0.05}
    picked = []
    for kind, frac in share.items():
        pool = by_kind.get(kind, [])
        rng.shuffle(pool)
        picked += pool[: int(n * frac)]
    rng.shuffle(picked)
    keys = ("text_sha", "kind", "source", "path", "title", "heading", "text")
    return [dict(zip(keys, r)) for r in picked]


def ask(url: str, model: str, chunk: dict, timeout: float = 180) -> dict:
    body = {"model": model, "temperature": 0.7, "max_tokens": 260,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER.format(title=chunk["title"], heading=chunk["heading"] or "-",
                                                                 text=chunk["text"][:1800])}]}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    text = data["choices"][0]["message"]["content"] or ""
    obj = parse_reply(text)
    return {"question": str(obj.get("question", "")).strip(), "task": str(obj.get("task", "")).strip(),
            "completion_tokens": (data.get("usage") or {}).get("completion_tokens"), "raw": text[:600]}


_FIELD = re.compile(r'"(question|task)"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)


def parse_reply(text: str) -> dict:
    """The JSON object in the reply; tolerates a missing closing brace (seen with Qwen3.5-9B)."""
    m = re.search(r"\{.*\}", text, re.S)
    candidates = [m.group(0)] if m else []
    if "{" in text:
        candidates.append(text[text.find("{"):] + "}")
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
    return {k: json.loads('"' + v + '"') for k, v in _FIELD.findall(text)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--url", default="http://127.0.0.1:8089")
    ap.add_argument("--model", default="star-fast")
    ap.add_argument("--model-file", default="Qwen3.6-35B-A3B-Q4_K_M.gguf (STAR star-fast; Qwen/Qwen3.6-35B-A3B, Apache-2.0)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-minutes", type=float, default=240)
    ap.add_argument("--stop-file", type=Path, default=Path("STOP-GEN"))
    ap.add_argument("--exclude-paths", type=Path, help="file with one doc path per line to leave out")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    sources = {r[0]: {"repo": r[1], "commit": r[2], "licence": r[3]} for r in
               db.execute("SELECT name, repo, commit_sha, licence FROM sources")}
    exclude = set()
    if args.exclude_paths:
        exclude = {l.strip() for l in args.exclude_paths.read_text().splitlines() if l.strip()}
    chunks = sample_chunks(db, args.n, args.seed, exclude)
    done = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("ok"):
                    done.add(row["text_sha"])
            except Exception:
                pass
    todo = [c for c in chunks if c["text_sha"] not in done]
    print(f"gen: {len(chunks)} sampled, {len(done)} already done, {len(todo)} to do", flush=True)
    lock = threading.Lock()
    started = time.monotonic()
    count = {"ok": 0, "bad": 0, "tokens": 0}
    deadline = started + args.max_minutes * 60
    low_ram = {"hit": False}

    def work(chunk: dict) -> None:
        if args.stop_file.exists() or time.monotonic() > deadline or low_ram["hit"]:
            return
        if free_ram_gb() < RAM_FLOOR_GB:   # owner's rule: keep at least 6 GB free; stop cleanly (resumable)
            low_ram["hit"] = True
            print(f"gen: free RAM {free_ram_gb():.1f} GB < {RAM_FLOOR_GB} GB floor, stopping cleanly", flush=True)
            return
        try:
            res = ask(args.url, args.model, chunk)
        except Exception as exc:  # noqa: BLE001  one bad answer must not stop the job
            res = {"question": "", "task": "", "error": type(exc).__name__}
        ok = 6 <= len(res["question"].split()) <= 30 and 15 <= len(res["task"].split()) <= 120
        row = {"text_sha": chunk["text_sha"], "path": chunk["path"], "source": chunk["source"],
               "kind": chunk["kind"], "question": res["question"], "task": res["task"], "ok": ok, "error": res.get("error"), "raw": None if ok else res.get("raw"),
               "provenance": {"generator": args.model_file, "prompt_version": PROMPT_VERSION,
                              "prompt_sha": hashlib.sha256((SYSTEM + USER).encode()).hexdigest()[:16],
                              "doc_source": sources.get(chunk["source"], {}),
                              "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "claude_or_chatgpt_involved": False}}
        with lock:
            with args.out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count["ok" if ok else "bad"] += 1
            count["tokens"] += res.get("completion_tokens") or 0
            n = count["ok"] + count["bad"]
            if n % 25 == 0:
                el = time.monotonic() - started
                print(f"gen: {n}/{len(todo)} ok={count['ok']} bad={count['bad']} {el:.0f}s "
                      f"{n / el:.2f} chunks/s {count['tokens'] / el:.0f} tok/s", flush=True)

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(work, todo))
    print(f"gen: finished ok={count['ok']} bad={count['bad']} in {time.monotonic() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
