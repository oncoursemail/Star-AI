"""Model routing, the learning loop and documentation grounding in the same turn.

Each feature has its own test file. These tests pin what must hold once all three are in one
tree: per-turn text (documentation first, then lessons) travels in the final user turn and
never in the system message; the model a turn is routed to on a STAR Server gets the same
lessons within their budget; a role the owner set by hand is used as set; and the background
summary of raw notes never replaces the cached conversation of a model the chat is routed to.
"""
import json
from types import SimpleNamespace

import pytest

import star.desktop_core as core
import star.doc_grounding as doc_grounding
import star.lesson_digest as digest
import star.providers as providers
from star import lessons as L
from star import server_roles, turn_memory
from star.desktop_core import Conversations, Settings, run_task
from star.doc_grounding import REFERENCE_CLOSE, REFERENCE_OPEN
from star.lessons import LessonStore
from star.providers import llama_request_fields, remember_server_limits

LAN = "http://192.168.1.20:8080/v1"
KEY = "test-server-key-0123456789"
# The `data` array of /v1/models as a llama.cpp router with a fleet reports it.
FLEET = [
    {"id": "star-fast", "aliases": ["star-code", "star-vision"], "status": {"value": "loaded"},
     "architecture": {"input_modalities": ["text", "image"]}},
    {"id": "star-voice", "aliases": ["star-quick"], "status": {"value": "loaded"},
     "architecture": {"input_modalities": ["text"]}},
]
ROBLOX_QUESTION = "How do I tween a part with TweenService in Roblox?"
PLAIN_QUESTION = "hello there, how are you today?"
LESSON = "Always name RemoteEvents with the prefix RE_ in this project."


@pytest.fixture(autouse=True)
def clean_process_memory():
    def clear():
        server_roles.forget()
        turn_memory.forget()
        providers._SERVER_LIMITS.clear()
        providers._MODEL_NAMES.clear()
        providers._SLOT_TABLE.clear()
    clear()
    yield
    clear()


def reply(content, model=None):
    return SimpleNamespace(model=model, choices=[SimpleNamespace(message=SimpleNamespace(content=content,
                                                                                         tool_calls=None))])


class Models:
    def __init__(self):
        self.responses, self.requests = [], []

    async def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return self.responses.pop(0)


class Client:
    def __init__(self, models):
        self.chat = SimpleNamespace(completions=models)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class Docs:
    """Stands in for the documentation service: two passages for any search, checks pass."""

    def search(self, query, *, top=4, mode="vector"):
        return [{"rank": n, "title": f"Title {n}", "heading": f"Title {n} > Section", "kind": "guide",
                 "url": f"https://create.roblox.com/docs/page{n}", "source": "creator-docs", "path": f"p{n}.md",
                 "commit": "af5f853c78b58c4e", "licence": "CC-BY-4.0",
                 "retrieved_at": "2026-10-10T20:00:00+00:00",
                 "text": "Tween a part with TweenService:Create."} for n in (1, 2)][:top]

    def api_lookup(self, symbols):
        return [{"symbol": s, "found": False} for s in symbols]

    def luau_check(self, code, *, strict=False):
        return {"ran": True, "ok": True, "errors": [], "error_count": 0, "executed": False}


def server(**fields) -> Settings:
    """STAR Server selected, its model list already read, role fields blank unless given."""
    server_roles.remember_models(LAN, FLEET)
    return Settings(**{"provider": "star_server", "server_endpoint": LAN, "model": "star-fast", **fields})


def text_of(message) -> str:
    content = message.get("content") or ""
    return content if isinstance(content, str) else "".join(part.get("text", "") for part in content)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("STAR_SERVER_API_KEY", KEY)
    models = Models()
    monkeypatch.setattr(core, "open_client", lambda settings, **_: Client(models))
    monkeypatch.setattr(doc_grounding, "client_for", lambda settings: Docs())
    home = core.app_data()
    home.mkdir(parents=True, exist_ok=True)
    chats = Conversations(home / "conversations.sqlite3")

    def teach(project, *texts):
        store = LessonStore(home)
        try:
            for number, text in enumerate(texts):
                assert store.capture_owner(project=project, kind="preference", text=text, message=text,
                                           source=f"chat:c#{number}").status == "accepted"
        finally:
            store.close()

    def turn(settings, text, answered_by):
        chat = chats.active_chat(settings.project)
        chats.add(settings.project, "user", text, chat_id=chat)
        models.responses.append(reply("Done.", model=answered_by))
        result = run_task(settings, text, chat_id=chat, mode="fast")
        chats.add(settings.project, "assistant", result, chat_id=chat)
        return models.requests[-1]

    yield SimpleNamespace(models=models, home=home, chats=chats, teach=teach, turn=turn)
    chats.close()


