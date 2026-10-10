"""Offline unit coverage for STAR's explicit multi-model capability router."""
from dataclasses import replace
from types import SimpleNamespace
import pytest

from star.brain_router import select_route, validate_alias
from star.desktop_core import Settings, needs_project_tools


def cfg(**kwargs):
    base = dict(provider="local", model="Qwen3.5-4B", fast_model="",
                reasoning_model="", roblox_model="", vision_model="", max_calls=12)
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_default_preserves_single_model_and_simple_chat():
    selection = select_route(cfg(), "Hello STAR, how are you?")
    assert selection.profile == "fast"
    assert selection.model == "Qwen3.5-4B"
    assert selection.subagent_model == "Qwen3.5-4B"
    assert selection.quick and not selection.use_tools
    assert selection.max_calls == 1
    assert selection.task_timeout == 85


def test_explicit_profile_map_routes_fast_reasoning_roblox_vision():
    s = cfg(model="qwen-4b", fast_model="qwen-2b",
            reasoning_model="qwen-27b", roblox_model="luau-specialist",
            vision_model="qwen-vision")
    assert select_route(s, "hi").model == "qwen-2b"
    deep = select_route(s, "Please debug and refactor this function")
    assert deep.profile == "reasoning" and deep.model == "qwen-27b"
    assert not deep.quick and not deep.use_tools
    roblox = select_route(s, "Build a responsive Roblox HUD")
    assert roblox.profile == "roblox" and roblox.model == "luau-specialist"
    vision = select_route(s, "What is in this picture?", image_count=1)
    assert vision.profile == "vision" and vision.model == "qwen-vision"
    assert not vision.quick


def test_manual_fast_overrides_expensive_agent_routing():
    s = cfg(fast_model="tiny", roblox_model="27B")
    route = select_route(s, "Build an entire Roblox game", mode="fast", project_tools=True)
    assert route.profile == "fast" and route.model == "tiny"
    assert route.quick and not route.use_tools


def test_explicit_agent_uses_fast_drafter_on_same_provider_only():
    s = cfg(provider="groq", fast_model="quick", reasoning_model="deep")
    route = select_route(s, "Implement an AI agent", mode="agent", project_tools=True)
    assert route.model == "deep" and route.subagent_model == "quick"
    assert route.profile == "agent" and route.use_tools
    assert route.max_calls == 12 and route.task_timeout == 480
    assert select_route(s, "simple", mode="fast").task_timeout == 55


def test_roblox_agent_prefers_roblox_specialist_and_preserves_agent_tools():
    s = cfg(reasoning_model="general-reasoner", roblox_model="star-luau")
    route = select_route(s, "Debug Luau code in Roblox Studio", mode="agent", project_tools=True)
    assert route.model == "star-luau" and route.use_tools
    assert select_route(s, "Reason about pure mathematics", mode="agent").model == "general-reasoner"


def test_images_select_vision_model_even_for_manual_agent():
    selection = select_route(cfg(reasoning_model="text-only", vision_model="image-capable"),
                             "Audit screenshot", mode="agent", image_count=2)
    assert selection.model == "image-capable"


def test_image_without_specialist_uses_primary_not_text_only_reasoner():
    s = cfg(model="vision-primary", reasoning_model="text-only-reasoner")
    assert select_route(s, "What is in this screenshot?", image_count=1).model == "vision-primary"
    assert select_route(s, "Inspect Roblox screenshots", mode="agent", image_count=1).model == "vision-primary"


def test_research_is_not_a_permission_to_run_local_studio_tools():
    route = select_route(cfg(), "Summarize latest sources", research=True)
    assert route.profile == "research" and not route.use_tools


def test_explicit_scoped_project_action_loads_tools_only_when_needed():
    route = select_route(cfg(), "Fix selected script", project_tools=True)
    assert route.use_tools and route.max_calls == 5
    assert not select_route(cfg(), "Give a definition", project_tools=False).use_tools


@pytest.mark.parametrize("bad", ["a b", "\nsecret", "x"*181, 99, None, " model", "model\tname", "https://evil.invalid/v1"])
def test_invalid_model_aliases_fail_closed(bad):
    with pytest.raises(ValueError):
        validate_alias(bad)


def test_existing_settings_are_backward_compatible_and_validate_aliases(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"provider":"local","model":"primary","project":"STAR"}', encoding="utf-8")
    old = Settings.load(path)
    assert old.fast_model == old.reasoning_model == old.roblox_model == old.vision_model == ""
    old.fast_model = "Qwen3.5-4B"
    old.reasoning_model = "Qwen3.8-27B"
    old.save(path)
    again = Settings.load(path)
    assert again.fast_model == "Qwen3.5-4B"
    assert again.reasoning_model == "Qwen3.8-27B"
    again.roblox_model = "INVALID MULTIWORD"
    with pytest.raises(ValueError):
        again.validate()


def test_followup_scoped_edit_intent_preserves_conversation_context():
    assert needs_project_tools("fix it", ["Please edit my Roblox Studio game"])
    assert needs_project_tools("make it better", ["Build my game", "Improve the Roblox HUD"])
    assert not needs_project_tools("What is the capital of France?", ["Fix Roblox UI"])
    assert not needs_project_tools("fix it", [])
    assert not needs_project_tools("fix it", ["I enjoy baking bread"])
    assert not needs_project_tools("fix this error" * 30, ["Roblox Studio"])
    assert not needs_project_tools("Tell me about Roblox history", ["Edit the script"])


def test_strict_route_inputs():
    with pytest.raises(ValueError):
        select_route(cfg(), "hello", image_count=5)
    with pytest.raises(ValueError):
        select_route(cfg(), "hello", mode="imaginary")
    with pytest.raises(ValueError):
        select_route(cfg(), " ", mode="auto")
