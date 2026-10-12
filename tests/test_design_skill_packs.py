"""Design packs: actual loading/routing, opt-in boundaries and source/content contracts."""
import re
from urllib.parse import urlsplit

import pytest

from star import skill_packs
from star.agent_skills import SkillLibrary

CASES = (
    ("design-core-loop-and-progression",
     "Design Roblox core loops with progression pacing, reward schedules and difficulty curves."),
    ("design-onboarding-and-tutorial",
     "Plan Roblox onboarding: first sixty seconds, tutorial design and teaching by doing."),
    ("design-game-feel",
     "Improve Roblox game feel with action feedback, feedback timing, camera feedback and sound feedback."),
    ("design-level-and-obby-layout",
     "Plan a Roblox obby layout with checkpoint spacing, level readability and risk and reward."),
    ("design-economy-and-fair-monetisation",
     "Design a Roblox economy with currency sinks, currency sources, inflation and fair monetisation."),
    ("design-ui-ux-for-games",
     "Plan Roblox game UI with information hierarchy, thumb zones, readable text and colour-blind safety."),
)
NAMES = tuple(name for name, _ in CASES)
SOURCE_HOSTS = {"create.roblox.com", "about.roblox.com", "learn.microsoft.com", "www.w3.org"}


@pytest.fixture(autouse=True)
def isolated_pack_settings(monkeypatch):
    monkeypatch.delenv(skill_packs.ENV_VAR, raising=False)
    skill_packs.available.cache_clear()
    yield
    skill_packs.available.cache_clear()


def section(body, heading):
    return body.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def test_design_packs_are_registered_but_not_promoted():
    assert set(NAMES) <= set(skill_packs.TRIGGERS)
    assert set(NAMES) <= {pack.name for pack in skill_packs.available()}
    assert set(NAMES).isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert set(NAMES).isdisjoint(skill_packs.enabled_names({}))
    assert set(NAMES) <= skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: ", ".join(NAMES)}) == set(NAMES)


@pytest.mark.parametrize(("name", "prompt"), CASES)
def test_opt_in_routes_and_renders_the_complete_design_pack(monkeypatch, name, prompt):
    # Execute the public selector with the environment switch, not just the regex.
    assert name not in skill_packs.matching_names(prompt)
    monkeypatch.setenv(skill_packs.ENV_VAR, name)
    assert skill_packs.enabled_names() == {name}
    selected = skill_packs.select(prompt)
    assert [pack.name for pack in selected] == [name]
    rendered = skill_packs.render(selected)
    assert rendered == selected[0].body + "\n"
    assert "## Checklist" in rendered and "## Sources" in rendered
    assert len(selected[0].body) <= skill_packs.MAX_BODY_CHARS
    assert len(rendered) <= skill_packs.MAX_BLOCK_CHARS
    monkeypatch.setenv(skill_packs.ENV_VAR, "all")
    assert skill_packs.matching_names(prompt) == [name]
    monkeypatch.setenv(skill_packs.ENV_VAR, "off")
    assert skill_packs.select(prompt) == []
    assert skill_packs.render(skill_packs.select(prompt)) == ""


@pytest.mark.parametrize(("name", "prompt"), CASES)
def test_design_routing_still_requires_roblox_context(name, prompt):
    assert skill_packs.select(prompt.replace("Roblox ", ""), enabled=NAMES) == []
    assert skill_packs.matching_names(prompt.upper(), enabled={name}) == [name]


@pytest.mark.parametrize("prompt", (
    "Roblox UI menu.",
    "Roblox camera and sound.",
    "Roblox checkpoints and kill bricks.",
    "Roblox Animator LoadAnimation and KeyframeMarker.",
    "Roblox DataStore UpdateAsync and BindToClose.",
    "Roblox RemoteEvent FireServer OnServerEvent.",
    "Roblox microeconomy, onboardingish, thumbnail and overinflation.",
    "hello", "", "   ", None, "Roblox " + "onboarding " * 2000,
))
def test_generic_words_implementation_topics_and_invalid_prompts_do_not_route_design(prompt):
    assert skill_packs.select(prompt, enabled=NAMES) == []


@pytest.mark.parametrize("name", NAMES)
def test_design_pack_has_ten_rules_an_example_and_a_checklist(name):
    pack = next(pack for pack in skill_packs.available() if pack.name == name)
    assert pack.file.parent.name == name
    assert 1 <= len(pack.description) <= 1024
    assert pack.body.startswith(f"# {name}\n")
    assert len(section(pack.body, "When to use")) > 100
    rules = re.findall(r"^(\d+)\. (.+)$", section(pack.body, "Ten concrete rules"), re.MULTILINE)
    assert [int(number) for number, _ in rules] == list(range(1, 11))
    assert all(len(rule) > 65 for _, rule in rules)
    example = section(pack.body, "Worked Roblox example")
    assert "Hypothetical game:" in example and len(example) > 900
    assert "not " in example  # distinguish proposals from observed playtests
    assert len(re.findall(r"^- \[ \] .+$", section(pack.body, "Checklist"), re.MULTILINE)) >= 6
    assert "[references/sources.md](references/sources.md)" in section(pack.body, "Sources")
    assert "```" not in pack.body  # these are design packs, not code skeletons
    files = {path.relative_to(pack.file.parent).as_posix()
             for path in pack.file.parent.rglob("*") if path.is_file()}
    assert files == {"SKILL.md", "references/sources.md"}


@pytest.mark.parametrize("name", NAMES)
def test_actual_skill_library_loads_design_instructions_and_grounding(tmp_path, name):
    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    assert {skill.name: skill.source for skill in library.catalog()}[name] == "bundled"
    loaded = library.load(name)
    pack = next(pack for pack in skill_packs.available() if pack.name == name)
    assert loaded["instructions"].strip() == pack.body
    assert loaded["references"] == ["references/sources.md"]
    sources = library.read_reference(name, "references/sources.md")["content"]
    assert sources.startswith(f"# Sources for {name}\n")
    assert "Reviewed on 2026-10-11" in sources
    assert "no knowledge-service lookup" in sources.lower()
    assert "verified with the knowledge service /api-lookup" not in sources
    links = re.findall(r"https://[^\s|]+", sources)
    assert len(set(links)) >= 3
    for link in links:
        url = urlsplit(link)
        assert url.scheme == "https" and url.hostname in SOURCE_HOSTS
        assert url.username is None and url.password is None
    assert sum(urlsplit(link).hostname == "create.roblox.com" for link in set(links)) >= 2
    source_ids = set(re.findall(r"^\| (S\d+) \|", sources, re.MULTILINE))
    assert len(source_ids) >= 3
    assert set(re.findall(r"\bS\d+\b", pack.body)) <= source_ids


def test_economy_pack_preserves_policy_requirements_and_fairness_distinction(tmp_path):
    name = "design-economy-and-fair-monetisation"
    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    body = library.load(name)["instructions"]
    sources = library.read_reference(name, "references/sources.md")["content"]
    for requirement in ("actual numerical percentage before purchase", "currency bought with Robux",
                        "probabilities total 100%", "ArePaidRandomItemsRestricted", "IsPaidItemTradingAllowed",
                        "each possible paid outcome", "no fake scarcity", "pay-to-win traps for children",
                        "not a claim that Roblox bans every paid advantage"):
        assert requirement.lower() in body.lower()
    for official_page in ("https://create.roblox.com/docs/production/monetization/paid-random-items",
                          "https://create.roblox.com/docs/production/monetization",
                          "https://about.roblox.com/community-standards"):
        assert official_page in sources
