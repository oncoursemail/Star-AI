"""Roblox skill packs: format, grounding files, selection, cost limits and the run_task hook."""
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from star import desktop_core, doc_grounding, skill_packs
from star.agent_skills import SkillLibrary
from star.desktop_core import Settings, run_task

NAMES = ["roblox-ui-layout", "roblox-secure-remotes", "roblox-datastore-safety",
         "roblox-animation-tools", "roblox-performance-streaming",
         "roblox-animation-craft", "roblox-vfx", "roblox-building-layout", "roblox-ui-styles",
         "game-obby", "game-tycoon", "game-simulator", "game-rounds",
         "game-inventory", "game-npc-quests",
         "eng-debugging", "eng-test-first", "eng-verify-before-done"]
ENGINEERING = {"eng-debugging", "eng-test-first", "eng-verify-before-done"}
UI_PROMPT = "In my Roblox game: write a LocalScript that builds a ScreenGui with a ScrollingFrame and a UIListLayout."
REMOTE_PROMPT = "In my Roblox game, my RemoteEvent handler trusts the client price. Make the server validate it."


def test_all_packs_ship_in_the_existing_skill_format():
    packs = skill_packs.available()
    assert [p.name for p in packs] == NAMES
    for pack in packs:
        assert pack.file.parent.name == pack.name and 1 <= len(pack.description) <= 1024
        assert pack.body.startswith("# ")
        grounding = "ATTRIBUTION.md" if pack.name in ENGINEERING else "sources.md"
        assert (pack.file.parent / "references" / grounding).is_file(), pack.name


def test_each_pack_is_short_enough_not_to_slow_the_first_token():
    for pack in skill_packs.available():
        assert len(pack.body) <= skill_packs.MAX_BODY_CHARS, (pack.name, len(pack.body))
    worst = skill_packs.render(skill_packs.available()[:skill_packs.MAX_PACKS_PER_TURN])
    assert len(worst) <= skill_packs.MAX_BLOCK_CHARS


def test_every_pack_cites_official_documentation_and_lists_the_api_names_it_checked():
    for pack in skill_packs.available():
        if pack.name in ENGINEERING:
            continue
        sources = (pack.file.parent / "references" / "sources.md").read_text(encoding="utf-8")
        assert sources.count("https://create.roblox.com/docs/") >= 5, pack.name
        assert "verified with the knowledge service /api-lookup" in sources, pack.name
        assert "http://" not in sources and "10.17" not in sources


def test_packs_do_not_contain_instructions_that_reach_beyond_the_task():
    for pack in skill_packs.available():
        text = pack.body.lower()
        for forbidden in ("ignore previous", "system prompt", "api key", "http://", "https://", "execute_luau", "publish"):
            assert forbidden not in text, (pack.name, forbidden)


def test_selection_needs_a_roblox_question_that_names_the_topic():
    assert skill_packs.matching_names(UI_PROMPT, enabled=NAMES) == ["roblox-ui-layout"]
    assert skill_packs.matching_names(REMOTE_PROMPT, enabled=NAMES) == ["roblox-secure-remotes"]
    for prompt in ("How do I centre a div in my web app UI?", "What is the capital of France?", "hello",
                   "Explain the UI of a spreadsheet", "", "   "):
        assert skill_packs.select(prompt, enabled=NAMES) == [], prompt
    assert skill_packs.select(None, enabled=NAMES) == []
    assert skill_packs.select("x" * 30_000 + " Roblox ScreenGui", enabled=NAMES) == []


def test_one_generic_word_is_not_enough():
    assert skill_packs.select("In my Roblox game the UI looks plain.", enabled=NAMES) == []
    assert skill_packs.select("In my Roblox game a Tool appears.", enabled=NAMES) == []


def test_only_the_best_matching_pack_is_added():
    prompt = ("In my Roblox game: RemoteEvent OnServerEvent FireServer validation, DataStore UpdateAsync BindToClose, "
              "ScreenGui UIListLayout, Animator LoadAnimation, performance StreamingEnabled.")
    picked = skill_packs.select(prompt, enabled=NAMES)
    assert len(picked) == skill_packs.MAX_PACKS_PER_TURN == 1
    assert len(skill_packs.select(prompt, enabled=NAMES, limit=3)) == 3 and skill_packs.select(prompt, enabled=NAMES, limit=3)[0] == picked[0]
    assert skill_packs.select(prompt, enabled=NAMES, limit=0) == []


