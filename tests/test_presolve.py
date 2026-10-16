"""Overnight pre-solving (star/presolve.py), with fake brain, fake checks and a fake chat database."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

from star import desktop_core as core, presolve

GOOD = "Here you go:\n```lua\nlocal Players = game:GetService(\"Players\")\nprint(#Players:GetPlayers())\n```\n"
LEADERBOARD = "Write a Roblox server script that makes a leaderboard with leaderstats Coins and Wins for every player"
DOOR = "Make a ProximityPrompt door script that opens the door part with TweenService and closes it after 3 seconds"


def chats(home, messages, project="STAR"):
    home.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(home / "conversations.sqlite3")
    db.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, role TEXT, body TEXT, "
               "created TEXT, chat_id TEXT DEFAULT 'legacy')")
    now = datetime.now(timezone.utc)
    for age_h, role, body in messages:
        db.execute("INSERT INTO messages(project, role, body, created) VALUES (?,?,?,?)",
                   (project, role, body, (now - timedelta(hours=age_h)).isoformat()))
    db.commit()
    db.close()


def ok_check(code):
    return {"ran": True, "ok": True, "error_count": 0}


def test_predict_prefers_recurring_standalone_coding_requests():
    requests = [DOOR, "thanks!", "and make it red too", LEADERBOARD,
                "Write a Roblox script for a leaderboard with leaderstats Coins and Wins for each player",
                "what is the capital of France", "Create a datastore module that saves player Coins safely"]
    found = presolve.predict(requests)
    assert found[0] in (LEADERBOARD, requests[4])                       # asked twice: first
    assert sum(presolve.similarity(f, LEADERBOARD) >= 0.6 for f in found) == 1   # near-duplicates kept once
    assert "thanks!" not in found and "and make it red too" not in found
    assert "what is the capital of France" not in found
    assert presolve.predict(requests, limit=2) == found[:2]


def test_project_files_named_in_a_request_rank_it_higher():
    requests = [DOOR, "Write a Roblox module script InventoryService that stores items per player"]
    assert presolve.predict(requests)[0] == DOOR                           # newest first
    assert presolve.predict(requests, files=("InventoryService.lua",))[0] == requests[1]


def test_recent_requests_reads_only_the_owners_recent_messages(tmp_path):
    home = tmp_path / "home"
    chats(home, [(100, "user", "very old request"), (2, "user", DOOR), (1, "assistant", "an answer"),
                 (0.5, "user", LEADERBOARD)])
    before = (home / "conversations.sqlite3").read_bytes()
    assert presolve.recent_requests(home, "STAR") == [LEADERBOARD, DOOR]
    assert presolve.recent_requests(home, "OTHER") == []
    assert (home / "conversations.sqlite3").read_bytes() == before        # read-only
    assert presolve.recent_requests(tmp_path / "nothing", "STAR") == []


def test_verify_needs_luau_that_passes_every_check():
    assert presolve.verify(GOOD, luau_check=ok_check, api_check=lambda c: [])[0] is True
    assert presolve.verify("Just words, no code.", luau_check=ok_check, api_check=lambda c: [])[0] is False
    assert presolve.verify("```lua\nprint(1)\n", luau_check=ok_check, api_check=lambda c: [])[0] is False   # cut off
    failed = presolve.verify(GOOD, luau_check=lambda c: {"ran": True, "ok": False, "error_count": 2},
                             api_check=lambda c: [])
    assert failed == (False, ["Luau check failed (2 errors)"])
    assert presolve.verify(GOOD, luau_check=ok_check, api_check=lambda c: ["Part.Colr"])[0] is False

    def down(code):
        raise OSError("knowledge down")
    assert presolve.verify(GOOD, luau_check=down, api_check=lambda c: [])[0] is False


def run(home, *, answers, idle_results, max_wait_s=3600.0):
    asked, idles = [], list(idle_results)

    async def ask(text):
        asked.append(text)
        return answers.get(text, GOOD)

    async def idle():
        return idles.pop(0) if idles else True

    async def no_sleep(_):
        return None
    ticks = iter(range(0, 10**6, 600))
    report = asyncio.run(presolve.run_night("STAR", home, ask=ask, idle=idle, luau_check=ok_check,
                                            api_check=lambda c: ["Bad.Name"] if "Bad" in c else [],
                                            sleep=no_sleep, clock=lambda: next(ticks), max_wait_s=max_wait_s))
    return report, asked


def test_night_run_stores_only_verified_answers_and_skips_known_ones(tmp_path):
    home = tmp_path / "home"
    chats(home, [(3, "user", DOOR), (2, "user", LEADERBOARD)])
    bad = "```lua\nlocal x = Bad.Name\n```\n"
    report, asked = run(home, answers={DOOR: bad}, idle_results=[False, True])
    assert report["predicted"] == 2 and report["asked"] == 2 and report["verified"] == 1
    assert report["rejected"] == ["1 unknown Roblox API names"]
    stored = presolve.Store(home).live("STAR")
    assert [row.request for row in stored] == [LEADERBOARD]
    again, asked_again = run(home, answers={DOOR: bad}, idle_results=[])
    assert asked_again == [DOOR]                                            # the stored one is not asked again


def test_night_run_waits_for_an_idle_server_and_gives_up(tmp_path):
    home = tmp_path / "home"
    chats(home, [(2, "user", LEADERBOARD)])
    report, asked = run(home, answers={}, idle_results=[False] * 50, max_wait_s=3000)
    assert asked == [] and report["stopped"] == "STAR Server was not idle"
    assert presolve.Store(home).live("STAR") == []


def test_take_matches_close_requests_marks_them_and_then_answers_fresh(tmp_path):
    home = tmp_path / "home"
    presolve.Store(home).put("STAR", LEADERBOARD, GOOD, ["Luau compile + type check passed (1 block)"])
    close = LEADERBOARD.replace("Write", "Please write")
    found = presolve.take(home, "STAR", "chat1", close)
    assert found is not None and found.answer == GOOD
    text = presolve.marked(found)
    assert text.startswith("**Pre-solved overnight**") and "Not run in Roblox Studio" in text and text.endswith(GOOD)
    assert presolve.take(home, "STAR", "chat1", close) is None                 # same request again: fresh
    assert presolve.take(home, "STAR", "chat1", close) is not None             # and after that, stored again
    assert presolve.take(home, "STAR", "chat2", DOOR) is None                  # unrelated request
    assert presolve.take(home, "OTHER", "chat3", LEADERBOARD) is None          # other project


def test_stored_answers_expire_and_are_capped(tmp_path):
    store = presolve.Store(tmp_path)
    old = datetime.now(timezone.utc) - timedelta(hours=presolve.KEEP_HOURS + 1)
    store.put("STAR", LEADERBOARD, GOOD, ["checked"], now=old)
    assert store.live("STAR") == [] and store.best("STAR", LEADERBOARD) is None
    for i in range(presolve.MAX_ROWS + 5):
        store.put("STAR", f"{LEADERBOARD} number {i}", GOOD, ["checked"])
    assert len(store.live("STAR")) == presolve.MAX_ROWS


def test_nightly_window_runs_once_per_night(tmp_path):
    night = datetime(2026, 10, 16, 3, 0)
    assert presolve.due(tmp_path, night) and not presolve.due(tmp_path, night.replace(hour=12))
    (tmp_path / "presolve-last-run.txt").write_text("2026-10-16", encoding="utf-8")
    assert not presolve.due(tmp_path, night) and presolve.due(tmp_path, night + timedelta(days=1))


def test_setting_is_off_by_default_and_must_be_a_boolean(tmp_path):
    file = tmp_path / "settings.json"
    assert core.Settings().presolve_enabled is False
    core.Settings(presolve_enabled=True).save(file)
    assert core.Settings.load(file).presolve_enabled is True
    try:
        core.Settings(presolve_enabled="yes").save(tmp_path / "bad.json")
    except ValueError as exc:
        assert "true or false" in str(exc)
    else:
        raise AssertionError("a non-boolean setting was saved")


def test_run_task_answers_from_the_store_only_when_switched_on(monkeypatch, tmp_path):
    home = tmp_path / "home"
    presolve.Store(home).put("STAR", LEADERBOARD, GOOD, ["Luau compile + type check passed (1 block)"])
    presolve._FRESH.clear()
    monkeypatch.setattr(core, "app_data", lambda: home)
    calls, events = [], []

    @asynccontextmanager
    async def model_client(settings, **kwargs):
        yield SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=None)))

    async def fake_execute(**kwargs):
        calls.append(kwargs["prompt"])
        return "fresh answer", [{"role": "assistant", "content": "fresh answer"}], []

    monkeypatch.setattr(core, "open_client", model_client)
    monkeypatch.setattr(core, "execute", fake_execute)
    settings = core.Settings(model="model", knowledge_endpoint="off", project="STAR")
    assert core.run_task(settings, LEADERBOARD, mode="fast", chat_id="c1") == "fresh answer"   # off: normal path
    settings.presolve_enabled = True
    stored = core.run_task(settings, LEADERBOARD, mode="fast", chat_id="c1", on_event=events.append)
    assert stored.startswith("**Pre-solved overnight**") and len(calls) == 1
    assert any(e.get("event") == "presolved_answer" for e in events)
    assert core.run_task(settings, LEADERBOARD, mode="fast", chat_id="c1") == "fresh answer"   # asked again: fresh
    assert len(calls) == 2


def test_idle_watch_needs_a_quiet_window_with_no_new_requests():
    state = {"busy": False, "task": 7}
    now = [0.0]

    async def fetch(path):
        if path == "/v1/models":
            return {"data": [{"id": "star-fast", "status": {"value": "loaded"}}, {"id": "off", "status": {"value": "unloaded"}}]}
        assert path == "/slots?model=star-fast"
        return [{"id": 0, "is_processing": state["busy"], "id_task": state["task"]}, {"id": 1, "id_task": 3}]

    watch = presolve.IdleWatch(fetch, quiet_s=600, clock=lambda: now[0])
    check = lambda: asyncio.run(watch())
    assert check() is False                     # first look: no history yet
    now[0] = 601
    assert check() is True                      # nothing changed for 10 minutes
    state["task"] = 8                           # somebody (night school) sent a request
    assert check() is False
    now[0] = 900
    assert check() is False
    now[0] = 1202
    assert check() is True
    state["busy"] = True
    assert check() is False

    async def broken(path):
        raise OSError("server down")
    assert asyncio.run(presolve.IdleWatch(broken, quiet_s=0)()) is False
