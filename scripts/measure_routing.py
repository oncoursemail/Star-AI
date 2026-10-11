"""Measure model routing through STAR's real task path, against a real STAR Server.

Every message goes through `star.desktop_core.run_task` exactly as the desktop
sends it (the message is saved, answered, the answer is saved; the post-answer
warm-up is `star.warmup.warm_up`), in a throwaway profile folder. The only
addition is a wrapper around the model client that reads the timing block
llama.cpp puts on the last chunk of each answer (tokens read, tokens reused,
tokens written and their speed). Nothing is changed in what is sent.

Scenarios (each one fits in a ten-minute measuring slot on a shared server):

  quick    a five-turn Fast-mode chat, without and with the post-answer warm-up
  roblox   one Fast-mode Roblox question (grounded in the documentation service)
  agent    two Agent-mode messages in one chat, then the same with the
           post-answer warm-up in between
  history  a chat that crosses a history-window boundary, with and without the
           post-answer warm-up, for each --budgets value

"Before" numbers come from running the same script against another checkout:

  python scripts/measure_routing.py --repo ../wt-integration --scenario quick ...

Usage:

  python scripts/measure_routing.py --endpoint http://192.168.1.20:8080/v1 \\
      --key-file ~/.star/server_api_key --model star-fast --scenario quick --out quick.json

The key is read from the file into the process environment and is never printed
or written. Take the server's measuring lock around a run (see the server notes).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

PROJECT = "STAR"
QUICK_TURNS = [
    "Hi! In one sentence, what can you help me with?",
    "Give me three short ideas for a weekend hobby.",
    "Which of those is the cheapest to start?",
    "What would I need to buy first?",
    "Thanks. Sum up your advice in one sentence.",
]
ROBLOX_PROMPT = "How do I tween a part's position smoothly with TweenService in Roblox? Give a short Luau example."
AGENT_TURNS = [
    "Which skill would help me write a clear README for a small project? Answer in two sentences, directly.",
    "Thanks. Which of those points would you start with? One sentence.",
]
FILLER = ("The lantern festival in the harbour town runs for three evenings each autumn, and every "
          "family hangs a paper lantern with its own colour and crest above the door. ")


class Watch:
    """The model client, unchanged, plus a record of each request's server-side timings."""

    def __init__(self, client, log: list):
        self._client, self._log = client, log
        self.chat = self.completions = self

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *error):
        return await self._client.__aexit__(*error)

    async def create(self, **kwargs):
        extra = kwargs.get("extra_body") or {}
        row = {"model": kwargs.get("model"), "id_slot": extra.get("id_slot"), "tools": len(kwargs.get("tools") or []),
               "max_tokens": kwargs.get("max_tokens"), "sent_at": time.perf_counter()}
        self._log.append(row)
        result = await self._client.chat.completions.create(**kwargs)
        if not kwargs.get("stream") or not hasattr(result, "__aiter__"):
            row["answered_model"] = getattr(result, "model", None)
            _timings(row, getattr(result, "timings", None))
            return result

        async def chunks():
            async for chunk in result:
                row.setdefault("first_chunk_s", round(time.perf_counter() - row["sent_at"], 3))
                if getattr(chunk, "model", None):
                    row["answered_model"] = chunk.model
                _timings(row, getattr(chunk, "timings", None))
                yield chunk
        return chunks()


def _timings(row: dict, timings) -> None:
    if isinstance(timings, dict):
        for key, name in (("prompt_n", "read"), ("cache_n", "cached"), ("predicted_n", "written"),
                          ("prompt_per_second", "read_tok_s"), ("predicted_per_second", "write_tok_s")):
            if isinstance(timings.get(key), (int, float)):
                row[name] = round(timings[key], 2) if isinstance(timings[key], float) else timings[key]