def test_environment_switch(monkeypatch):
    monkeypatch.delenv(skill_packs.ENV_VAR, raising=False)
    assert skill_packs.enabled_names() == frozenset(skill_packs.DEFAULT_ENABLED) & frozenset(NAMES)
    for value, expected in (("off", set()), ("none", set()), ("0", set()), ("all", set(NAMES)),
                            ("roblox-ui-layout", {"roblox-ui-layout"}),
                            ("roblox-ui-layout, roblox-secure-remotes ,nonsense", {"roblox-ui-layout", "roblox-secure-remotes"}),
                            ("nonsense", set())):
        monkeypatch.setenv(skill_packs.ENV_VAR, value)
        assert skill_packs.enabled_names() == expected, value
        assert {p.name for p in skill_packs.select(UI_PROMPT + " " + REMOTE_PROMPT)} <= expected
    monkeypatch.setenv(skill_packs.ENV_VAR, "off")
    assert skill_packs.select(UI_PROMPT) == []


def test_render_is_empty_without_packs_and_bounded():
    assert skill_packs.render([]) == ""
    long = skill_packs.Pack("x", "d", "y" * 10_000, Path("."))
    assert len(skill_packs.render([long])) <= skill_packs.MAX_BLOCK_CHARS + 1


def test_the_skill_library_lists_bundled_packs_and_a_user_copy_wins(tmp_path):
    lib = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    by_name = {s.name: s for s in lib.catalog()}
    assert set(NAMES) <= set(by_name) and by_name["roblox-ui-layout"].source == "bundled"
    loaded = lib.load("roblox-secure-remotes")
    assert "server is authoritative" in loaded["instructions"] and "references/sources.md" in loaded["references"]
    own = tmp_path / "skills" / "roblox-ui-layout"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("---\nname: roblox-ui-layout\ndescription: mine\n---\n# mine\n", encoding="utf-8")
    assert {s.name: s for s in lib.catalog()}["roblox-ui-layout"].source == "personal"
    assert not set(NAMES) & {s.name for s in SkillLibrary(workspace=None, home=tmp_path / "elsewhere").catalog()}   # only when asked for


class FakeModel:
    def __init__(self):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK", tool_calls=None))])


def run_turn(monkeypatch, tmp_path, prompt, mode="auto"):
    model = FakeModel()

    @asynccontextmanager
    async def fake_client(settings, **_):
        yield model

    monkeypatch.setattr(desktop_core, "app_data", lambda: tmp_path / "STAR")
    monkeypatch.setattr(desktop_core, "open_client", fake_client)
    monkeypatch.setattr(doc_grounding, "client_for", lambda settings: None)
    events = []
    run_task(Settings(model="m"), prompt, on_event=events.append, mode=mode)
    messages = model.requests[0]["messages"]
    final = messages[-1]["content"]
    text = final if isinstance(final, str) else "".join(p.get("text", "") for p in final if isinstance(p, dict))
    return messages, text, events


def test_run_task_adds_the_pack_after_the_users_words_and_never_to_the_system_message(monkeypatch, tmp_path):
    monkeypatch.setenv(skill_packs.ENV_VAR, "all")
    messages, text, events = run_turn(monkeypatch, tmp_path, UI_PROMPT)
    assert text.startswith(UI_PROMPT) and skill_packs.BLOCK_HEADING in text and "Build UI from real objects" in text
    assert "Build UI from real objects" not in messages[0]["content"]
    event = next(e for e in events if e["event"] == "skill_packs")
    assert event["names"] == ["roblox-ui-layout"] and event["chars"] > 500


def test_run_task_without_packs_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv(skill_packs.ENV_VAR, "off")
    messages, text, events = run_turn(monkeypatch, tmp_path, UI_PROMPT)
    assert skill_packs.BLOCK_HEADING not in text and not any(e["event"] == "skill_packs" for e in events)
    other_messages, other_text, other_events = run_turn(monkeypatch, tmp_path, "What is the capital of France?")
    assert skill_packs.BLOCK_HEADING not in other_text
    # the system message is identical whether or not a pack was added (the server's prompt cache depends on it)
    monkeypatch.setenv(skill_packs.ENV_VAR, "all")
    on_messages, _, _ = run_turn(monkeypatch, tmp_path, UI_PROMPT)
    assert on_messages[0] == messages[0]


