"""Benchmark: Python-side cost of one chat turn (no network, fake model client).

Runs `desktop_core.run_task` end to end in a private, throw-away app-data folder with a
model client that answers instantly, so every millisecond measured is STAR's own work:
settings validation, opening the stores, the history window, retrieval, skill packs,
system prompt and request assembly, saving the answer and after-turn learning.

    python benchmarks/bench_chat_turn.py [--turns 40] [--history 200] [--profile out.prof]
"""
from __future__ import annotations

import argparse
import cProfile
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROMPTS = (
    "How do I make a RemoteEvent that validates the player on the server in Roblox?",
    "Write a short Luau ModuleScript for a round timer with intermission in Roblox Studio.",
    "What is the capital of France?",
    "Make a ParticleEmitter burst with sparks and a shockwave when a Roblox part explodes.",
)


def reply(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))])


class Models:
    def __init__(self):
        self.requests = 0

    async def create(self, **kwargs):
        self.requests += 1
        if kwargs.get("stream"):
            raise AssertionError("benchmark runs without streaming")
        return reply("Here is an answer with a few lines.\n" * 8)


class Client:
    def __init__(self, models):
        self.chat = SimpleNamespace(completions=models)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=40)
    parser.add_argument("--history", type=int, default=200, help="stored messages before the timed turns")
    parser.add_argument("--other-messages", type=int, default=20000,
                        help="messages in other projects and chats of the same database (a long-used install)")
    parser.add_argument("--mode", default="fast", choices=("fast", "auto", "agent"))
    parser.add_argument("--profile", help="write a cProfile file of the timed turns")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    tmp = tempfile.mkdtemp(prefix="star-bench-")
    os.environ["APPDATA"] = tmp
    os.environ["XDG_DATA_HOME"] = tmp
    started = time.perf_counter()
    import star.desktop_core as core
    import_ms = (time.perf_counter() - started) * 1000

    models = Models()
    core.open_client = lambda settings, **_: Client(models)
    home = core.app_data()
    home.mkdir(parents=True, exist_ok=True)
    chats = core.Conversations(home / "conversations.sqlite3")
    chat = chats.new_chat("STAR")
    for index in range(args.history):
        chats.add("STAR", "user" if index % 2 == 0 else "assistant",
                  f"message {index} " + "lorem ipsum dolor sit amet " * 20, chat_id=chat)
    rows = [(f"Project{i % 6}", "user" if i % 2 else "assistant", "x" * 400, "2026-10-01T12:00:00+00:00",
             f"chat{i % 150}" if i % 40 else "legacy") for i in range(args.other_messages)]
    chats.connection.executemany("INSERT INTO messages(project,role,body,created,chat_id) VALUES (?,?,?,?,?)", rows)
    chats.connection.commit()
    settings = core.Settings(model="qwen-test")

    def turn(index):
        text = PROMPTS[index % len(PROMPTS)]
        chats.add("STAR", "user", text, chat_id=chat)
        answer = core.run_task(settings, text, chat_id=chat, mode=args.mode)
        chats.add("STAR", "assistant", answer, chat_id=chat)

    turn(0)  # warm-up: first-use imports and caches are not part of the steady-state number
    profiler = cProfile.Profile() if args.profile else None
    times = []
    for index in range(1, args.turns + 1):
        if profiler:
            profiler.enable()
        t0 = time.perf_counter()
        turn(index)
        times.append((time.perf_counter() - t0) * 1000)
        if profiler:
            profiler.disable()
    chats.close()
    if profiler:
        profiler.dump_stats(args.profile)
    result = {
        "import_desktop_core_ms": round(import_ms, 1),
        "turns": args.turns,
        "history_messages": args.history,
        "other_messages": args.other_messages,
        "turn_ms_median": round(statistics.median(times), 2),
        "turn_ms_p90": round(sorted(times)[int(0.9 * (len(times) - 1))], 2),
        "turn_ms_min": round(min(times), 2),
    }
    print(json.dumps(result) if args.json else "\n".join(f"{k}: {v}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
