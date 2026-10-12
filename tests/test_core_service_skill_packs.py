"""Source-grounded, opt-in Roblox service skill packs and example-code lint contracts."""
import re
from urllib.parse import urlsplit

import pytest

from star import skill_packs
from star.agent_skills import SkillLibrary
from star.luau_lint import lint


CASES = (
    ("roblox-datastore-service-patterns",
     "In Roblox Studio, explain DataStoreService UpdateAsync and StandardRead request budgets."),
    ("roblox-remote-event-function-patterns",
     "In Roblox Studio, build a RemoteFunction OnServerInvoke with per-player validation."),
    ("roblox-tweenservice-easing",
     "In Roblox Studio, implement TweenService with TweenInfo and EasingDirection."),
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


def test_packs_exist_but_are_all_off_by_default():
    assert set(NAMES) <= set(skill_packs.TRIGGERS)
    assert set(NAMES) <= {pack.name for pack in skill_packs.available()}
    assert set(NAMES).isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert set(NAMES).isdisjoint(skill_packs.enabled_names({}))
    assert set(NAMES) <= skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: ", ".join(NAMES)}) == set(NAMES)


@pytest.mark.parametrize(("name", "prompt"), CASES)
def test_real_selector_and_renderer_respect_explicit_opt_in(monkeypatch, name, prompt):
    assert name not in skill_packs.matching_names(prompt)
    monkeypatch.setenv(skill_packs.ENV_VAR, name)
    assert skill_packs.enabled_names() == {name}
    chosen = skill_packs.select(prompt)
    assert [pack.name for pack in chosen] == [name]
    assert skill_packs.matching_names(prompt) == [name]
    assert skill_packs.render(chosen) == chosen[0].body + "\n"
    assert len(chosen[0].body) <= skill_packs.MAX_BODY_CHARS
    assert len(skill_packs.render(chosen)) <= skill_packs.MAX_BLOCK_CHARS
    monkeypatch.setenv(skill_packs.ENV_VAR, "off")
    assert skill_packs.select(prompt) == []
    assert skill_packs.render(skill_packs.select(prompt)) == ""


@pytest.mark.parametrize("name", NAMES)
def test_pack_schema_examples_mistakes_and_its_actual_bundled_loader(tmp_path, name):
    pack = next(p for p in skill_packs.available() if p.name == name)
    assert pack.file.parent.name == name
    assert pack.body.startswith(f"# {name}\n")
    assert 10 <= len(pack.description) <= 1024
    assert len(section(pack.body, "When to use")) > 80
    assert re.findall(r"^(\d+)\. .+$", section(pack.body, "Ten concrete rules"), re.M) == [
        str(i) for i in range(1, 11)]
    assert re.findall(r"^(\d+)\. .+$", section(pack.body, "Three common mistakes"), re.M) == [
        "1", "2", "3"]
    assert len(re.findall(r"^### Example \d:", section(pack.body, "Three correct Luau examples"), re.M)) == 3
    assert len(re.findall(r"^- \[ \] .+$", section(pack.body, "Checklist"), re.M)) >= 5
    assert "[references/sources.md](references/sources.md)" in section(pack.body, "Sources")
    assert {p.relative_to(pack.file.parent).as_posix() for p in pack.file.parent.rglob("*")
            if p.is_file()} == {"SKILL.md", "references/sources.md"}

    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    assert {s.name: s.source for s in library.catalog()}[name] == "bundled"
    assert library.load(name)["instructions"].strip() == pack.body
    assert library.load(name)["references"] == ["references/sources.md"]
    sources = library.read_reference(name, "references/sources.md")["content"]
    assert sources.startswith(f"# Sources for {name}\n")
    assert "2026-10-12" in sources and "studio" in sources.lower()
    assert "verified with the knowledge service /api-lookup" not in sources.lower()

    links = re.findall(r"\b[a-z][a-z0-9+.-]*://[^\s|)]+", sources, re.I)
    assert len(links) >= 4
    assert len(links) == len(set(links))
    for link in links:
        parsed = urlsplit(link)
        assert parsed.scheme == "https"
        assert parsed.hostname == "create.roblox.com"
        assert parsed.path.startswith("/docs/")
        assert parsed.username is None and parsed.password is None
    ids = set(re.findall(r"^\| (S\d+) \|", sources, re.M))
    assert len(ids) >= 4
    assert set(re.findall(r"\bS\d+\b", pack.body)) <= ids


@pytest.mark.parametrize("name", NAMES)
def test_each_of_nine_luau_examples_passes_the_existing_offline_linter(name):
    pack = next(p for p in skill_packs.available() if p.name == name)
    examples = re.findall(r"^~~~luau\n(.*?)\n~~~$", pack.body, re.M | re.S)
    assert len(examples) == 3
    for example in examples:
        assert len(example) > 100
        assert lint(example) == []  # Only this heuristic checker; not luau-analyze or Studio.


@pytest.mark.parametrize(("expected_rule", "bad_source"), (
    ("datastore-unprotected", 'local result = store:GetAsync("Key")'),
    ("remote-unvalidated", 'remote.OnServerEvent:Connect(function(player, amount) coins.Value += amount end)'),
    ("deprecated-task-global", "wait(1)"),
))
def test_linter_control_cases_detect_known_mistakes(expected_rule, bad_source):
    assert expected_rule in {finding.rule_id for finding in lint(bad_source)}


@pytest.mark.parametrize("prompt", (
    None, "", "   ", [], "Roblox " + "TweenInfo " * 3000,
    "Show TweenInfo easing for my CSS website",
    "How do I configure React RemoteFunctions?",
))
def test_empty_malformed_non_roblox_and_oversized_prompts_are_not_selected(prompt):
    assert skill_packs.select(prompt, enabled=NAMES) == []


def test_malformed_pack_is_skipped_by_real_inventory(tmp_path, monkeypatch):
    folder = tmp_path / NAMES[0]
    folder.mkdir()
    (folder / "SKILL.md").write_text("---\nname: roblox-datastore-service-patterns\n---\n# invalid\n",
                                     encoding="utf-8")  # Missing required description.
    monkeypatch.setattr(skill_packs, "PACKS_DIR", tmp_path)
    skill_packs.available.cache_clear()
    assert skill_packs.available() == ()


def test_datastore_examples_fail_closed_on_existing_wrong_schema():
    pack = next(p for p in skill_packs.available()
                if p.name == "roblox-datastore-service-patterns")
    examples = re.findall(r"^~~~luau\n(.*?)\n~~~$", pack.body, re.M | re.S)
    assert len(examples) == 3
    for example in examples[:2]:
        assert 'if old ~= nil and typeof(old) ~= "number" then return nil end' in example
    assert 'if old ~= nil and typeof(old) ~= "table" then return nil end' in examples[2]
