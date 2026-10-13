"""CI-backed real timers against the full run_task fake stream, no network."""
import warnings
import hashlib
import asyncio
from types import SimpleNamespace

import pytest

from scripts.audit_first_word_offline import PROMPTS, audit, report


def test_real_first_visible_delta_includes_ten_stage_timings(monkeypatch):
    monkeypatch.setenv('STAR_FAST_FIRST_DELTA', '0')
    rows = audit()
    assert len(rows) == len(PROMPTS) == 10
    assert [row.index for row in rows] == list(range(1, 11))
    assert all(row.elapsed_ms > 0 and row.prompt_chars > 0 for row in rows)
    assert all(row.answer.startswith("READY") for row in rows)
    assert all(row.stages_ms["history"] >= 0 for row in rows)
    assert all(row.stages_ms["knowledge"] >= 0 for row in rows)
    assert all(row.stages_ms["documents"] >= 0 for row in rows)
    # Pytest prints the measured table in CI's warning summary; no fabricated numbers.
    warnings.warn("OFFLINE_FIRST_WORD_TABLE\\n" + report(rows), RuntimeWarning, stacklevel=1)


@pytest.mark.parametrize("enabled", [False, True])
def test_first_short_stream_delta_arrives_before_the_second_chunk(monkeypatch, enabled):
    import asyncio
    from types import SimpleNamespace
    import star.agent as agent
    from star.agent import read_stream

    # Freeze only the stream flush clock; otherwise a busy CI runner could
    # reach the old 75-ms threshold even before the first short chunk.
    monkeypatch.setattr(agent, "monotonic", lambda: 100.0)
    monkeypatch.setenv("STAR_FAST_FIRST_DELTA", "1" if enabled else "0")
    received = []

    def chunk(content, finish_reason=None):
        return SimpleNamespace(model="fake", choices=[SimpleNamespace(
            delta=SimpleNamespace(content=content, tool_calls=[]),
            finish_reason=finish_reason)])

    async def sequence():
        yield chunk("Hello")
        # The default behavior remains unchanged; the opted-in run must show
        # a short first delta *before* the second chunk arrives.
        observed = any(event.get("event") == "assistant_delta" and event.get("text") == "Hello"
                       for event in received)
        assert observed is enabled
        yield chunk(" there", "stop")

    result, tools, shown = asyncio.run(read_stream(sequence(), received.append))
    assert result == "Hello there" and tools == [] and shown
    assert "".join(event.get("text", "") for event in received
                   if event.get("event") == "assistant_delta") == result


def test_opt_in_ten_turn_before_after_matches_prompts_answers(monkeypatch):
    # Wall-clock deltas are measurements, not deterministic test predicates:
    # the old 30ms-per-turn assertion failed under Windows scheduling noise.
    for name in ("STAR_FAST_FIRST_DELTA", "STAR_FAST_GROUNDING_NOOP", "STAR_FAST_HISTORY_SNAPSHOT"):
        monkeypatch.delenv(name, raising=False)
    baseline = audit()
    monkeypatch.setenv("STAR_FAST_FIRST_DELTA", "1")
    first_delta = audit()
    monkeypatch.setenv("STAR_FAST_GROUNDING_NOOP", "1")
    no_thread = audit()
    monkeypatch.setenv("STAR_FAST_HISTORY_SNAPSHOT", "1")
    combined = audit()
    assert len(baseline) == len(first_delta) == len(no_thread) == len(combined) == len(PROMPTS) == 10
    for rows in (first_delta, no_thread, combined):
        assert [row.prompt_chars for row in rows] == [row.prompt_chars for row in baseline]
        assert [row.answer for row in rows] == [row.answer for row in baseline]
    warnings.warn("OFFLINE_FIRST_WORD_BEFORE_AFTER\nBEFORE\n" + report(baseline)
                  + "\nFIRST_DELTA\n" + report(first_delta)
                  + "\nDOC_NOOP\n" + report(no_thread)
                  + "\nALL_THREE\n" + report(combined), RuntimeWarning, stacklevel=1)


def test_history_connection_reuse_is_opt_in_and_detects_tampered_checkpoint(monkeypatch, tmp_path):
    from star import conversation_memory as cm, desktop_core as core

    home = tmp_path / "home"
    home.mkdir()
    store = core.Conversations(home / "conversations.sqlite3")
    chat = store.new_chat("STAR")
    for i in range(3):
        store.add("STAR", "user", f"Earlier question {i}", chat_id=chat)
        store.add("STAR", "assistant", f"Earlier answer {i}", chat_id=chat)
    records = store.raw_history_records("STAR", chat)
    prefix = records[:2]
    summary = "A prior checkpoint"
    checkpoint = cm.Checkpoint("STAR", chat, prefix[-1]["id"], cm.source_digest(prefix),
                               summary, hashlib.sha256(summary.encode("utf-8")).hexdigest())
    store.close()
    cm.commit(home / "conversations.sqlite3", cm.Prepared(checkpoint, None, True))
    settings = core.Settings(model="offline-fake", project="STAR")

    monkeypatch.delenv("STAR_FAST_HISTORY_SNAPSHOT", raising=False)
    original = core.chat_history_snapshot(settings, home, chat)
    monkeypatch.setenv("STAR_FAST_HISTORY_SNAPSHOT", "1")
    assert core.chat_history_snapshot(settings, home, chat) == original
    assert original[1] == records
    assert original[0].through_id >= checkpoint.through_id

    # The shortcut genuinely uses the existing read connection.
    def forbidden(*args, **kwargs):
        raise AssertionError("shortcut opened the second checkpoint reader")
    monkeypatch.setattr(cm, "read_checkpoint", forbidden)
    assert core.chat_history_snapshot(settings, home, chat) == original

    # The same checkpoint integrity failure must remain fatal.
    db = core.Conversations(home / "conversations.sqlite3")
    try:
        with db.connection:
            db.connection.execute("UPDATE conversation_checkpoints SET summary='tampered' WHERE project='STAR'")
    finally:
        db.close()
    with pytest.raises(cm.ConversationRetentionError, match="integrity"):
        core.chat_history_snapshot(settings, home, chat)


def test_grounding_noop_opt_in_avoids_thread_without_suppressing_followup(monkeypatch):
    from star import doc_grounding
    from star.brain_router import NO_GROUNDING

    settings = SimpleNamespace()
    route = SimpleNamespace(grounding=NO_GROUNDING)
    monkeypatch.delenv("STAR_FAST_GROUNDING_NOOP", raising=False)
    baseline = asyncio.run(doc_grounding.prepare_async(settings, route, "hello", [],
                                                       mode="fast", client=None))
    monkeypatch.setenv("STAR_FAST_GROUNDING_NOOP", "1")

    async def forbidden(*args, **kwargs):
        raise AssertionError("grounding noop scheduled a worker")
    monkeypatch.setattr(doc_grounding.asyncio, "to_thread", forbidden)
    result = asyncio.run(doc_grounding.prepare_async(settings, route, "hello", [],
                                                     mode="fast", client=None))
    assert result == baseline

    seen = []
    async def fake_thread(func, *args, **kwargs):
        seen.append(True)
        return func(*args, **kwargs)
    monkeypatch.setattr(doc_grounding.asyncio, "to_thread", fake_thread)
    follow = asyncio.run(doc_grounding.prepare_async(
        settings, route, "How does that work?", ["How do I use Roblox TweenService?"],
        mode="fast", client=None))
    assert seen
    assert follow.plan.retrieve != "none"
