"""Bridge regression: navigation cannot move a running turn into another chat."""
from star.desktop_core import Conversations
from star.react_shell import TurnRef, run_worker


def test_bridge_worker_persists_answer_in_origin_chat_after_switch(tmp_path):
    home = tmp_path
    store = Conversations(home / "conversations.sqlite3")
    try:
        first = store.active_chat("STAR")
        user_id = store.add("STAR", "user", "Create a forest", chat_id=first)
        second = store.new_chat("STAR")
        store.switch_chat("STAR", second)
    finally:
        store.close()

    events = []

    def worker():
        # The worker keeps the origin id, not the currently selected chat.
        chats = Conversations(home / "conversations.sqlite3")
        try:
            chats.add("STAR", "assistant", "Forest complete", chat_id=first)
        finally:
            chats.close()
        return {"answer": "Forest complete"}

    run_worker("request-1", "sendMessage", worker,
               emit=lambda rid, kind, data: events.append((rid, kind, data)),
               home=home, current_turn=lambda: TurnRef("STAR", first, user_id),
               cancelled=lambda: False)

    saved = Conversations(home / "conversations.sqlite3")
    try:
        assert saved.active_chat("STAR") == second
        assert [r[1] for r in saved.recent("STAR", chat_id=first)] == [
            "Create a forest", "Forest complete"
        ]
        assert saved.recent("STAR", chat_id=second) == []
    finally:
        saved.close()
    assert events == [("request-1", "result", {"answer": "Forest complete"})]
