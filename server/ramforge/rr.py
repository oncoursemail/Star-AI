#!/usr/bin/env python3
"""rr.py TAG : star-rerank latency like starkb search (15 documents per query): 10 distinct queries, then the same 10 again."""
import json, time, statistics, urllib.request, sys
K = open("/opt/star/secrets/api_keys").readline().strip()
TOP = ["DataStoreService", "RemoteEvent", "TweenService", "Humanoid", "CollectionService", "PathfindingService",
       "RunService.Heartbeat", "ProximityPrompt", "MarketplaceService", "ContextActionService", "Attributes", "ModuleScript",
       "BindableEvent", "SoundService", "Workspace.StreamingEnabled"]
DOCS = [("%s. " % t) + ("The %s API in Roblox lets a developer work with game state. It has properties, methods and events. "
        "Use it from server scripts or local scripts as documented; check the threading model, rate limits and error handling. " % t) * 4
        for t in TOP]
Q = ["How do I save player coins between sessions?", "How can the client tell the server a button was pressed?",
     "Smoothly move a door part over two seconds", "Make an NPC walk around walls to a target", "Tag many parts and give them all the same behaviour",
     "Run code every frame on the client", "Show an interact prompt when a player is near a chest", "Sell a game pass and check ownership",
     "Bind a key to an action on PC and a button on mobile", "Store a custom value on a part without a ValueBase"]
def call(q):
    body = {"model": "star-rerank", "query": q, "documents": DOCS, "top_n": 5}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/rerank", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + K})
    t = time.time(); r = json.loads(urllib.request.urlopen(req, timeout=300).read()); return time.time() - t, [x["index"] for x in r["results"]]
call("warm up")
first = [call(q) for q in Q]; second = [call(q) for q in Q]
print(json.dumps({"tag": sys.argv[1], "first_median_s": round(statistics.median(x[0] for x in first), 3),
                  "repeat_median_s": round(statistics.median(x[0] for x in second), 3),
                  "first_total_s": round(sum(x[0] for x in first), 2), "repeat_total_s": round(sum(x[0] for x in second), 2),
                  "top5_same_on_repeat": sum(a[1] == b[1] for a, b in zip(first, second)), "top5": [x[1] for x in first]}))
