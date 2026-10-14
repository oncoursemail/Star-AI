"""skill_packs.select tests the prompt before it reads the enabled set (which may open SQLite)."""
import pytest

from star import skill_packs

PROMPTS = (
    "What is the capital of France?",
    "How do I make a RemoteEvent that validates the player on the server in Roblox?",
    "Make a ParticleEmitter burst with sparks and a shockwave in Roblox Studio.",
    "In Godot 4, how do signals and @export work in GDScript?",
    "Fix this Roblox error: attempt to index nil with Humanoid",
    "",
)


def test_plain_prompts_never_read_the_enabled_set(monkeypatch):
    def fail(**_):
        pytest.fail("enabled_names was read for a prompt that is not a Roblox or Godot question")
    monkeypatch.setattr(skill_packs, "enabled_names", fail)
    assert skill_packs.select("What is the capital of France?", home="unused") == []
    assert skill_packs.select("Write me a poem about the sea.") == []


def test_selection_is_unchanged(monkeypatch):
    # Reference: the old order (enabled set first) is equivalent to filtering after the fact.
    for enabled in (None, (), ("roblox-vfx",), tuple(p.name for p in skill_packs.available())):
        for prompt in PROMPTS:
            chosen = skill_packs.select(prompt, enabled=enabled)
            allowed = skill_packs.enabled_names() if enabled is None else frozenset(enabled)
            if not allowed:
                assert chosen == []
            assert all(pack.name in allowed for pack in chosen)
    assert [p.name for p in skill_packs.select(PROMPTS[2], enabled=("roblox-vfx",))] == ["roblox-vfx"]
    assert skill_packs.select(PROMPTS[2], enabled=()) == []