class Bench:
    def __init__(self, args, home: Path):
        import star.desktop_core as core
        import star.warmup as warmup
        from star.providers import open_client
        self.core, self.warmup, self.home = core, warmup, home
        self.log: list[dict] = []
        watched = lambda settings, **kw: Watch(open_client(settings, **kw), self.log)   # noqa: E731
        core.open_client = watched
        warmup.open_client = watched
        self.settings = core.Settings(provider="star_server", server_endpoint=args.endpoint, model=args.model,
                                      project=PROJECT, knowledge_endpoint="" if args.knowledge else "off")
        self.chats = core.Conversations(home / "conversations.sqlite3")
        try:
            from star import server_roles
            self.roles = server_roles
        except ImportError:                      # a checkout from before model routing
            self.roles = None

    def check(self) -> dict:
        """What the app does at start: the server check (which also reads the model list)."""
        from star.model_health import probe_server
        report = probe_server(self.settings, chat=False)
        return {"ok": report.get("ok"), "code": report.get("code"), "slots": report.get("slots"),
                "context_tokens": report.get("context_tokens"),
                "roles": {entry["role"]: entry["model"] for entry in report.get("roles") or []}}

    def new_chat(self, seed: list[tuple[str, str]] = ()) -> str:
        chat = self.chats.new_chat(PROJECT)
        for user, answer in seed:
            self.chats.add(PROJECT, "user", user, chat_id=chat)
            self.chats.add(PROJECT, "assistant", answer, chat_id=chat)
        return chat

    def turn(self, chat: str, text: str, mode: str = "fast") -> dict:
        self.chats.add(PROJECT, "user", text, chat_id=chat)
        mark = len(self.log)
        seen: dict = {}
        began = time.perf_counter()

        def on_event(event: dict) -> None:
            kind, now = event.get("event"), round(time.perf_counter() - began, 3)
            if kind == "assistant_delta" and str(event.get("text", "")).strip():
                seen.setdefault("first_token_s", now)
            elif kind == "model_responding":
                seen.setdefault("responding_s", now)
            elif kind == "route_selected":
                seen["profile"], seen["route_model"] = event.get("profile"), event.get("model")
            elif kind == "model_answered":
                seen["answered_model"] = event.get("model")
            elif kind == "knowledge_finished":
                seen["docs"] = {"state": event.get("state"), "passages": event.get("passages"),
                                "elapsed_ms": event.get("elapsed_ms")}
            elif kind == "luau_check_finished":
                seen["luau_check"] = event.get("state")
            elif kind in ("tool_started", "route_fallback"):
                seen.setdefault("events", []).append(kind + ":" + str(event.get("tool") or event.get("model") or ""))
        answer = self.core.run_task(self.settings, text, on_event=on_event, stream_tokens=True, mode=mode,
                                    chat_id=chat)
        total = round(time.perf_counter() - began, 3)
        self.chats.add(PROJECT, "assistant", answer, chat_id=chat)
        requests = [{key: value for key, value in row.items() if key != "sent_at"} for row in self.log[mark:]]
        first = requests[0] if requests else {}
        row = {"prompt": text[:70], "mode": mode, **seen, "total_s": total, "answer_chars": len(answer),
               "answer_start": " ".join(answer.split())[:140], "has_sources": "Sources" in answer[-900:],
               "requests": requests}
        row.setdefault("answered_model", first.get("answered_model") or first.get("model"))
        shown = (f"  {text[:44]!r:48} {str(row.get('answered_model')):11} first token {row.get('first_token_s')} s  "
                 f"read {first.get('read')} cached {first.get('cached')}  "
                 f"{first.get('written')} tok at {first.get('write_tok_s')} tok/s  total {total} s")
        print(shown, flush=True)
        return row

    def warm(self, chat: str) -> dict:
        """The post-answer warm-up the desktop starts when an answer has been saved."""
        mark = len(self.log)
        began = time.perf_counter()
        report = self.warmup.warm_up(self.settings, home=self.home, chat_id=chat, check=False)
        seconds = round(time.perf_counter() - began, 2)
        requests = [{key: value for key, value in row.items() if key != "sent_at"} for row in self.log[mark:]]
        print(f"  warm-up {seconds} s: " + ", ".join(
            f"{row.get('model')} tools={row.get('tools')} read {row.get('read')} cached {row.get('cached')}"
            for row in requests), flush=True)
        return {"seconds": seconds, "report": {k: v for k, v in report.items() if k != "error"}, "requests": requests}


def stamp(text: str) -> str:
    """A first message no server has seen, so every arm starts with an uncached conversation."""
    return f"(session {uuid.uuid4().hex[:8]}) {text}"


def quick(bench: Bench) -> dict:
    """Five turns twice: sent one right after the other, and with the post-answer warm-up the
    desktop runs after every answer (what the owner gets when reading the answer first)."""
    result = {}
    for arm, warm in (("next message sent at once", False), ("post-answer warm-up after each answer", True)):
        print(f" {arm}", flush=True)
        chat, turns, warm_ups = bench.new_chat(), [], []
        for number, text in enumerate(QUICK_TURNS):
            turns.append(bench.turn(chat, stamp(text) if number == 0 else text))
            if warm and number < len(QUICK_TURNS) - 1:
                warm_ups.append(bench.warm(chat))
        result[arm] = {"turns": turns, "warm_ups": warm_ups}
    return result


def roblox(bench: Bench) -> dict:
    chat = bench.new_chat()
    return {"turns": [bench.turn(chat, ROBLOX_PROMPT)]}


