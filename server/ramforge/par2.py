#!/usr/bin/env python3
"""par2.py BASE K : K background streams (300 tokens) start together; 6 s later one chat request (150 tokens).
Prints chat first token / tok/s, background tok/s, aggregate tok/s over the whole run (JSON)."""
import sys, threading, time, json
sys.path.insert(0, "/opt/star/bench")
from validate import Client
base, k = sys.argv[1], int(sys.argv[2])
cl = Client(base, None, 900)
res = {}
def run(name, prompt, n):
    t0 = time.time(); r = cl.chat("star-fast", [{"role": "user", "content": prompt}], n); r["wall"] = time.time() - t0; res[name] = r
ts = [threading.Thread(target=run, args=("bg%d" % i, "(%d %f) Write a long, detailed guide to Roblox DataStore session locking, with code." % (i, time.time()), 300)) for i in range(k)]
t0 = time.time(); [t.start() for t in ts]
if k: time.sleep(6)
c = threading.Thread(target=run, args=("chat", "(%f) In about 100 words, how do I make a part spin in Roblox?" % time.time(), 150)); c.start()
[t.join() for t in ts]; c.join(); wall = time.time() - t0
tot = sum((r.get("gen_n") or 0) for r in res.values())
print(json.dumps({"k": k, "chat_first_token_s": round(res["chat"].get("first_token_s") or -1, 2), "chat_gen_tps": res["chat"].get("gen_tps"),
                  "bg_gen_tps": [res["bg%d" % i].get("gen_tps") for i in range(k)], "tokens": tot, "wall_s": round(wall, 1), "aggregate_tps": round(tot / wall, 2)}))