def test_quick_chat_mode_never_gets_a_pack(monkeypatch, tmp_path):
    monkeypatch.setenv(skill_packs.ENV_VAR, "all")
    _, text, events = run_turn(monkeypatch, tmp_path, UI_PROMPT, mode="fast")
    assert skill_packs.BLOCK_HEADING not in text and not any(e["event"] == "skill_packs" for e in events)


def test_engineering_packs_keep_the_attribution_and_licence_of_the_two_mit_collections():
    notices = (skill_packs.PACKS_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Copyright (c) 2025 Addy Osmani" in notices and "Copyright (c) 2025 Jesse Vincent" in notices
    assert notices.count("Permission is hereby granted, free of charge") == 2
    for name in ENGINEERING:
        text = (skill_packs.PACKS_DIR / name / "references" / "ATTRIBUTION.md").read_text(encoding="utf-8")
        assert "MIT" in text and "github.com/addyosmani/agent-skills" in text and "github.com/obra/superpowers" in text, name
        assert "THIRD_PARTY_NOTICES.md" in text


def test_the_creation_packs_are_chosen_for_their_own_topic():
    assert skill_packs.matching_names("In my Roblox game: write easing functions with anticipation and follow-through for a sword combo.",
                                      enabled=NAMES) == ["roblox-animation-craft"]
    assert skill_packs.matching_names("In my Roblox game: spawn a ParticleEmitter burst with a Beam and a Trail on hit.",
                                      enabled=NAMES) == ["roblox-vfx"]
    assert skill_packs.matching_names("In my Roblox game: snap the modular kit walls to a grid and place the model with PivotTo.",
                                      enabled=NAMES) == ["roblox-building-layout"]
    assert skill_packs.matching_names("In my Roblox game: debug this script, it errors and crashes with attempt to index nil.",
                                      enabled=NAMES) == ["eng-debugging"]
    assert skill_packs.matching_names("In my Roblox game: fix this and tell me how you verified it works.",
                                      enabled=NAMES) == ["eng-verify-before-done"]


def test_the_new_packs_are_off_until_the_gate_has_passed_them():
    assert "roblox-vfx" in skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})
    assert skill_packs.enabled_names({}) == frozenset(skill_packs.DEFAULT_ENABLED) & frozenset(NAMES)

GAME_PACKS = ("game-obby", "game-tycoon", "game-simulator",
              "game-rounds", "game-inventory", "game-npc-quests")


def test_new_game_packs_are_registered_but_switched_off_pending_evaluation():
    # Keep each new pack available for opt-in testing, but never enable it by default
    # until docs/evals.md's evaluation gate has passed it.
    assert set(GAME_PACKS) <= {pack.name for pack in skill_packs.available()}
    assert set(GAME_PACKS).isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert set(GAME_PACKS).isdisjoint(skill_packs.enabled_names({}))
    assert set(GAME_PACKS) <= skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})
    for name in GAME_PACKS:
        assert skill_packs.enabled_names({skill_packs.ENV_VAR: name}) == {name}


@pytest.mark.parametrize(("name", "prompt"), (
    ("game-obby", "Build a Roblox obby with checkpoints and kill bricks."),
    ("game-tycoon", "Build a Roblox tycoon with droppers and collectors."),
    ("game-simulator", "Build a Roblox simulator with rebirth and leaderstats."),
    ("game-rounds", "Build a Roblox round-based game with intermission."),
    ("game-inventory", "Build a Roblox inventory with equip and backpack."),
    ("game-npc-quests", "Build Roblox NPC quests with quest dialogue."),
))
def test_new_game_pack_routing_requires_explicit_opt_in(name, prompt):
    assert skill_packs.matching_names(prompt) == [] or name not in skill_packs.matching_names(prompt)
    assert skill_packs.matching_names(prompt, enabled={name}) == [name]
