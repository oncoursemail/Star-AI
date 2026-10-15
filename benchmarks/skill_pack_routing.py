"""Skill-pack routing accuracy: keyword router vs embedding router (star/skill_routing.py).

Needs an OpenAI-compatible /v1/embeddings endpoint serving star-embed-ft1 (STAR Server, or the GGUF in a local
llama-server with --embedding). Nothing is written to the repository.

    python benchmarks/skill_pack_routing.py record recorded.json          # run the pack tests, keep every routing call
    python benchmarks/skill_pack_routing.py measure recorded.json --url http://127.0.0.1:8097/v1

Two sets:
  recorded    every skill_packs.select call made by the existing pack tests, with the keyword router's answer as
              the label. The keyword router was written against these tests, so it scores ~100% here by
              construction; the question is how close the embedding router gets. Split 50/50 by a hash of the
              prompt: the similarity floor is chosen on the first half and reported on the second.
  paraphrase  author-written requests that describe a pack's topic without its trigger words (not independent:
              written for this benchmark, before looking at any embedding score). Each lists the packs that
              would be a correct pick; every pack is enabled.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PARAPHRASES = [
    ("In my Roblox game the menu looks fine on my monitor but on phones the buttons are cut off at the edge. How do I make it fit every screen?", {"roblox-ui-layout", "design-ui-ux-for-games"}),
    ("Exploiters in my Roblox game fire the event that gives coins with any number they like. How do I stop that on the server?", {"roblox-secure-remotes", "roblox-remote-event-function-patterns"}),
    ("Players in my Roblox game sometimes lose their progress when the server shuts down. How do I make saving reliable?", {"roblox-datastore-safety", "roblox-datastore-service-patterns"}),
    ("My Roblox character's sword swing animation does not play for other players and the sword floats next to the hand.", {"roblox-animation-tools", "roblox-animation-craft"}),
    ("My Roblox map is huge and the game stutters on low-end phones; my scripts loop over every part each frame.", {"roblox-performance-streaming", "roblox-replication-hot-paths"}),
    ("My Roblox punch looks stiff and weightless. How should the wind-up and the recovery be timed so it feels strong?", {"roblox-animation-craft", "design-game-feel"}),
    ("I want sparks and a glowing streak behind a fireball in Roblox Studio. Which emitters should I use?", {"roblox-vfx", "roblox-vfx-composer"}),
    ("How should I lay out a Roblox city map so buildings snap together cleanly and stay the right size for characters?", {"roblox-building-layout", "roblox-architecture-blender"}),
    ("My Roblox shop window looks flat and boring. How do I give every panel rounded edges, outlines and one consistent colour theme?", {"roblox-ui-styles", "design-ui-ux-for-games"}),
    ("My Roblox forest scene looks washed out and fake in screenshots. How do I make the sky, fog and trees look moody?", {"roblox-environment-art"}),
    ("I am making a Roblox parkour course where you jump between platforms, die on lava and come back at the last stage you reached.", {"game-obby", "design-level-and-obby-layout"}),
    ("Roblox game idea: each player claims a base where machines make money over time and they buy more machines.", {"game-tycoon"}),
    ("A Roblox clicking game where you tap to earn points, buy multipliers and reset for a permanent bonus.", {"game-simulator"}),
    ("Roblox minigame: everyone waits in a lobby, then gets sent to an arena for three minutes, last one standing wins.", {"game-rounds", "roblox-teleport-matchmaking"}),
    ("How should a Roblox backpack of collected items be stored so players cannot give themselves items from the client?", {"game-inventory"}),
    ("In Roblox I want a villager you walk up to who asks you to collect five apples and pays you when you come back.", {"game-npc-quests"}),
    ("My Roblox script throws attempt to index nil sometimes and I cannot figure out why. How do I track it down?", {"eng-debugging"}),
    ("I want to write automated checks for my Roblox Luau module before writing the code itself.", {"eng-test-first", "roblox-luau-specs"}),
    ("In Roblox, how do I make a turret part rotate smoothly to face the nearest player?", {"roblox-game-math"}),
    ("What should players in my Roblox game do minute to minute so they keep coming back, and how fast should rewards grow?", {"design-core-loop-and-progression", "design-economy-and-fair-monetisation"}),
    ("New players quit my Roblox game in the first minute because they do not know what to do. How do I teach them?", {"design-onboarding-and-tutorial"}),
    ("How do I price things in my Roblox game so coins do not pile up endlessly and paid items still feel fair?", {"design-economy-and-fair-monetisation", "roblox-marketplace-purchases"}),
    ("How do I smoothly slide a Roblox menu in from the side over half a second?", {"roblox-tweenservice-easing"}),
    ("Roblox sword fighting: how does the server decide who got hit so laggy players cannot cheat?", {"roblox-combat-hitboxes"}),
    ("A Roblox zombie that walks around walls to chase the closest player.", {"roblox-pathfinding-npc"}),
    ("In Roblox how do I make a hover board float and glide using the newer physics movers instead of BodyVelocity?", {"roblox-physics-constraints"}),
    ("I have fifty lava parts in Roblox; how do I give them all the same kill behaviour with one script?", {"roblox-collection-tags"}),
    ("Roblox: footsteps and music should get quieter far away and duck when someone talks.", {"roblox-sound-design"}),
    ("How do I sell a double-coins pass and a one-time coin bundle in my Roblox game without losing purchases?", {"roblox-marketplace-purchases", "roblox-purchases-badges", "design-economy-and-fair-monetisation"}),
    ("In Roblox, how do I send a party of four friends together from the lobby into a private match server?", {"roblox-teleport-matchmaking", "game-rounds"}),
    ("In Roblox I want the camera to fly around the boss arena for a few seconds before the fight starts.", {"roblox-cutscenes"}),
    ("How can my website update a Roblox game's leaderboard data from outside Roblox?", {"roblox-open-cloud"}),
    ("My Roblox game works with keyboard, but players on gamepad and touch cannot sprint. How do I support all of them?", {"roblox-input-devices"}),
    ("Roblox: how are you today?", set()),
    ("What year was Roblox released?", set()),
    ("Thanks, that Roblox answer helped a lot!", set()),
]


def record(out: Path) -> None:
    import pytest
    from star import skill_packs
    calls = []
    original = skill_packs.select

    def recording(prompt, *, enabled=None, limit=skill_packs.MAX_PACKS_PER_TURN, home=None):
        result = original(prompt, enabled=enabled, limit=limit, home=home)
        if isinstance(prompt, str) and enabled is not None:
            calls.append({"prompt": prompt, "enabled": sorted(enabled), "limit": limit,
                          "result": [p.name for p in result]})
        return result
    skill_packs.select = recording
    files = sorted(str(p) for p in (ROOT / "tests").glob("test_*pack*.py") if "packag" not in p.name)
    code = pytest.main(["-q", "-p", "no:cacheprovider", *files])
    seen, unique = set(), []
    for call in calls:
        key = (call["prompt"], tuple(call["enabled"]), call["limit"])
        if key not in seen:
            seen.add(key)
            unique.append(call)
    out.write_text(json.dumps(unique, indent=1), encoding="utf-8")
    print(f"pytest exit {code}; {len(unique)} distinct routing calls -> {out}")


def embedder(url: str, model: str):
    import httpx
    client = httpx.Client(base_url=url.rstrip("/"), timeout=120)

    async def embed(texts):
        out = []
        for start in range(0, len(texts), 32):
            reply = client.post("/embeddings", json={"model": model, "input": texts[start:start + 32]})
            reply.raise_for_status()
            out.extend(row["embedding"] for row in sorted(reply.json()["data"], key=lambda r: r["index"]))
        return out
    return embed


def measure(recorded: Path, url: str, model: str) -> None:
    from star import skill_packs, skill_routing
    skill_routing.QUERY_TIMEOUT = skill_routing.PACKS_TIMEOUT = 600.0     # offline measurement, no turn deadline
    embed = embedder(url, model)
    rows = json.loads(recorded.read_text(encoding="utf-8"))
    known = frozenset(p.name for p in skill_packs.available())
    paraphrases = [{"prompt": p, "enabled": sorted(known), "limit": 1, "accept": sorted(a)} for p, a in PARAPHRASES]

    async def ranked(row):
        return await skill_routing.rank(row["prompt"], embed, allowed=frozenset(row["enabled"]))
    loop = asyncio.new_event_loop()
    for row in rows + paraphrases:
        row["ranked"] = [(score, pack.name) for score, pack in loop.run_until_complete(ranked(row))]
        row["keyword"] = [p.name for p in skill_packs.select(row["prompt"], enabled=frozenset(row["enabled"]),
                                                            limit=row["limit"])]

    def pick(row, floor):
        return [name for score, name in row["ranked"] if score >= floor][:row["limit"]]

    def hybrid(row, floor):
        # What star/skill_routing.select ships: the keyword router's pick, else the embedding pick.
        return row["keyword"] or pick(row, floor)

    def correct(row, chosen):
        if "accept" in row:
            return chosen[:1] == [] if not row["accept"] else bool(chosen) and chosen[0] in row["accept"]
        return chosen == row["result"]

    half = lambda row: int(hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest(), 16) % 2
    calibration = [r for r in rows if half(r) == 0]
    test = [r for r in rows if half(r) == 1]
    floors = [round(0.20 + 0.01 * i, 2) for i in range(41)]
    best = max(floors, key=lambda f: (sum(correct(r, pick(r, f)) for r in calibration), -f))
    # Hybrid: the LOWEST floor that is still as accurate as possible on the calibration half (it adds no false
    # pick there); a lower floor lets the embedding fill more of the keyword router's silences.
    best_hybrid = max(floors, key=lambda f: (sum(correct(r, hybrid(r, f)) for r in calibration), -f))

    def report(name, subset, floor):
        pos = [r for r in subset if (r.get("accept") if "accept" in r else r["result"])]
        neg = [r for r in subset if r not in pos]
        kw = sum(correct(r, r["keyword"]) for r in subset)
        em = sum(correct(r, pick(r, floor)) for r in subset)
        kwp = sum(correct(r, r["keyword"]) for r in pos)
        emp = sum(correct(r, pick(r, floor)) for r in pos)
        kwn = sum(correct(r, r["keyword"]) for r in neg)
        emn = sum(correct(r, pick(r, floor)) for r in neg)
        hy = sum(correct(r, hybrid(r, floor)) for r in subset)
        hyp = sum(correct(r, hybrid(r, floor)) for r in pos)
        hyn = sum(correct(r, hybrid(r, floor)) for r in neg)
        print(f"{name}: n={len(subset)} (pack expected {len(pos)}, none expected {len(neg)}) floor={floor}")
        print(f"  keyword   {kw}/{len(subset)}  (picks right pack {kwp}/{len(pos)}, stays silent {kwn}/{len(neg)})")
        print(f"  embedding {em}/{len(subset)}  (picks right pack {emp}/{len(pos)}, stays silent {emn}/{len(neg)})")
        print(f"  hybrid    {hy}/{len(subset)}  (picks right pack {hyp}/{len(pos)}, stays silent {hyn}/{len(neg)})")

    print(f"floor chosen on the calibration half: embedding alone {best}, hybrid {best_hybrid}")
    print(f"shipped floor (star/skill_routing.MIN_SIMILARITY): {skill_routing.MIN_SIMILARITY}")
    for floor in sorted({best, best_hybrid, skill_routing.MIN_SIMILARITY}):
        report("recorded, test half", test, floor)
        report("paraphrase", paraphrases, floor)
    print("hybrid sweep: floor, recorded test half, paraphrase")
    for floor in floors[10:31:2]:
        print(f"  {floor:.2f}  {sum(correct(r, hybrid(r, floor)) for r in test)}/{len(test)}"
              f"  {sum(correct(r, hybrid(r, floor)) for r in paraphrases)}/{len(paraphrases)}")
    for row in paraphrases:
        chosen = hybrid(row, skill_routing.MIN_SIMILARITY)
        mark = "ok " if correct(row, chosen) else "MISS"
        top = row["ranked"][0] if row["ranked"] else (0, "-")
        print(f"  {mark} kw={row['keyword'] or '-'} emb={chosen or '-'} top={top[1]} {top[0]:.3f} :: {row['prompt'][:70]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("out", type=Path)
    mea = sub.add_parser("measure")
    mea.add_argument("recorded", type=Path)
    mea.add_argument("--url", default="http://127.0.0.1:8097/v1")
    mea.add_argument("--model", default="star-embed-ft1")
    args = parser.parse_args()
    record(args.out) if args.command == "record" else measure(args.recorded, args.url, args.model)


if __name__ == "__main__":
    main()
