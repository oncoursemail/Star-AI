"""W8: owner corrections become regression-test candidates in a separate corrections suite (star/corrections.py).

App path: thumbs-down plus a correction through the real lesson bridge (star.lessons.handle_action messageFeedback).
Discord path: `wrong: ...` in an owner DM through the real DM classifier and DiscordService. Throwaway data folders.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from star import corrections as cr
from star.desktop_core import Conversations
from star.discord_bot.core import AccessPolicy
from star.discord_bot.dm_mode import DMSettings, capture_discord_correction, classify_owner_dm
from star.discord_bot.service import DiscordService
from star.eval_checks import extract_luau_blocks, pattern_checks
from star.eval_runner import load_suite
from star.evals import load_catalog
from star.failure_ledger import CAUSES
from star.lessons import LessonStore, handle_action

FENCE = chr(96) * 3
QUESTION = "Write a Luau script that waits 2 seconds and then opens the door in my Roblox game."
ANSWER = f"Here you go:\n{FENCE}luau\nwait(2)\nworkspace.Door.Transparency = 1\n{FENCE}"


def chat_with_answer(home: Path, project: str = "MyGame") -> int:
    chats = Conversations(home / "conversations.sqlite3")
    try:
        chat = chats.active_chat(project)
        chats.add(project, "user", QUESTION, chat_id=chat)
        chats.add(project, "assistant", ANSWER, chat_id=chat)
        return int(chats.connection.execute("SELECT MAX(id) FROM messages WHERE role='assistant'").fetchone()[0])
    finally:
        chats.close()


def feedback(home, mid, value, correction=None):
    body = {"messageId": mid, "value": value}
    if correction is not None:
        body["correction"] = correction
    return handle_action(home, "MyGame", "messageFeedback", body)


def test_thumbs_down_with_a_correction_makes_exactly_one_candidate_and_no_suite(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata-must-stay-empty"))
    mid = chat_with_answer(tmp_path)
    done = feedback(tmp_path, mid, "down", "Use task.wait instead of wait, the old one is deprecated.")
    assert done["correction"]["status"] == "candidate"
    feedback(tmp_path, mid, "down", "Use task.wait instead of wait; wait() is deprecated.")   # edited, same answer
    store = cr.CorrectionStore(tmp_path)
    try:
        items = store.list("MyGame")
    finally:
        store.close()
    assert len(items) == 1
    item = items[0]
    assert item["prompt"] == QUESTION and "wait(2)" in item["answer"] and item["source"] == "app"
    assert item["correction"].startswith("Use task.wait instead of wait;")
    assert item["cause"] == "invented API name"                     # "deprecated" names that cause
    assert not (tmp_path / "corrections").exists()                  # nothing in any suite before approval
    lessons = LessonStore(tmp_path)
    try:
        waiting = [l for l in lessons.list("MyGame", "candidate")]
    finally:
        lessons.close()
    assert any(l.source_type == "chat-correction" and "task.wait" in l.text for l in waiting)
    assert all(l.status == "candidate" for l in waiting)            # a memory candidate the owner reviews
    assert not (tmp_path / "appdata-must-stay-empty").exists()


def test_taking_the_thumb_back_withdraws_the_candidate(tmp_path):
    mid = chat_with_answer(tmp_path)
    feedback(tmp_path, mid, "down", "The door should tween open, not vanish.")
    feedback(tmp_path, mid, "")
    store = cr.CorrectionStore(tmp_path)
    try:
        assert store.list("MyGame") == []
    finally:
        store.close()
    with pytest.raises(ValueError, match="thumbs-down"):
        feedback(tmp_path, mid, "up", "a correction on a thumbs-up")


def test_owner_approval_adds_a_loadable_task_to_the_corrections_suite(tmp_path):
    mid = chat_with_answer(tmp_path)
    feedback(tmp_path, mid, "down", "Use task.wait instead of wait.")
    listing = cr.handle_action(tmp_path, "MyGame", "listCorrections", {})
    item = listing["corrections"][0]
    with pytest.raises(PermissionError):
        cr.handle_action(tmp_path, "MyGame", "reviewCorrection", {"op": "approve", "id": item["id"]})
    done = cr.handle_action(tmp_path, "MyGame", "reviewCorrection", {"op": "approve", "id": item["id"], "approved": True})
    assert done["counts"] == {"candidate": 0, "approved": 1, "dismissed": 0}
    path = tmp_path / "corrections" / done["suite"]
    assert path.name == "corrections-MyGame.json" and "holdout" not in path.name
    load_catalog(path)
    suite = load_suite(path)                                         # the evaluation runner accepts it as a suite
    task = suite.tasks[0]
    assert task["id"] == f"CR-{item['id']:04d}" and task["split"] == "corrections" and task["run_mode"] == "automated"
    good = f"{FENCE}luau\ntask.wait(2)\nworkspace.Door.Transparency = 1\n{FENCE}"
    for answer, ok in ((good, True), (ANSWER, False)):
        checks = pattern_checks(task["auto"], extract_luau_blocks(answer), answer)
        assert all(c.ok for c in checks) is ok
    with pytest.raises(ValueError, match="waiting"):
        cr.handle_action(tmp_path, "MyGame", "reviewCorrection", {"op": "dismiss", "id": item["id"], "approved": True})


def test_a_correction_without_named_patterns_becomes_a_human_task_stub(tmp_path):
    store = cr.CorrectionStore(tmp_path)
    try:
        item = store.record(project="P", source="app", ref="c#1", prompt="Make the shop prices cheaper on Fridays.",
                            answer="Prices are set in the module.", correction="It ignored Fridays completely.")
        store.approve("P", item["id"], human_approved=True)
        task = json.loads(store.suite_path("P").read_text(encoding="utf-8"))[0]
    finally:
        store.close()
    assert task["run_mode"] == "human" and task["check_status"] == "stub" and "auto" not in task


def test_secrets_are_refused_and_private_addresses_scrubbed(tmp_path):
    store = cr.CorrectionStore(tmp_path)
    try:
        with pytest.raises(ValueError, match="key or password"):
            store.record(project="P", source="app", ref="c#2", prompt="Connect to my server",
                         answer="ok", correction="use " + "pass" + "word: " + "hunter2" * 2 + " for the admin panel")
        lan, other, third = ".".join(["192", "168", "1", "20"]), ".".join(["10", "0", "0", "5"]), ".".join(["172", "16", "4", "2"])
        item = store.record(project="P", source="app", ref="c#3", prompt=f"Ping {lan} from the game",
                            answer=f"Use {other}", correction=f"The server is at {third}, not that one.")
    finally:
        store.close()
    blob = json.dumps(item)
    assert lan not in blob and other not in blob and third not in blob
    assert "<private-address>" in item["prompt"] and "<private-address>" in item["correction"]


def test_the_suite_is_never_written_into_evals_or_the_holdout(tmp_path):
    with pytest.raises(ValueError, match="never written"):
        cr.write_suite(tmp_path / "evals" / "roblox" / "corrections.json", [])
    with pytest.raises(ValueError, match="never written"):
        cr.write_suite(tmp_path / "holdout-v2.json", [])
    assert not (tmp_path / "evals").exists()


def test_corrections_feed_the_failure_ledger(tmp_path):
    store = cr.CorrectionStore(tmp_path)
    try:
        for n, text in enumerate(["It is cut off halfway through the module.", "You forgot the cooldown check.",
                                  "The total is off by one.", "Syntax error on line 3."]):
            store.record(project="P", source="app", ref=f"c#{n}", prompt="Write the module.", answer="...",
                         correction=text)
        failures = store.as_failures("P")
    finally:
        store.close()
    assert {f.cause for f in failures} == {"answer cut off", "required feature missing", "wrong logic",
                                           "self-check error left unrepaired"}
    assert all(f.cause in CAUSES and f.result_file == "corrections" for f in failures)


# --- Discord ---------------------------------------------------------------------------------------------------

ON = DMSettings(enabled=True, images=False, learning_candidates=True, project="MyGame")


def test_dm_classifier_recognises_a_correction_only_when_candidates_are_on():
    action = classify_owner_dm("wrong: the leaderboard must sort high to low", attachments=0, options=ON)
    assert action.kind == "correct" and action.prompt == "the leaderboard must sort high to low"
    off = classify_owner_dm("wrong: the leaderboard must sort high to low", attachments=0,
                            options=DMSettings(enabled=True))
    assert off.kind == "ignored" and "disabled" in off.error
    assert classify_owner_dm("wrong: no", attachments=0, options=ON).kind == "ignored"
    assert classify_owner_dm("what is wrong with my code?", attachments=0, options=ON).kind == "text"


def test_discord_correction_uses_the_last_dm_answer_and_needs_an_owner(tmp_path):
    service = DiscordService(AccessPolicy(frozenset({123}), frozenset(), frozenset()))
    key = service.authorized(123, None, 789)

    async def work():
        with pytest.raises(ValueError, match="no recent STAR answer"):
            await service.propose_dm_correction(key, message_id=5, text="the sort order is reversed",
                                                project="MyGame", home=tmp_path)
        service.memory.remember(key, "Sort my leaderboard", "table.sort(t, function(a, b) return a < b end)")
        item, lesson = await service.propose_dm_correction(key, message_id=6, text="the sort order is reversed",
                                                           project="MyGame", home=tmp_path)
        assert item["source"] == "discord" and item["prompt"] == "Sort my leaderboard" and "a < b" in item["answer"]
        assert lesson.status == "candidate"
        with pytest.raises(PermissionError):
            await service.propose_dm_correction((456, 789, 123), message_id=7, text="the sort order is reversed",
                                                project="MyGame", home=tmp_path)

    asyncio.run(work())
    with pytest.raises(PermissionError):
        capture_discord_correction(owner_id=999, allowed_owners=frozenset({123}), message_id=8,
                                   text="the sort order is reversed", question="q", answer="a", project="MyGame",
                                   home=tmp_path)
    store = cr.CorrectionStore(tmp_path)
    try:
        assert len(store.list("MyGame")) == 1 and not store.suite_path("MyGame").exists()
    finally:
        store.close()