def test_documentation_then_lessons_travel_in_the_final_user_turn_and_the_system_message_does_not_change(desk):
    desk.teach("WithLessons", LESSON)
    taught = desk.turn(server(project="WithLessons"), ROBLOX_QUESTION, "star-fast")
    plain = desk.turn(server(project="NoLessons"), ROBLOX_QUESTION, "star-fast")

    # A Roblox question in Fast mode goes to the code model on a STAR Server, in both projects.
    assert taught["model"] == plain["model"] == "star-fast"
    # The system message is the same bytes with and without a lesson, and carries neither block.
    assert taught["messages"][0] == plain["messages"][0] and taught["messages"][0]["role"] == "system"
    system = text_of(taught["messages"][0])
    assert LESSON not in system and L.LESSONS_HEADING not in system and REFERENCE_OPEN not in system

    final = text_of(taught["messages"][-1])
    assert final.startswith(ROBLOX_QUESTION)
    # Documentation first, with its own markers and budget; the lessons after it, complete.
    assert final.count(REFERENCE_OPEN) == 1 and final.count(REFERENCE_CLOSE) == 1
    assert final.index(REFERENCE_OPEN) < final.index(REFERENCE_CLOSE) < final.index(L.LESSONS_HEADING)
    assert "[2] Title 2 > Section" in final and final.count(LESSON) == 1
    # The other project gets the same passages and no lesson.
    other = text_of(plain["messages"][-1])
    assert other.count(REFERENCE_OPEN) == 1 and LESSON not in other and L.LESSONS_HEADING not in other


def test_plain_chat_goes_to_the_quick_model_with_the_lessons_inside_their_budget(desk):
    lessons = [f"Always keep rule number {number} in mind: " + f"detail{number} " * 14 for number in range(1, 7)]
    desk.teach("P", *lessons)
    request = desk.turn(server(project="P"), PLAIN_QUESTION, "star-voice")

    assert request["model"] == "star-voice"            # the server's quick model answers plain chat
    final = text_of(request["messages"][-1])
    assert final.startswith(PLAIN_QUESTION) and L.LESSONS_HEADING in final
    lines = [line for line in final.splitlines() if line.startswith("[#")]
    limit, budget = L.RECALL_QUICK
    assert 1 <= len(lines) <= limit and sum(len(line) for line in lines) <= budget
    assert not any(text in text_of(request["messages"][0]) for text in lessons)


def test_a_model_the_owner_set_by_hand_answers_instead_of_the_servers_quick_model(desk):
    desk.teach("P", LESSON)
    request = desk.turn(server(project="P", fast_model="my-quick"), PLAIN_QUESTION, "my-quick")
    assert request["model"] == "my-quick" and LESSON in text_of(request["messages"][-1])


# --- the background summary of raw notes on a STAR Server that routes chat to a fleet ---------

SUMMARY = json.dumps({"lessons": [{"from": [1], "kind": "preference", "text": "The owner wants the Buy button blue."}]})


def raw_notes(home, project="P"):
    store = LessonStore(home)
    try:
        for number, text in enumerate(["No, make it blue", "No, make it wider", "No, make it bold"]):
            store.capture_inferred(project=project, kind="correction", source_type="chat-correction",
                                   source=f"chat:c#{number}", text=text, evidence="Follows STAR's answer")
    finally:
        store.close()


def summarise(settings, home, *, minimum):
    models = Models()
    models.responses = [reply(SUMMARY)]
    report = digest.digest_once(settings, home, settings.project, minimum=minimum,
                                open_model=lambda settings, **_: Client(models))
    return report, models


def test_the_automatic_summary_does_not_replace_the_cache_of_the_routed_quick_model(tmp_path):
    """Plain chat is routed to the server's quick model, which `star-quick` is another name of.
    The summary that follows the warm-up may use that model only in the slot next to the chat's."""
    raw_notes(tmp_path)
    settings = server(project="P")
    assert digest.chat_models(settings) >= {"star-fast", "star-voice"}

    # Slot count unknown, then a single slot: nothing protects the chat's cached conversation.
    for slots in (None, 1):
        if slots:
            remember_server_limits(LAN, "star-voice", 16384, slots)
        report, models = summarise(settings, tmp_path, minimum=3)
        assert report["skipped"] == "no_spare_model" and models.requests == []

    # Two slots: the chat keeps its slot (primed by the warm-up) and the summary takes the other one.
    remember_server_limits(LAN, "star-voice", 16384, 2)
    chats = Conversations(tmp_path / "conversations.sqlite3")
    try:
        conversation = core.memory_scope_for(settings, chats.active_chat("P"))
    finally:
        chats.close()
    own = llama_request_fields(settings, conversation=conversation, model="star-voice", prime=True)["id_slot"]
    report, models = summarise(settings, tmp_path, minimum=3)
    assert report["created"] == 1 and report["model"] == "star-quick" and "shared_model" not in report
    assert [request["extra_body"]["id_slot"] for request in models.requests] == [1 - own]
    assert llama_request_fields(settings, conversation=conversation, model="star-voice")["id_slot"] == own


def test_the_summary_follows_the_roles_the_owner_set_and_says_when_it_shared_the_chat_model(tmp_path):
    raw_notes(tmp_path)
    # The owner chose another quick model: the server's small model is spare, whatever its slots.
    by_hand = server(project="P", fast_model="my-quick")
    assert "star-voice" not in digest.chat_models(by_hand)
    report, models = summarise(by_hand, tmp_path, minimum=3)
    assert report["created"] == 1 and report["model"] == "star-quick" and "shared_model" not in report

    # Asked for by the owner on a server whose quick model has one slot: it runs, and the report
    # says the chat's model was used (the bridge then primes the chat's cache again).
    raw_notes(tmp_path, "Q")
    routed = server(project="Q")
    remember_server_limits(LAN, "star-voice", 16384, 1)
    report, models = summarise(routed, tmp_path, minimum=1)
    assert report["created"] == 1 and report["model"] == "star-quick" and report["shared_model"] is True
