"""Field-lesson Roblox skill packs (Studio MCP workflow, replication, editable memory, uploads, multi-agent).

The lessons come from a large Studio port project and are written as ordinary bundled packs. They ship OFF until the
evaluation gate measures them, load through the real SkillLibrary, and their Luau examples pass the offline linter.
"""
import re
from urllib.parse import urlsplit

import pytest

from star import skill_packs
from star.agent_skills import SkillLibrary
from star.luau_lint import lint


CASES = (
    ("roblox-studio-mcp-workflow",
     "In Roblox Studio over MCP, how do I get a confirmed cloud save and stop agents deleting the map by accident?"),
    ("roblox-replication-hot-paths",
     "My Roblox game calls PivotTo and SetAttribute every frame and replication bandwidth is huge. How do I cut it?"),
    ("roblox-editable-memory-streaming",
     "In Roblox the second player's avatar fails because EditableMesh copies hit the memory budget. What should I do?"),
    ("roblox-asset-upload-moderation",
     "Before I upload Roblox textures, how do I avoid moderation for off-platform content like barcodes?"),
    ("roblox-multi-agent-studio",
     "Claude and Codex both edit one Roblox Studio place. How do we split claims and pick one integrator?"),
)
NAMES = tuple(name for name, _ in CASES)


@pytest.fixture(autouse=True)
def reset_pack_selection(monkeypatch):
    monkeypatch.delenv(skill_packs.ENV_VAR, raising=False)
    skill_packs.available.cache_clear()
    yield
    skill_packs.available.cache_clear()


def section(body, heading):
    return body.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def pack_named(name):
    return next(p for p in skill_packs.available() if p.name == name)


def test_lesson_packs_load_and_are_off_by_default():
    loaded = {pack.name for pack in skill_packs.available()}
    assert set(NAMES) <= set(skill_packs.TRIGGERS)
    assert set(NAMES) <= loaded
    assert set(NAMES).isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert set(NAMES).isdisjoint(skill_packs.enabled_names({}))
    assert set(NAMES) <= skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})


@pytest.mark.parametrize(("name", "prompt"), CASES)
def test_each_pack_is_chosen_for_its_own_topic_only_after_opt_in(monkeypatch, name, prompt):
    assert name not in skill_packs.matching_names(prompt)
    assert skill_packs.matching_names(prompt, enabled=set(NAMES)) == [name]
    monkeypatch.setenv(skill_packs.ENV_VAR, name)
    chosen = skill_packs.select(prompt)
    assert [pack.name for pack in chosen] == [name]
    assert skill_packs.render(chosen) == chosen[0].body + "\n"
    assert len(skill_packs.render(chosen)) <= skill_packs.MAX_BLOCK_CHARS
    monkeypatch.setenv(skill_packs.ENV_VAR, "off")
    assert skill_packs.select(prompt) == []


@pytest.mark.parametrize("name", NAMES)
def test_lesson_packs_stay_silent_outside_roblox(name):
    for prompt in ("How do two agents share a git repo with claims and a handoff?",
                   "How do I upload a photo without moderation problems on my blog?",
                   "My web app has memory budget problems with large images."):
        assert skill_packs.select(prompt, enabled={name}) == []


@pytest.mark.parametrize("name", NAMES)
def test_pack_schema_sources_and_bundled_loader(tmp_path, name):
    pack = pack_named(name)
    body = pack.body
    assert pack.file.parent.name == name and body.startswith(f"# {name}\n")
    assert 10 <= len(pack.description) <= 1024
    assert len(body) <= skill_packs.MAX_BODY_CHARS
    assert len(section(body, "When to use")) > 80
    assert re.findall(r"^(\d+)\. .+$", section(body, "Ten concrete rules"), re.M) == [str(i) for i in range(1, 11)]
    assert re.findall(r"^(\d+)\. .+$", section(body, "Three common mistakes"), re.M) == ["1", "2", "3"]
    assert len(re.findall(r"^### Example \d:", section(body, "Three correct Luau examples"), re.M)) == 3
    assert len(re.findall(r"^- \[ \] .+$", section(body, "Checklist"), re.M)) >= 5
    assert "[references/sources.md](references/sources.md)" in section(body, "Sources")
    lowered = body.lower()
    for forbidden in ("http://", "https://", "execute_luau", "publish", "api key", "password"):
        assert forbidden not in lowered, forbidden

    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    assert {s.name: s.source for s in library.catalog()}[name] == "bundled"
    assert library.load(name)["instructions"].strip() == body
    assert library.load(name)["references"] == ["references/sources.md"]
    sources = library.read_reference(name, "references/sources.md")["content"]
    assert sources.startswith(f"# Sources for {name}\n") and "2026-10-13" in sources
    assert "verified with the knowledge service /api-lookup on 2026-10-13" in sources

    labels = set(re.findall(r"^\| ([FS]\d+) \|", sources, re.M))
    cited = set(re.findall(r"\[([FS]\d+)\]", body))
    assert cited and cited <= labels, cited - labels
    assert any(label.startswith("F") for label in cited)
    links = re.findall(r"\b[a-z][a-z0-9+.-]*://[^\s|)]+", sources, re.I)
    assert len(links) >= 5 and len(links) == len(set(links))
    for link in links:
        parsed = urlsplit(link)
        assert parsed.scheme == "https" and parsed.hostname == "create.roblox.com"
        assert parsed.path.startswith("/docs/")


@pytest.mark.parametrize("name", NAMES)
def test_no_private_details_or_original_game_material(name):
    folder = pack_named(name).file.parent
    text = "\n".join(p.read_text(encoding="utf-8") for p in folder.rglob("*.md"))
    assert not re.search(r"\b\d{9,}\b", text)  # no place or asset ids
    assert not re.search(r"[A-Za-z]:\\Users\\", text) and not re.search(r"\b\w+@\w[\w.-]*\b", text)
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    for original in ("rec room", "recroom", "il2cpp", "libil2cpp", "global-metadata"):
        assert original not in text.lower(), original


@pytest.mark.parametrize("name", NAMES)
def test_each_luau_example_passes_the_offline_linter(name):
    examples = re.findall(r"^~~~luau\n(.*?)\n~~~$", pack_named(name).body, re.M | re.S)
    assert len(examples) == 3
    for example in examples:
        assert len(example) > 100
        assert lint(example) == []  # Only this heuristic checker; not luau-analyze or Studio.
