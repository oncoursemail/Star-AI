#!/usr/bin/env python3
"""rr2.py BASE FIXTURE TAG [N_DOCS] [MAX_CHARS] : replay captured starkb rerank requests; median latency + full order per query."""
import json, sys, time, statistics, urllib.request
base, fx, tag = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
nd = int(sys.argv[4]) if len(sys.argv) > 4 else 15; mc = int(sys.argv[5]) if len(sys.argv) > 5 else 100000
K = open("/opt/star/secrets/api_keys").readline().strip()
def call(q, docs):
    body = {"model": "star-rerank", "query": q, "documents": docs, "top_n": len(docs)}
    req = urllib.request.Request(base + "/v1/rerank", json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": "Bearer " + K})
    t = time.time(); r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return time.time() - t, [x["index"] for x in sorted(r["results"], key=lambda x: -x["relevance_score"])]
call("warm up", ["x"])
lat, orders = [], []
for c in fx:
    dt, o = call(c["query"], [d[:mc] for d in c["docs"][:nd]]); lat.append(dt); orders.append(o)
print(json.dumps({"tag": tag, "n_docs": nd, "max_chars": mc, "median_s": round(statistics.median(lat), 3), "mean_s": round(statistics.fmean(lat), 3),
                  "total_s": round(sum(lat), 1), "orders": orders}))
