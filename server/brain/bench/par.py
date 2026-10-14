#!/usr/bin/env python3
"""N concurrent streamed chats against one server; prints per-stream and aggregate generation tok/s."""
import sys, threading, time, json
sys.path.insert(0, "/opt/star/bench")
from validate import Client, load_key
base, model, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
cl = Client(base, load_key(sys.argv[4]) if len(sys.argv) > 4 else None, 900)
res = [None] * n
def run(i):
    msgs = [{"role": "user", "content": "(%d %f) Write a detailed paragraph about Luau type checking in Roblox Studio, then a second about RemoteEvents." % (i, time.time())}]
    t0 = time.time()
    r = cl.chat(model, msgs, 150)
    r["wall"] = time.time() - t0
    res[i] = r
ts = [threading.Thread(target=run, args=(i,)) for i in range(n)]
t0 = time.time()
[t.start() for t in ts]; [t.join() for t in ts]
wall = time.time() - t0
gen = [r.get("gen_tps") for r in res]
tot = sum(r.get("gen_n") or 0 for r in res)
print(json.dumps({"n": n, "per_stream_gen_tps": gen, "first_token_s": [r.get("first_token_s") for r in res], "tokens": tot, "wall_s": round(wall, 2), "aggregate_tps": round(tot / wall, 2)}))
