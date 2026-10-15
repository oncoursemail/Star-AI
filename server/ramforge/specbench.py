#!/usr/bin/env python3
"""RAMForge specbench: generation speed and draft acceptance on STAR-like chat and Luau prompts.

Usage: specbench.py --base http://127.0.0.1:8094 --tag LABEL [--reps 2] [--out file.json]

Greedy decoding (temperature 0) so that a lossless speculative method must reproduce the baseline text;
the output hash per prompt is recorded so runs can be compared for identity. Each repetition uses a
slightly different prompt (different names/numbers) so that the shared n-gram pool of ngram-mod cannot
simply replay the previous answer; rep 1 and later reps are reported separately for that reason.
Server-side numbers come from the `timings` object llama-server returns (predicted_per_second, draft_n,
draft_n_accepted).
"""
import argparse
import hashlib
import json
import time
import urllib.request

SYSTEM = ("You are STAR, a Roblox game-development assistant. Answer precisely. When you write code, write "
          "complete, working Luau in a fenced ```luau block and keep explanations short.")

EDIT_SCRIPT = """local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local coinFolder = workspace:WaitForChild("Coins")
local collectEvent = ReplicatedStorage:WaitForChild("CoinCollected")

local COIN_VALUE = {value}
local RESPAWN_SECONDS = 8

local function setupLeaderstats(player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local coins = Instance.new("IntValue")
	coins.Name = "{stat}"
	coins.Value = 0
	coins.Parent = leaderstats
end

local function onCoinTouched(coin, hit)
	local character = hit.Parent
	local player = Players:GetPlayerFromCharacter(character)
	if not player then
		return
	end
	local stats = player:FindFirstChild("leaderstats")
	if not stats then
		return
	end
	stats.{stat}.Value += COIN_VALUE
	collectEvent:FireClient(player, COIN_VALUE)
	coin.Transparency = 1
	coin.CanTouch = false
	task.wait(RESPAWN_SECONDS)
	coin.Transparency = 0
	coin.CanTouch = true
end

for _, coin in ipairs(coinFolder:GetChildren()) do
	if coin:IsA("BasePart") then
		coin.Touched:Connect(function(hit)
			onCoinTouched(coin, hit)
		end)
	end
end

Players.PlayerAdded:Connect(setupLeaderstats)
"""

VARIANTS = [
    {"thing": "RemoteEvents", "game": "obby", "value": 10, "new": 25, "stat": "Coins", "door": "VaultDoor", "room": "VaultRooms", "mins": 3},
    {"thing": "RemoteFunctions", "game": "tycoon", "value": 5, "new": 15, "stat": "Gems", "door": "BossGate", "room": "Dungeon", "mins": 5},
    {"thing": "BindableEvents", "game": "racing game", "value": 2, "new": 7, "stat": "Points", "door": "FinishGate", "room": "Track", "mins": 4},
]


def prompts(v):
    return [
        ("chat", 220, [{"role": "user", "content":
            "In about 150 words, explain how %s work in a Roblox %s and how to keep them secure against exploiters." % (v["thing"], v["game"])}]),
        ("code_new", 450, [{"role": "user", "content":
            "Write a Luau ModuleScript for a %d-minute round timer in a Roblox %s: Start(), Stop(), GetRemaining(), "
            "and a Changed signal fired every second. Server-side only." % (v["mins"], v["game"])}]),
        ("code_edit", 600, [{"role": "user", "content":
            "Here is my ServerScriptService script:\n```luau\n" + EDIT_SCRIPT.format(value=v["value"], stat=v["stat"]) +
            "```\nChange the coin value from %d to %d and add a per-player debounce so one player cannot collect the "
            "same coin twice within the respawn time. Return the complete updated script." % (v["value"], v["new"])}]),
        ("debug_fix", 350, [{"role": "user", "content":
            "In my Roblox game: \"My %s is nil when the match starts, then it appears.\"\nLocation: ServerScriptService/%s Script\n"
            "Broken Luau:\n```luau\nlocal door = workspace.%s.%s\ndoor.CanCollide = false\n```\nFind and fix the bug. Return "
            "corrected Luau in fenced code and explain it briefly." % (v["door"], v["door"], v["room"], v["door"])}]),
    ]


def call(base, model, messages, max_tokens):
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM}] + messages, "max_tokens": max_tokens,
            "temperature": 0, "top_k": 1, "seed": 42, "stream": False, "cache_prompt": True}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.loads(r.read())
    wall = time.time() - t0
    t = j.get("timings") or {}
    text = j["choices"][0]["message"].get("content") or ""
    return {"wall_s": round(wall, 2), "gen_n": t.get("predicted_n"), "gen_tps": t.get("predicted_per_second"),
            "prompt_n": t.get("prompt_n"), "prompt_ms": t.get("prompt_ms"), "draft_n": t.get("draft_n"),
            "draft_accepted": t.get("draft_n_accepted"), "sha": hashlib.sha256(text.encode()).hexdigest()[:12],
            "chars": len(text)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8094")
    ap.add_argument("--model", default="star-fast")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = []
    for rep in range(a.reps):
        for kind, mt, msgs in prompts(VARIANTS[rep % len(VARIANTS)]):
            if a.only and kind not in a.only.split(","):
                continue
            r = call(a.base, a.model, msgs, mt)
            r.update({"kind": kind, "rep": rep + 1})
            rows.append(r)
            acc = ""
            if r["draft_n"]:
                acc = " draft %s accepted %s (%.0f%%)" % (r["draft_n"], r["draft_accepted"], 100.0 * r["draft_accepted"] / r["draft_n"])
            print("%-10s rep%d gen %4s tok %6.2f tok/s wall %6.1fs%s sha %s" % (kind, rep + 1, r["gen_n"], r["gen_tps"] or 0, r["wall_s"], acc, r["sha"]), flush=True)
    summary = {}
    for kind in sorted({r["kind"] for r in rows}):
        rs = [r for r in rows if r["kind"] == kind]
        tok = sum(r["gen_n"] or 0 for r in rs)
        gen_s = sum((r["gen_n"] or 0) / r["gen_tps"] for r in rs if r["gen_tps"])
        dn = sum(r["draft_n"] or 0 for r in rs)
        da = sum(r["draft_accepted"] or 0 for r in rs)
        summary[kind] = {"gen_tps": round(tok / gen_s, 2) if gen_s else None, "tokens": tok,
                         "accept": round(da / dn, 3) if dn else None, "draft_n": dn}
    allt = sum(v["tokens"] for v in summary.values())
    alls = sum(v["tokens"] / v["gen_tps"] for v in summary.values() if v["gen_tps"])
    summary["all"] = {"gen_tps": round(allt / alls, 2) if alls else None, "tokens": allt}
    print("SUMMARY", a.tag, json.dumps(summary))
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"tag": a.tag, "rows": rows, "summary": summary, "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=1)


if __name__ == "__main__":
    main()
