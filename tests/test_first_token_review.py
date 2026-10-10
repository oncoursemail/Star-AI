"""Regressions found by the independent review of the request-layout change.

Each test failed on the branch as it was handed over (7d743ba) and names the
behaviour that was wrong.
"""
import json

from star.context_layout import NO_REPLY, conversation_window, exchanges

from test_first_token import desk, text_of   # noqa: F401  (pytest fixture and helper)


# ------------------------------------------------------------------ stopped and failed turns

def test_a_stopped_turn_is_still_known_to_the_next_one(desk):
    """Stop a long answer, then refine the request: the model must know what "it" is.

    The old layout replayed the unanswered message in its transcript; the new one
    dropped it, so "make it shorter" reached the model with nothing to refer to.
    """
    desk.turn("first", "one")
    stopped = desk.chats.add("STAR", "user", "Write a long sword combat script", chat_id=desk.chat)
    desk.chats.add_terminal("STAR", desk.chat, stopped, "cancelled", "SECRET-FAILURE-TEXT")
    messages = desk.turn("make it shorter please", "A short one.")["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert [text_of(m) for m in messages[1:]] == [
        "first", "one", "Write a long sword combat script", NO_REPLY, "make it shorter please"]
    assert "SECRET-FAILURE-TEXT" not in json.dumps(messages)       # the failure record itself stays out
    # It is ordinary append-only history from then on: the next request starts with the same bytes.
    later = desk.turn("thanks", "You are welcome.")["messages"]
    assert later[:5] == messages[:5]
    assert [text_of(m) for m in later[5:]] == ["make it shorter please", "A short one.", "thanks"]


def test_sending_the_same_message_again_is_not_replayed_twice():
    rows = [("user", "first"), ("assistant", "one"), ("user", "try this"), ("user", "try this")]
    assert [m["content"] for m in conversation_window(rows, budget_chars=6000)] == ["first", "one"]
    # Several different unanswered messages are all kept, in order, each marked as unanswered.
    rows = [("user", "a"), ("user", "b"), ("user", "c"), ("assistant", "C")]
    assert [m["content"] for m in exchanges(rows)] == ["a", NO_REPLY, "b", NO_REPLY, "c", "C"]
    assert [m["role"] for m in exchanges(rows)] == ["user", "assistant"] * 3
