"""Opt-in Roblox gameplay and platform skill packs: schema, typed examples, routing and source grounding.

These packs carry three --!strict Luau examples each. The checks here are offline: STAR's own linter (default and
server-security rules), a structural schema, and a grounding rule that every service fetched with GetService and
every class created with Instance.new in an example is linked to its official reference page in sources.md.
They do not prove the examples run in Studio.
"""
import re
from urllib.parse import urlsplit

import pytest

from star import skill_packs
from star.agent_skills import SkillLibrary
from star.luau_lint import lint

CASES = (
    ("roblox-combat-hitboxes",
     "In my Roblox game, build a melee hitbox with GetPartBoundsInBox and validate the hitscan damage on the server."),
    ("roblox-pathfinding-npc",
     "In my Roblox game, make an NPC chase the player with PathfindingService, ComputeAsync and GetWaypoints."),
    ("roblox-physics-constraints",
     "In my Roblox game, replace BodyVelocity with LinearVelocity and AlignOrientation for a knockback."),
    ("roblox-collection-tags",
     "In my Roblox game, use CollectionService GetTagged and GetInstanceAddedSignal for every tagged lava part."),
    ("roblox-input-devices",
     "In my Roblox game, bind a sprint action with ContextActionService that works on gamepad, touch and keyboard."),
    ("roblox-sound-design",
     "In my Roblox game, play footsteps and music through SoundService with a SoundGroup for the volume settings."),
    ("roblox-luau-specs",
     "In my Roblox game, write TestEZ specs with describe and expect for my inventory ModuleScript."),
    ("roblox-marketplace-purchases",
     "In my Roblox game, handle a developer product with MarketplaceService ProcessReceipt and a game pass check."),
    ("roblox-teleport-matchmaking",
     "In my Roblox game, teleport a party from the lobby to a reserved server with TeleportService TeleportAsync."),
    ("roblox-open-cloud",
     "In my Roblox game, receive Open Cloud messages with MessagingService SubscribeAsync from an external tool."),
)
NAMES = tuple(name for name, _ in CASES)
PROMPTS = dict(CASES)


@pytest.fixture(autouse=True)
def reset_pack_selection(monkeypatch):
    monkeypatch.delenv(skill_packs.ENV_VAR, raising=False)
    skill_packs.available.cache_clear()
    yield
    skill_packs.available.cache_clear()


def pack(name):
    return next(p for p in skill_packs.available() if p.name == name)


def section(body, heading):
    return body.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def examples(body):
    return re.findall(r"^~~~luau\n(.*?)\n~~~$", body, re.M | re.S)


def sources_of(name):
    return (pack(name).file.parent / "references" / "sources.md").read_text(encoding="utf-8")


def test_packs_ship_registered_and_are_off_by_default():
    assert set(NAMES) <= set(skill_packs.TRIGGERS)
    assert set(NAMES) <= {p.name for p in skill_packs.available()}
    assert set(NAMES).isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert set(NAMES).isdisjoint(skill_packs.enabled_names({}))
    assert set(NAMES) <= skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})


@pytest.mark.parametrize(("name", "prompt"), CASES)
def test_each_pack_routes_only_after_opt_in_and_wins_its_own_prompt(monkeypatch, name, prompt):
    assert name not in skill_packs.matching_names(prompt)
    monkeypatch.setenv(skill_packs.ENV_VAR, name)
    chosen = skill_packs.select(prompt)
    assert [p.name for p in chosen] == [name]
    assert skill_packs.render(chosen) == chosen[0].body + "\n"
    # With every shipped pack switched on, the pack still wins the prompt written for it.
    assert skill_packs.matching_names(prompt, enabled=[p.name for p in skill_packs.available()]) == [name]
    monkeypatch.setenv(skill_packs.ENV_VAR, "off")
    assert skill_packs.select(prompt) == []


