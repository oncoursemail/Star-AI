#!/usr/bin/env python3
"""greedy.py OUT.json : greedy answers from the live router (star-fast, star-quick) for fixed prompts; prints sha + start."""
import json, sys, hashlib, urllib.request
K = open("/opt/star/secrets/api_keys").readline().strip()
P = [("star-fast", "What is 17 * 23? Answer with the number only.", 16),
     ("star-fast", "Write a Luau function `sum(t)` that returns the sum of a numeric array. Code only.", 120),
     ("star-fast", "Name the Roblox service used to save player data between sessions. One line.", 40),
     ("star-quick", "What is 17 * 23? Answer with the number only.", 16),
     ("star-quick", "Write a Luau function `sum(t)` that returns the sum of a numeric array. Code only.", 120),
     ("star-quick", "Name the Roblox service used to save player data between sessions. One line.", 40)]
out = []
for m, q, n in P:
    body = {"model": m, "messages": [{"role": "user", "content": q}], "max_tokens": n, "temperature": 0, "top_k": 1, "seed": 42,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + K})
    t = json.loads(urllib.request.urlopen(req, timeout=300).read())["choices"][0]["message"].get("content") or ""
    s = hashlib.sha256(t.encode()).hexdigest()[:12]
    out.append({"model": m, "q": q, "sha": s, "text": t})
    print(m, s, repr(t[:70]))
json.dump(out, open(sys.argv[1], "w"), indent=1)
