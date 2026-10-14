"""Exercise the real registry, selection and rendering path for the opt-in pack."""
import pytest

from star import skill_packs

NAME = "roblox-game-math"


def test_math_pack_is_registered_but_default_context_is_unchanged(monkeypatch):
    monkeypatch.delenv(skill_packs.ENV_VAR, raising=False)
    packs = {pack.name: pack for pack in skill_packs.available()}
    assert NAME in packs
    assert NAME not in skill_packs.DEFAULT_ENABLED
    assert NAME not in skill_packs.enabled_names({})
    assert NAME in skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: NAME}) == {NAME}
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: "off"}) == set()
    prompt = "Roblox Vector3 dot products and cross products for projectile gravity"
    assert NAME not in skill_packs.matching_names(prompt)
    assert skill_packs.select(prompt) == skill_packs.select(prompt, enabled=skill_packs.DEFAULT_ENABLED)


@pytest.mark.parametrize("prompt", (
    "Roblox Vector3 normalize directions",
    "Luau vectors with dot products and cross products",
    "Roblox CFrame composition and look-at",
    "Luau lerp and easing families",
    "Roblox critically damped springs",
    "Luau quadratic Bezier paths",
    "Luau cubic Bezier paths",
    "Roblox projectile motion with gravity",
    "Luau angle wrapping",
    "Roblox raycast geometry",
    "Luau weighted random with seeded random streams",
    "Roblox fixed-timestep accumulation",
))
def test_explicit_opt_in_routes_math_prompts_through_the_real_selector(monkeypatch, prompt):
    monkeypatch.setenv(skill_packs.ENV_VAR, NAME)
    assert skill_packs.matching_names(prompt) == [NAME]
    selected = skill_packs.select(prompt.upper())
    assert [pack.name for pack in selected] == [NAME]
    rendered = skill_packs.render(selected)
    assert rendered == selected[0].body.rstrip() + "\n"
    assert len(rendered) <= skill_packs.MAX_BLOCK_CHARS
    assert "## Vectors and coordinate frames" in rendered
    assert "## Rays, randomness and fixed steps" in rendered


@pytest.mark.parametrize("prompt", (
    "Explain weighted random and seeded random in Python",
    "CFrame composition for a graphics essay",
    "hello", "", "Roblox checkpoint saving", "Roblox lerp",
))
def test_pack_does_not_broaden_unrelated_or_generic_routing(monkeypatch, prompt):
    monkeypatch.setenv(skill_packs.ENV_VAR, NAME)
    assert skill_packs.select(prompt) == []


def test_math_guidance_fits_the_existing_budget_and_ships_grounding():
    pack = next(pack for pack in skill_packs.available() if pack.name == NAME)
    assert len(pack.body) <= skill_packs.MAX_BODY_CHARS
    assert pack.file.parent.name == NAME
    assert "references/math.md" in pack.body
    for filename in ("math.md", "sources.md"):
        assert (pack.file.parent / "references" / filename).is_file()
    sources = (pack.file.parent / "references/sources.md").read_text(encoding="utf-8")
    assert "**not**\nverified with the knowledge service /api-lookup" in sources
    assert sources.count("https://create.roblox.com/docs/") >= 5
    for forbidden in ("MATH-01", "golden-tasks", "reference_answer", "bad_answer"):
        assert forbidden not in pack.body
