"""Scripted evidence for the learning loop, through the real run_task with a fake model.

    python scripts/learning_loop_demo.py

Nothing is sent anywhere and the owner's STAR data is not touched: APPDATA points at a
temporary folder and the model client is replaced by one that returns scripted answers and
records every request. The script prints what was captured, what was accepted, what a later
chat of the same project was sent, and that another project was sent nothing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    home_root = tempfile.mkdtemp(prefix="star-learning-demo-")
    os.environ["APPDATA"] = home_root
    os.environ["XDG_DATA_HOME"] = home_root

    import star.desktop_core as core
    import star.doc_grounding as doc_grounding
    from star import lessons
    from star.analytics import get_dashboard
    from star.desktop_core import Conversations, Settings, run_task

    requests: list[dict] = []
    answers: list[str] = []

    class Completions:
        async def create(self, **kwargs):
            requests.append(json.loads(json.dumps(kwargs, default=str)))
            message = SimpleNamespace(content=answers.pop(0), tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class Client:
        chat = SimpleNamespace(completions=Completions())

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    core.open_client = lambda settings, **_: Client()
    doc_grounding.client_for = lambda settings: None        # no documentation service in this demo
    home = core.app_data()
    home.mkdir(parents=True, exist_ok=True)
    chats = Conversations(home / "conversations.sqlite3")

    def last_user_turn() -> str:
        content = requests[-1]["messages"][-1]["content"]
        return content if isinstance(content, str) else "".join(part.get("text", "") for part in content)

    def turn(project: str, text: str, answer: str) -> tuple[list[dict], int]:
        """What the desktop bridge does for one message: save it, answer it, save the answer."""
        settings = Settings(model="fake-model", project=project)
        chat = chats.active_chat(project)
        chats.add(project, "user", text, chat_id=chat)
        answers.append(answer)
        events: list[dict] = []
        result = run_task(settings, text, chat_id=chat, mode="fast", on_event=events.append)
        return events, chats.add(project, "assistant", result, chat_id=chat)

    def show(title: str, body: str) -> None:
        print(f"\n== {title}\n{body}")

    correction = "No, use task.wait instead of wait."
    turn("Obby", "How do I pause for one second in a script?", "Call wait(1).")
    show("Turn 1 (project Obby, chat A): final user turn sent to the model", last_user_turn())

    events, _ = turn("Obby", correction, "Understood: task.wait(1).")
    show("Turn 2 (same chat): the owner corrects the answer. Final user turn sent to the model", last_user_turn())
    show("Turn 2: capture event after the answer", json.dumps([e for e in events if e.get("event") == "lessons_captured"]))
    listing = lessons.handle_action(home, "Obby", "listLessons", {})
    record = listing["lessons"][0]
    show("Lesson record (accepted because it is the owner's own words)", json.dumps(
        {key: record[key] for key in ("id", "project", "kind", "status", "source_type", "source", "origin", "text", "evidence")},
        indent=2))

    chats.new_chat("Obby")
    turn("Obby", "Write a loop that spawns a part every second.", "while true do task.wait(1) end")
    recalled = last_user_turn()
    show("Turn 3 (project Obby, NEW chat B): final user turn sent to the model", recalled)
    same_system = requests[0]["messages"][0] == requests[-1]["messages"][0]

    turn("Racing", "Write a loop that spawns a part every second.", "ok")
    other = last_user_turn()
    show("Same question in ANOTHER project (Racing): final user turn sent to the model", other)

    # Something STAR inferred (a thumbs-down) stays a candidate and is not sent to the model.
    _, answer_id = turn("Obby", "How do I tween a door open?", "Use BodyPosition.")
    lessons.handle_action(home, "Obby", "messageFeedback", {"messageId": answer_id, "value": "down"})
    turn("Obby", "How do I tween a door open again?", "Use TweenService.")
    after_feedback = last_user_turn()
    counts = lessons.handle_action(home, "Obby", "listLessons", {})["counts"]
    show("After a thumbs-down in Obby: lesson counts", json.dumps(counts))
    show("Analytics (Obby)", json.dumps(get_dashboard(home, "Obby")["learning"]))
    show("Analytics (Racing)", json.dumps(get_dashboard(home, "Racing")["learning"]))
    chats.close()

    checks = {
        "captured after the correcting turn": record["text"] == correction and record["status"] == "accepted",
        "the correcting turn itself carried no extra context": requests[1]["messages"][-1]["content"] in (correction, [{"type": "text", "text": correction}]),
        "recalled in a later chat of the same project": correction in recalled,
        "system message unchanged by the lesson": same_system,
        "not sent to another project": correction not in json.dumps(requests[3]),
        "inferred candidate not sent to the model": "marked not helpful" not in after_feedback and counts["pending"] == 1,
    }
    print("\n== Checks")
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