@pytest.mark.parametrize("name", NAMES)
def test_pack_schema_and_bundled_loader(tmp_path, name):
    body = pack(name).body
    assert body.startswith(f"# {name}\n")
    assert 10 <= len(pack(name).description) <= 1024
    assert len(body) <= skill_packs.MAX_BODY_CHARS
    assert len(section(body, "When to use")) > 80
    assert re.findall(r"^(\d+)\. .+$", section(body, "Ten concrete rules"), re.M) == [str(i) for i in range(1, 11)]
    assert re.findall(r"^(\d+)\. .+$", section(body, "Three common mistakes"), re.M) == ["1", "2", "3"]
    assert len(re.findall(r"^### Example \d:", section(body, "Three correct Luau examples"), re.M)) == 3
    assert len(re.findall(r"^- \[ \] .+$", section(body, "Checklist"), re.M)) >= 5
    assert "[references/sources.md](references/sources.md)" in section(body, "Sources")
    files = {p.relative_to(pack(name).file.parent).as_posix() for p in pack(name).file.parent.rglob("*") if p.is_file()}
    assert files == {"SKILL.md", "references/sources.md"}
    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    assert {s.name: s.source for s in library.catalog()}[name] == "bundled"
    assert library.load(name)["instructions"].strip() == body
    assert library.load(name)["references"] == ["references/sources.md"]


@pytest.mark.parametrize("name", NAMES)
def test_every_example_is_strict_luau_and_passes_the_offline_linter(name):
    found = examples(pack(name).body)
    assert len(found) == 3
    for example in found:
        assert example.startswith("--!strict\n") and len(example) > 200
        assert lint(example) == []
        assert lint(example, server_security=True) == []
        # Old patterns the packs teach against must not appear in their own examples.
        for banned in ("wait(", "spawn(", "delay(", "Humanoid:LoadAnimation", "game.Players", "game.Workspace",
                       "BodyVelocity", "BodyPosition", "BodyGyro", "FindPartOnRay", ":connect("):
            assert banned not in example.replace("task.wait(", "").replace("task.spawn(", "").replace("task.delay(", ""), (
                name, banned)


@pytest.mark.parametrize("name", NAMES)
def test_sources_are_official_unique_and_cover_every_cited_id(name):
    sources = sources_of(name)
    assert sources.startswith(f"# Sources for {name}\n")
    assert "2026-10-13" in sources and "Full API dump" in sources and "have not run in a live" in sources
    assert "verified with the knowledge service /api-lookup" not in sources
    links = re.findall(r"\b[a-z][a-z0-9+.-]*://[^\s|)]+", sources, re.I)
    assert len(links) >= 5 and len(links) == len(set(links))
    for link in links:
        parsed = urlsplit(link)
        assert parsed.scheme == "https" and parsed.hostname == "create.roblox.com"
        assert parsed.path.startswith("/docs/") and parsed.username is None
    ids = set(re.findall(r"^\| (S\d+) \|", sources, re.M))
    cited = set(re.findall(r"\bS\d+\b", pack(name).body))
    assert cited and cited <= ids


@pytest.mark.parametrize("name", NAMES)
def test_every_service_and_created_class_in_the_examples_is_linked_to_its_reference_page(name):
    sources = sources_of(name)
    code = "\n".join(examples(pack(name).body))
    used = set(re.findall(r'GetService\("(\w+)"\)', code)) | set(re.findall(r'Instance\.new\("(\w+)"\)', code))
    missing = sorted(c for c in used if f"https://create.roblox.com/docs/reference/engine/classes/{c} " not in sources
                     and f"https://create.roblox.com/docs/reference/engine/classes/{c}\n" not in sources)
    assert not missing, (name, missing)


def test_the_packs_do_not_take_unrelated_or_non_roblox_prompts():
    every = [p.name for p in skill_packs.available()]
    for prompt in ("How do I add sound to my React web app?", "Write pytest specs for my Flask API",
                   "Teleport my Unity character to a spawn point", "What is the capital of France?"):
        assert not set(skill_packs.matching_names(prompt, enabled=every)) & set(NAMES), prompt
