"""STAR chat can safely preview architecture without local write or Blender privileges."""
from jsonschema import ValidationError
import pytest

from star.intelligence import LocalIntelligence

REQUEST = {"name": "Stylized Workshop", "style": "industrial",
           "width_studs": 48, "depth_studs": 24, "floors": 1, "bays": 4}


def local_intelligence(tmp_path):
    return LocalIntelligence(home=tmp_path, skills_enabled=False,
                             graphify_enabled=False, roblox_research_enabled=False)


def test_architecture_tool_is_discoverable_only_for_roblox_building_prompts(tmp_path, monkeypatch):
    monkeypatch.setenv('STAR_ARCHITECTURE_TOOLS', '1')
    local = local_intelligence(tmp_path)
    tools = local.definitions("In my Roblox Studio game build a Blender building with real architecture")
    assert {t["name"] for t in tools} == {"star_architecture_preview", "star_architecture_compare_styles"}
    assert local.definitions("Explain this GitHub codebase architecture") == []
    assert local.definitions("hello") == []


def test_architecture_tool_is_pure_read_only_and_reports_actual_geometry(tmp_path):
    local = local_intelligence(tmp_path)
    data = local.call("star_architecture_preview", REQUEST, enabled={"star_architecture_preview"})
    assert data["openings"]["entrances"] == 1
    assert data["openings"]["glazed_windows"] == 7
    assert data["audit"]["valid"] is True, data["audit"]
    assert data["roof"] == "flat"
    assert data["dimensions_studs"] == [48, 24, 13]
    assert data["output"].startswith("PLAN_ONLY:")
    assert list(tmp_path.iterdir()) == []  # No Blender, output folder or Studio edit


def test_architecture_tool_rejects_scope_and_bad_model_arguments(tmp_path):
    local = local_intelligence(tmp_path)
    with pytest.raises(PermissionError):
        local.call("star_architecture_preview", REQUEST, enabled=set())
    with pytest.raises(ValidationError):
        local.call("star_architecture_preview", {**REQUEST, "python_script": "exec('x')"},
                   enabled={"star_architecture_preview"})
    with pytest.raises(ValidationError):
        local.call("star_architecture_preview", {**REQUEST, "floors": True},
                   enabled={"star_architecture_preview"})
    with pytest.raises(ValueError, match="facade bay"):
        local.call("star_architecture_preview", {**REQUEST, "bays": 8, "width_studs": 24},
                   enabled={"star_architecture_preview"})


def test_compare_eight_styles_without_blender_or_any_file_write(tmp_path):
    local = local_intelligence(tmp_path)
    request = {key: value for key, value in REQUEST.items() if key != "style"}
    result = local.call("star_architecture_compare_styles", request,
                        enabled={"star_architecture_compare_styles"})
    assert len(result["variants"]) == 8
    assert {row["style"] for row in result["variants"]} == {
        "storybook", "industrial", "modern", "spaceport",
        "gothic", "brutalist", "coastal", "anime_city",
    }
    assert all(row["static_valid"] and row["estimated_triangles"] > 0 for row in result["variants"])
    assert result["rendered"] is False and result["studio_imported"] is False
    assert list(tmp_path.iterdir()) == []


def test_compare_styles_rejects_invalid_unknown_style(tmp_path):
    local = local_intelligence(tmp_path)
    request = {key: value for key, value in REQUEST.items() if key != "style"}
    with pytest.raises(ValidationError):
        local.call("star_architecture_compare_styles",
                   {**request, "styles": ["storybook", "unknown"]},
                   enabled={"star_architecture_compare_styles"})


def test_architecture_tools_are_not_offered_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("STAR_ARCHITECTURE_TOOLS", raising=False)
    local = local_intelligence(tmp_path)
    assert local.definitions("In my Roblox Studio game build a Blender building with real architecture") == []
    assert local.owns("star_architecture_preview")
    with pytest.raises(PermissionError, match="not enabled"):
        local.call("star_architecture_preview", REQUEST, enabled=set())


@pytest.mark.parametrize("switch", ["1", "true", "on", "yes"])
def test_architecture_tools_accept_explicit_truthy_switches(tmp_path, monkeypatch, switch):
    monkeypatch.setenv("STAR_ARCHITECTURE_TOOLS", "  " + switch.upper() + "  ")
    local = local_intelligence(tmp_path)
    names = [tool["name"] for tool in local.definitions("Build a Roblox Blender warehouse")]
    assert names == ["star_architecture_preview", "star_architecture_compare_styles"]
    assert local.definitions("Explain my Roblox code architecture") == []


@pytest.mark.parametrize("switch", ["0", "false", "off", "no", "invalid"])
def test_architecture_tools_reject_non_opt_in_values(tmp_path, monkeypatch, switch):
    monkeypatch.setenv("STAR_ARCHITECTURE_TOOLS", switch)
    local = local_intelligence(tmp_path)
    assert local.definitions("Build a Roblox Blender warehouse") == []


def test_architecture_schemas_follow_existing_tool_order(tmp_path, monkeypatch):
    monkeypatch.setenv("STAR_ARCHITECTURE_TOOLS", "1")
    local = LocalIntelligence(home=tmp_path, skills_enabled=True,
                              graphify_enabled=False, roblox_research_enabled=False)
    names = [tool["name"] for tool in local.definitions("In Roblox Studio, build a Blender warehouse")]
    assert names[:3] == ["star_skill_catalog", "star_skill_load", "star_skill_reference"]
    assert names[-2:] == ["star_architecture_preview", "star_architecture_compare_styles"]