def agent(bench: Bench) -> dict:
    result = {}
    for arm, warm in (("no warm-up between the turns", False), ("post-answer warm-up between the turns", True)):
        print(f" {arm}", flush=True)
        chat = bench.new_chat()
        first = bench.turn(chat, stamp(AGENT_TURNS[0]), mode="agent")
        warmed = bench.warm(chat) if warm else None
        second = bench.turn(chat, AGENT_TURNS[1], mode="agent")
        result[arm] = {"turns": [first, second], "warm_up": warmed}
    return result


MARGIN = 40   # characters below the boundary; the crossing question alone is longer than this


def history(bench: Bench, budgets: list[int], prompt_kind: str, start_warm_up: bool = True) -> dict:
    """Seed a chat to just under a window boundary, then cross it."""
    core, result = bench.core, {}
    crossing = ("Write a python function that adds two numbers. Code only." if prompt_kind == "code"
                else "In two sentences, what is a lantern festival?")
    after = ("Now write a python function that multiplies them. Code only." if prompt_kind == "code"
             else "And in one sentence, when is it usually held?")
    for budget in budgets:
        if hasattr(core, "SERVER_HISTORY_CHARS"):
            core.SERVER_HISTORY_CHARS = budget
        real = core.history_char_budget(bench.settings)
        half = real // 2
        for warm in (False, True):
            arm = f"budget {real}, {'with' if warm else 'without'} the post-answer warm-up"
            print(f" {arm}", flush=True)
            marker = uuid.uuid4().hex[:8]
            # Exchanges of about 1,400 characters, ending MARGIN characters before the fourth half-window.
            seed, total, number = [], 0, 0
            while total < 4 * half - MARGIN - 1500:
                number += 1
                user = f"({marker}) Tell me part {number} of the story."
                answer = (FILLER * 20)[:1400 - len(user)]
                seed.append((user, answer))
                total += len(user) + len(answer)
            last_user = f"({marker}) And the last part before we change the subject?"
            seed.append((last_user, (FILLER * 20)[:max(60, 4 * half - MARGIN - total - len(last_user))]))
            chat = bench.new_chat(seed)
            before = len(core.chat_history(bench.settings, bench.home, chat)[0])
            primed = bench.warm(chat) if start_warm_up else None    # the app start: the window is read once
            crossed = bench.turn(chat, crossing)              # this answer pushes the chat over the boundary
            moved = len(core.chat_history(bench.settings, bench.home, chat)[0])
            warmed = bench.warm(chat) if warm else None
            follow = bench.turn(chat, after)                  # the message after the window moved
            result[arm] = {"history_messages_before": before, "history_messages_after_the_move": moved,
                           "start_warm_up": primed, "crossing_turn": crossed, "post_answer_warm_up": warmed,
                           "turn_after_the_move": follow}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--endpoint", required=True, help="for example http://192.168.1.20:8080/v1")
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--model", default="star-fast", help="the one configured model (Settings: Model)")
    parser.add_argument("--scenario", action="append", required=True, choices=["quick", "roblox", "agent", "history"])
    parser.add_argument("--repo", default="", help="measure another checkout's star package (the 'before' numbers)")
    parser.add_argument("--no-discovery", action="store_true", help="skip the start-up server check (no role table)")
    parser.add_argument("--knowledge", action="store_true", help="use the documentation service next to the server")
    parser.add_argument("--budgets", default="6000,12000", help="history budgets for the history scenario")
    parser.add_argument("--history-prompt", default="chat", choices=["chat", "code"],
                        help="history scenario: a plain question (quick model) or a coding one (main model)")
    parser.add_argument("--no-start-warm-up", action="store_true",
                        help="history scenario: skip the app-start warm-up (it primes the quick model only)")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))
    os.environ["STAR_SERVER_API_KEY"] = Path(args.key_file).expanduser().read_text(encoding="utf-8").strip()
    with tempfile.TemporaryDirectory(prefix="star-measure-") as folder:
        os.environ["APPDATA"] = os.environ["XDG_DATA_HOME"] = folder      # never the owner's real profile
        import star.desktop_core as core
        home = core.app_data()
        home.mkdir(parents=True, exist_ok=True)
        bench = Bench(args, home)
        report = {"repo": repo.name, "model": args.model, "knowledge": args.knowledge,
                  "started_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}
        try:
            if not args.no_discovery:
                report["server_check"] = bench.check()
                print("server check: " + json.dumps(report["server_check"]), flush=True)
            for name in args.scenario:
                print(f"\n{name} ({repo.name})", flush=True)
                report[name] = (quick(bench) if name == "quick" else roblox(bench) if name == "roblox"
                                else agent(bench) if name == "agent"
                                else history(bench, [int(value) for value in args.budgets.split(",")],
                                             args.history_prompt, not args.no_start_warm_up))
        finally:
            bench.chats.close()
            report["finished_utc"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            if args.out:
                Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
