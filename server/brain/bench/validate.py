#!/usr/bin/env python3
"""STAR Brain speed check: first-token time and tokens/second through the OpenAI-compatible API.

Run it BEFORE and AFTER a configuration change and compare:

    python validate.py --tag before            # writes validate-before.json next to this file
    ... apply the change ...
    python validate.py --tag after
    python validate.py --compare validate-before.json validate-after.json

Standard library only (works with any Python 3.8+ on the PC or inside the container).
The API key is read from a file (or the STAR_API_KEY environment variable) and is never printed or written.

What is measured, per chat model:
  short        short question, nothing cached: first-token time, generation tokens/s (median of --reps)
  long_cold    about 1,200-token prompt that the server has never seen: prompt-processing tokens/s, first-token time
  next_turn    the same conversation one turn later: tokens reused from the cache (cache_n) and first-token time
  under_embed  generation tokens/s while an embedding job runs at the same time (skipped with --no-contention)
and for the retrieval models: embedding throughput (tokens/s) and rerank latency.

Server-side numbers (prompt_n, cache_n, tokens/s) come from the `timings` object llama-server adds to the last
stream chunk; first-token time and total time are measured on the client.
"""
import argparse
import http.client
import json
import os
import statistics
import sys
import threading
import time
import urllib.parse

DEFAULT_BASE = "http://127.0.0.1:8080"  # set STAR_BRAIN_URL or --base for a remote brain
KEY_FILES = [os.path.join(os.path.expanduser("~"), ".star", "server_api_key"), "/opt/star/secrets/api_keys"]

TOPICS = ["memory", "documents", "voice", "Roblox Studio", "Luau scripts", "tool calls", "retrieval", "privacy", "files", "the calendar",
          "reminders", "code review", "web search", "images", "the knowledge base", "long tasks"]


def system_prompt(nonce="", rules=28):
    head = ("(%s) " % nonce) if nonce else ""
    return head + "You are STAR, a local-first assistant. Follow these operating rules.\n" + "\n".join(
        "Rule %d: When the request is about %s, answer from verified context first, say plainly what you could not check, keep the reply "
        "short, and never invent a source, a file path, an API name or a number." % (i + 1, TOPICS[i % len(TOPICS)]) for i in range(rules))


def load_key(path):
    env = os.environ.get("STAR_API_KEY")
    if env:
        return env.strip()
    for p in ([path] if path else KEY_FILES):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read().strip().splitlines()[0].strip()
        except OSError:
            continue
    return None


