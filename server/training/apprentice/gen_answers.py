"""Answer measuring-slice tasks with one model behind an OpenAI-compatible endpoint (llama-server), single shot.

    python gen_answers.py --tasks measure.json --url http://127.0.0.1:8111 --model apprentice --out answers.jsonl

Same system prompt as training (build_dataset.SYSTEM), greedy, thinking off, so the three arms (apprentice, base
small model, star-fast) differ only in the model. Speed comes from llama-server's own timings (generation tok/s,
prompt tok/s). Resumable: ids already in --out are skipped. A key is sent only with --key-file (STAR server).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.request

from build_dataset import SYSTEM


def ask(url: str, model: str, prompt: str, max_tokens: int, timeout: float, key: str = "") -> dict:
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens, "cache_prompt": False,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + key} if key else {})})
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    timings = data.get("timings") or {}
    usage = data.get("usage") or {}
    return {"answer": data["choices"][0]["message"].get("content") or "",
            "finish": data["choices"][0].get("finish_reason"), "seconds": round(time.monotonic() - started, 2),
            "gen_tokens": usage.get("completion_tokens"), "prompt_tokens": usage.get("prompt_tokens"),
            "gen_tps": round(timings.get("predicted_per_second") or 0, 2),
            "prompt_tps": round(timings.get("prompt_per_second") or 0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--key-file", type=Path, help="STAR server key file (read, never printed); local servers need none")
    args = ap.parse_args()
    key = args.key_file.read_text(encoding="utf-8").strip() if args.key_file else ""
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    if args.limit:
        tasks = tasks[:args.limit]
    done = set()
    if args.out.is_file():
        done = {json.loads(l)["id"] for l in args.out.read_text(encoding="utf-8").splitlines() if l.strip()}
    with open(args.out, "a", encoding="utf-8", newline="\n") as handle:
        for i, task in enumerate(tasks, 1):
            if task["id"] in done:
                continue
            try:
                row = ask(args.url, args.model, task["prompt"], args.max_tokens, args.timeout, key)
            except OSError as exc:
                row = {"answer": "", "error": type(exc).__name__}
            row = {"id": task["id"], "arm": args.model, **row}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{i}/{len(tasks)} {task['id']} {row.get('gen_tokens')} tok {row.get('gen_tps')} tok/s", flush=True)


if __name__ == "__main__":
    main()
