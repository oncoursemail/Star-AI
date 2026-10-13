"""Offline timing of the real run_task path through a deterministic streaming fake.

No real provider, Studio, network, server or keyring. Stage times are wall clock
observations and have noisy CI variance; they do not represent production TTFT.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import ExitStack, asynccontextmanager
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from types import SimpleNamespace
from unittest.mock import patch

from star import desktop_core as core, doc_grounding, lessons, skill_packs, knowledge

PROMPTS = (
    "How does Roblox TweenService move a door?",
    "Can the same door close after a delay?",
    "What does the RemoteEvent server handler validate?",
    "How does an NPC detect a nearby player?",
    "Can a Humanoid move to the next waypoint?",
    "What is the cost of checking every frame?",
    "How should a DataStore UpdateAsync call be retried?",
    "What does UIListLayout do in a Roblox menu?",
    "How should I debug an Unknown type NPC error in Luau?",
    "Summarise those Roblox debugging steps.",
)


@dataclass(frozen=True)
class Row:
    index: int
    elapsed_ms: float
    stages_ms: dict[str, float]
    prompt_chars: int
    answer: str


class FakeCompletions:
    def __init__(self):
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if kwargs.get("stream"):
            async def chunks():
                yield SimpleNamespace(model="offline-fake", choices=[
                    SimpleNamespace(delta=SimpleNamespace(content="READY " * 20, tool_calls=None),
                                    finish_reason="stop")])
            return chunks()
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="READY " * 20, tool_calls=None),
            finish_reason="stop")])


def audit() -> list[Row]:
    rows: list[Row] = []
    with TemporaryDirectory(prefix="star-first-word-audit-") as tmp:
        home = Path(tmp)
        settings_file = home / "settings.json"
        settings_file.write_text(json.dumps({"model": "offline-fake"}), encoding="utf-8")
        models = FakeCompletions()

        @asynccontextmanager
        async def client(*_args, **_kwargs):
            yield SimpleNamespace(chat=SimpleNamespace(completions=models))

        from star import doc_grounding as grounding

        with ExitStack() as stack:
            stack.enter_context(patch.object(core, "app_data", lambda: home))
            stack.enter_context(patch.object(core, "open_client", client))
            stack.enter_context(patch.object(grounding, "client_for", lambda settings: None))
            # No network: the fake provider and empty official-docs client are explicit.
            chats = core.Conversations(home / "conversations.sqlite3")
            chat_id = chats.new_chat("STAR")
            try:
                for index, prompt in enumerate(PROMPTS, 1):
                    timings = defaultdict(float)

                    def track(obj, method, label):
                        original = getattr(obj, method)
                        def call(*args, **kwargs):
                            start = perf_counter_ns()
                            try:
                                return original(*args, **kwargs)
                            finally:
                                timings[label] += (perf_counter_ns() - start) / 1_000_000
                        return patch.object(obj, method, call)

                    with ExitStack() as per_turn:
                        per_turn.enter_context(track(core, "chat_history_snapshot", "history"))
                        per_turn.enter_context(track(knowledge.KnowledgeStore, "find_contextual", "knowledge"))
                        per_turn.enter_context(track(lessons.LessonStore, "recall", "lessons"))
                        per_turn.enter_context(track(skill_packs, "select", "skills"))
                        original_async = doc_grounding.prepare_async
                        async def docs(*args, **kwargs):
                            started = perf_counter_ns()
                            try:
                                return await original_async(*args, **kwargs)
                            finally:
                                timings["documents"] += (perf_counter_ns() - started) / 1_000_000
                        per_turn.enter_context(patch.object(doc_grounding, "prepare_async", docs))

                        start = perf_counter_ns()
                        loaded = core.Settings.load(settings_file)
                        timings["settings"] += (perf_counter_ns() - start) / 1_000_000
                        chats.add("STAR", "user", prompt, chat_id=chat_id)
                        first = []
                        def on_event(event):
                            if event.get("event") == "assistant_delta" and str(event.get("text", "")).strip() and not first:
                                first.append(perf_counter_ns())
                        answer = core.run_task(loaded, prompt, chat_id=chat_id, mode="fast",
                                               stream_tokens=True, on_event=on_event)
                        if not first:
                            raise AssertionError("fake provider produced no first visible delta")
                        chats.add("STAR", "assistant", answer, chat_id=chat_id)
                        messages = models.requests[-1]["messages"]
                        size = sum(len(str(message["content"])) for message in messages)
                        elapsed = (first[0] - start) / 1_000_000
                        tracked = sum(timings.values())
                        stages = dict(timings)
                        stages["other (incl. assembly/provider)"] = max(0.0, elapsed - tracked)
                        rows.append(Row(index, elapsed, stages, size, answer))
            finally:
                chats.close()
    return rows


def report(rows: list[Row]) -> str:
    keys = ("settings", "history", "knowledge", "lessons", "documents", "skills",
            "other (incl. assembly/provider)")
    lines = ["turn | prompt chars | first delta ms | " + " | ".join(keys)]
    for row in rows:
        lines.append(f"{row.index:>4} | {row.prompt_chars:>12} | {row.elapsed_ms:>14.2f} | " +
                     " | ".join(f"{row.stages_ms.get(k, 0):.2f}" for k in keys))
    return "\\n".join(lines)


if __name__ == "__main__":
    print(report(audit()))