class Client:
    def __init__(self, base, key, timeout):
        self.u = urllib.parse.urlparse(base)
        self.key = key
        self.timeout = timeout

    def _conn(self):
        cls = http.client.HTTPSConnection if self.u.scheme == "https" else http.client.HTTPConnection
        return cls(self.u.hostname, self.u.port or (443 if self.u.scheme == "https" else 80), timeout=self.timeout)

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = "Bearer " + self.key
        return h

    def get(self, path):
        c = self._conn()
        c.request("GET", path, headers=self._headers())
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, body

    def post_json(self, path, body):
        c = self._conn()
        t0 = time.time()
        c.request("POST", path, json.dumps(body), self._headers())
        r = c.getresponse()
        raw = r.read()
        dt = time.time() - t0
        c.close()
        if r.status != 200:
            return {"error": "HTTP %d %s" % (r.status, raw[:200].decode("utf-8", "replace")), "seconds": dt}
        return {"json": json.loads(raw), "seconds": dt}

    def chat(self, model, messages, max_tokens, extra=None):
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True, "temperature": 0.2, "seed": 7,
                "stream_options": {"include_usage": True}, "chat_template_kwargs": {"enable_thinking": False}}
        if extra:
            body.update(extra)
        c = self._conn()
        h = self._headers()
        h["Accept"] = "text/event-stream"
        t0 = time.time()
        c.request("POST", "/v1/chat/completions", json.dumps(body), h)
        r = c.getresponse()
        if r.status != 200:
            msg = r.read()[:200].decode("utf-8", "replace")
            c.close()
            return {"error": "HTTP %d %s" % (r.status, msg)}
        first = None
        text = []
        timings = {}
        usage = {}
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            d = line[5:].strip()
            if d == "[DONE]":
                break
            try:
                j = json.loads(d)
            except ValueError:
                continue
            if j.get("timings"):
                timings = j["timings"]
            if j.get("usage"):
                usage = j["usage"]
            for ch in j.get("choices", []):
                de = ch.get("delta", {})
                piece = de.get("content") or de.get("reasoning_content")
                if piece:
                    if first is None:
                        first = time.time() - t0
                    text.append(piece)
        total = time.time() - t0
        c.close()
        out_n = timings.get("predicted_n") or usage.get("completion_tokens") or 0
        client_tps = (out_n - 1) / (total - first) if first is not None and out_n > 1 and total > first else None
        return {"first_token_s": first, "total_s": total, "prompt_n": timings.get("prompt_n"), "cache_n": timings.get("cache_n"),
                "prompt_tps": timings.get("prompt_per_second"), "gen_n": out_n, "gen_tps": timings.get("predicted_per_second") or client_tps,
                "gen_tps_client": client_tps, "draft_n": timings.get("draft_n"), "draft_accepted": timings.get("draft_n_accepted"),
                "text": "".join(text)}


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def test_chat(cl, model, reps, contention, embed_model):
    out = {}
    runs = []
    for i in range(reps):
        nonce = "run %d-%d" % (int(time.time() * 1000), i)
        r = cl.chat(model, [{"role": "system", "content": "You are STAR, a concise assistant."},
                            {"role": "user", "content": "(%s) Explain in about 100 words how a hash map handles collisions." % nonce}], 120)
        if "error" in r:
            return {"error": r["error"]}
        runs.append(r)
    out["short"] = {"first_token_s": med([r["first_token_s"] for r in runs]), "gen_tps": med([r["gen_tps"] for r in runs]),
                    "prompt_n": runs[-1]["prompt_n"], "gen_n": runs[-1]["gen_n"], "draft_n": runs[-1]["draft_n"],
                    "draft_accepted": runs[-1]["draft_accepted"]}
    nonce = "session %d" % int(time.time() * 1000)
    sysmsg = {"role": "system", "content": system_prompt(nonce)}
    hist = [sysmsg, {"role": "user", "content": "In one sentence, what is a hash map?"}]
    r1 = cl.chat(model, hist, 40)
    if "error" in r1:
        return {"error": r1["error"]}
    out["long_cold"] = {"first_token_s": r1["first_token_s"], "prompt_n": r1["prompt_n"], "cache_n": r1["cache_n"], "prompt_tps": r1["prompt_tps"]}
    hist = hist + [{"role": "assistant", "content": r1["text"]}, {"role": "user", "content": "And what is a collision, in one sentence?"}]
    r2 = cl.chat(model, hist, 40)
    if "error" in r2:
        return {"error": r2["error"]}
    out["next_turn"] = {"first_token_s": r2["first_token_s"], "prompt_n": r2["prompt_n"], "cache_n": r2["cache_n"]}
    if contention and embed_model:
        stop = threading.Event()
        counted = {"tokens": 0, "seconds": 0.0, "calls": 0}

        def hammer():
            docs = [("Chunk %d. " % k) + system_prompt(rules=3) for k in range(16)]
            while not stop.is_set():
                e = cl.post_json("/v1/embeddings", {"model": embed_model, "input": docs})
                if "error" in e:
                    break
                counted["tokens"] += (e["json"].get("usage") or {}).get("prompt_tokens", 0)
                counted["seconds"] += e["seconds"]
                counted["calls"] += 1

        th = threading.Thread(target=hammer, daemon=True)
        th.start()
        time.sleep(1.0)
        r3 = cl.chat(model, [{"role": "system", "content": "You are STAR, a concise assistant."},
                             {"role": "user", "content": "(run %d) Explain in about 100 words what a binary search tree is." % int(time.time() * 1000)}], 100)
        stop.set()
        th.join(timeout=120)
        if "error" in r3:
            out["under_embed"] = {"error": r3["error"]}
        else:
            out["under_embed"] = {"first_token_s": r3["first_token_s"], "gen_tps": r3["gen_tps"], "gen_n": r3["gen_n"],
                                  "embed_calls": counted["calls"],
                                  "embed_tps_meanwhile": (counted["tokens"] / counted["seconds"]) if counted["seconds"] else None}
    return out


def test_embed(cl, model):
    docs = [("Chunk %d (%d). " % (k, int(time.time() * 1000))) + system_prompt(rules=3) for k in range(16)]
    cl.post_json("/v1/embeddings", {"model": model, "input": docs[:1]})  # warm-up / load
    e = cl.post_json("/v1/embeddings", {"model": model, "input": docs})
    if "error" in e:
        return {"error": e["error"]}
    n = (e["json"].get("usage") or {}).get("prompt_tokens", 0)
    return {"seconds": e["seconds"], "tokens": n, "tps": n / e["seconds"] if e["seconds"] else None, "dim": len(e["json"]["data"][0]["embedding"])}


def test_rerank(cl, model):
    docs = [("Passage %d: " % k) + system_prompt(rules=2) for k in range(8)]
    body = {"model": model, "query": "How should the assistant treat a request about Luau scripts?", "documents": docs, "top_n": 3}
    cl.post_json("/v1/rerank", body)
    e = cl.post_json("/v1/rerank", body)
    if "error" in e:
        return {"error": e["error"]}
    return {"seconds": e["seconds"], "documents": len(docs)}


def f(x, d=2):
    return "-" if x is None else (("%." + str(d) + "f") % x if isinstance(x, float) else str(x))


