"""Benchmark: the offline Luau lint pipeline (star.luau_lint.lint with every opt-in check).

Lints the repository's own Luau files (evals/roblox) one by one, then one large synthetic
script built from them, the way `roblox_project_preflight` lints every script of a project.
The external luau-analyze CLI is switched off so only STAR's Python is timed.

    python benchmarks/bench_luau_lint.py [--repeat 5] [--scale 8]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from star.luau_lint import lint  # noqa: E402

EXTRA = r'''
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("Coins")
local items = {}
for i = 1, 10 do
    items[i] = {name = "item" .. i, cost = i * 5, tags = {[1] = "a", [2] = "b"}}
end
--[[ a long
comment ]]
local text = [==[ a long string with ] and ]] inside ]==]
remote.OnServerEvent:Connect(function(player, amount, target)
    local data = store:GetAsync(player.UserId)
    data.coins = data.coins + amount
    store:SetAsync(player.UserId, data)
    workspace:FindFirstChild("Part").Touched:Connect(function(hit) print(items[1][2]) end)
end)
while true do
    wait(1)
end
'''


def sources() -> list[str]:
    files = sorted((ROOT / "evals" / "roblox").rglob("*.luau"))
    return [f.read_text(encoding="utf-8", errors="replace") for f in files] + [EXTRA]


def run(code: str) -> list:
    return lint(code, external=False, safety_checks=True, script_class="Script", server_security=True)


def timed(fn, repeat: int) -> float:
    best = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        best.append((time.perf_counter() - t) * 1000)
    return statistics.median(best)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--scale", type=int, default=8, help="copies of the corpus in the large script")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    corpus = sources()
    big = "\n".join(corpus * max(1, args.scale))
    run(EXTRA)  # first-use imports
    result = {
        "files": len(corpus),
        "corpus_chars": sum(map(len, corpus)),
        "per_file_total_ms": round(timed(lambda: [run(c) for c in corpus], args.repeat), 2),
        "large_script_chars": len(big),
        "large_script_lines": big.count("\n") + 1,
        "large_script_ms": round(timed(lambda: run(big), max(1, args.repeat // 2)), 2),
        "findings_large": len(run(big)),
    }
    print(json.dumps(result) if args.json else "\n".join(f"{k}: {v}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