def show(res):
    for m, r in res.get("chat", {}).items():
        if "error" in r:
            print("  %-12s ERROR %s" % (m, r["error"]))
            continue
        s, l, n = r["short"], r["long_cold"], r["next_turn"]
        print("  %-12s short: first token %ss, generation %s tok/s | cold %s-token prompt: %s tok/s, first token %ss | next turn: %s reused, "
              "%s processed, first token %ss" % (m, f(s["first_token_s"]), f(s["gen_tps"]), l["prompt_n"], f(l["prompt_tps"], 1),
                                                 f(l["first_token_s"]), n["cache_n"], n["prompt_n"], f(n["first_token_s"])))
        if s.get("draft_n"):
            print("  %-12s speculative decoding: %s of %s drafted tokens accepted" % ("", s["draft_accepted"], s["draft_n"]))
        if "under_embed" in r:
            u = r["under_embed"]
            if "error" in u:
                print("  %-12s while embedding runs: ERROR %s" % ("", u["error"]))
            else:
                print("  %-12s while embedding runs: generation %s tok/s (embedding %s tok/s meanwhile, %s batches finished)" % (
                    "", f(u["gen_tps"]), f(u["embed_tps_meanwhile"], 0), u.get("embed_calls")))
    for kind in ("embed", "rerank"):
        for m, r in res.get(kind, {}).items():
            if "error" in r:
                print("  %-12s ERROR %s" % (m, r["error"]))
            elif kind == "embed":
                print("  %-12s %s tokens in %ss = %s tok/s" % (m, r["tokens"], f(r["seconds"]), f(r["tps"], 0)))
            else:
                print("  %-12s %d documents reranked in %ss" % (m, r["documents"], f(r["seconds"])))


def compare(a_path, b_path):
    a, b = json.load(open(a_path)), json.load(open(b_path))
    print("%-34s %12s %12s %8s" % ("metric", a.get("tag", "A"), b.get("tag", "B"), "change"))
    rows = []
    for m in sorted(set(a.get("chat", {})) | set(b.get("chat", {}))):
        for sec, key, label in (("short", "first_token_s", "first token s (short)"), ("short", "gen_tps", "generation tok/s"),
                                ("long_cold", "prompt_tps", "prompt tok/s (cold)"), ("long_cold", "first_token_s", "first token s (cold long)"),
                                ("next_turn", "first_token_s", "first token s (next turn)"), ("next_turn", "cache_n", "tokens reused (next turn)"),
                                ("under_embed", "gen_tps", "generation tok/s under embed")):
            rows.append((m + " " + label, a.get("chat", {}).get(m, {}).get(sec, {}).get(key), b.get("chat", {}).get(m, {}).get(sec, {}).get(key)))
    for m in sorted(set(a.get("embed", {})) | set(b.get("embed", {}))):
        rows.append((m + " embed tok/s", a.get("embed", {}).get(m, {}).get("tps"), b.get("embed", {}).get(m, {}).get("tps")))
    for m in sorted(set(a.get("rerank", {})) | set(b.get("rerank", {}))):
        rows.append((m + " rerank s", a.get("rerank", {}).get(m, {}).get("seconds"), b.get("rerank", {}).get(m, {}).get("seconds")))
    for label, x, y in rows:
        ch = ("%+.0f%%" % ((y - x) / x * 100)) if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x else "-"
        print("%-34s %12s %12s %8s" % (label[:34], f(x), f(y), ch))


def main():
    ap = argparse.ArgumentParser(description="Measure STAR Brain first-token time and tokens/s through the API.")
    ap.add_argument("--base", default=os.environ.get("STAR_BRAIN_URL", DEFAULT_BASE))
    ap.add_argument("--keyfile", default=None, help="file holding the API key (default: ~/.star/server_api_key, then /opt/star/secrets/api_keys)")
    ap.add_argument("--models", default="star-fast", help="comma-separated chat models to test (models that are not listed by the server are skipped)")
    ap.add_argument("--embed", default="star-embed")
    ap.add_argument("--rerank", default="star-rerank")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-contention", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE.json", "AFTER.json"))
    a = ap.parse_args()
    if a.compare:
        compare(*a.compare)
        return 0
    key = load_key(a.keyfile)
    cl = Client(a.base, key, a.timeout)
    st, body = cl.get("/v1/models")
    if st != 200:
        print("cannot list models: HTTP %d (is the key file readable?)" % st)
        return 2
    have = [m.get("id") for m in json.loads(body).get("data", [])]
    res = {"tag": a.tag, "base": a.base, "time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "models_listed": have,
           "chat": {}, "embed": {}, "rerank": {}}
    emb = a.embed if a.embed in have else None
    for m in [x for x in a.models.split(",") if x]:
        if m not in have:
            print("  %-12s not listed by the server, skipped" % m)
            continue
        res["chat"][m] = test_chat(cl, m, a.reps, not a.no_contention, emb)
    if emb:
        res["embed"][emb] = test_embed(cl, emb)
    if a.rerank in have:
        res["rerank"][a.rerank] = test_rerank(cl, a.rerank)
    print("STAR Brain check '%s' at %s (%s UTC)" % (a.tag, a.base, res["time_utc"]))
    show(res)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate-%s.json" % a.tag)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print("saved " + out)
    bad = [m for m, r in res["chat"].items() if "error" in r]
    return 1 if bad or not res["chat"] else 0


if __name__ == "__main__":
    sys.exit(main())
