"""Executable compiler tests; no Roblox Studio, network, GPU, or keyring."""
import json
import re

import pytest

from star.roblox_ui_compiler import SpecError, compile_ui, validate


PALETTE = {"white": "#FFFFFF", "black": "#111111", "muted": "#777777"}
CASES = {
    "shop": {"type": "screen", "id": "shop", "children": [
        {"type": "frame", "id": "panel", "background": "black", "corner": 12,
         "children": [{"type": "button", "id": "buy", "text": "Buy", "textColor": "white",
                       "background": "black", "states": {"hover": {"background": "muted"}}}]}]},
    "inventory": {"type": "screen", "id": "inventory", "children": [
        {"type": "grid", "id": "slots", "layout": {"kind": "grid", "columns": 4,
           "cellSize": {"x": {"offset": 60}, "y": {"offset": 60}}}, "children": [
           {"type": "image", "id": "sword", "image": "rbxassetid://1234"}]}]},
    "settings": {"type": "screen", "id": "settings", "children": [
        {"type": "frame", "id": "pane", "padding": 8, "stroke": {"color": "muted", "thickness": 1},
         "children": [{"type": "toggle", "id": "music", "text": "Music", "states": {
             "selected": {"background": "muted", "duration": .2}}}]}]},
    "hud": {"type": "screen", "id": "hud", "children": [
        {"type": "progress", "id": "health", "value": .75, "aspectRatio": 6}]},
    "dialog": {"type": "screen", "id": "dialog", "children": [
        {"type": "input", "id": "reply", "placeholder": "Your reply", "textColor": "white",
         "background": "black", "states": {"pressed": {"transparency": .2}}}]},
    "leaderboard": {"type": "screen", "id": "leaderboard", "children": [
        {"type": "scroll", "id": "rows", "layout": {"kind": "list", "spacing": 4},
         "children": [{"type": "text", "id": "entry", "text": "Score"}]}]},
}


def spec(name):
    return {"palette": PALETTE, "root": CASES[name]}


@pytest.mark.parametrize("name", list(CASES))
def test_six_golden_scenarios(name):
    """Each fixture checks generated classes, handles, determinism, and cleanups."""
    s = spec(name)
    code = compile_ui(s).source
    assert code == compile_ui(json.dumps(s)).source
    assert 'local n1 = Instance.new("ScreenGui")' in code
    assert 'return {handles = handles, destroy = destroy}' in code
    assert 'connection:Disconnect()' in code
    assert 'tween:Cancel()' in code
    assert 'GuiService:GetGuiInset()' in code
    for node in _nodes(s["root"]):
        assert f'handles["{node["id"]}"]' in code
    assert code.count('Instance.new("ScreenGui")') == 1


def _nodes(node):
    yield node
    for child in node.get("children", []):
        yield from _nodes(child)


@pytest.mark.parametrize("change,path", [
    ({"extra": True}, "$.extra"),
    ({"root": {"type": "alien", "id": "root"}}, "$.root.type"),
    ({"root": {"type": "screen", "id": "bad-id"}}, "$.root.id"),
    ({"root": {"type": "screen", "id": "root", "padding": -1}}, "$.root.padding"),
    ({"root": {"type": "screen", "id": "root", "value": 1.1}}, "$.root.value"),
    ({"root": {"type": "screen", "id": "root", "children": [
        {"type": "text", "id": "root"}]}}, "$.root.children[0].id"),
    ({"mobile": {"minTouchSize": 20}}, "$.mobile.minTouchSize"),
    ({"palette": {"bad": "red"}}, "$.palette.bad"),
    ({"root": {"type": "screen", "id": "root", "children": [
        {"type": "button", "id": "buy", "states": {"hover": {"easing": "Fake"}}}]}},
     "$.root.children[0].states.hover.easing"),
    ({"root": {"type": "screen", "id": "root", "children": [
        {"type": "image", "id": "icon", "image": "http://example.com/a"}]}},
     "$.root.children[0].image"),
])
def test_validation_errors(change, path):
    base = {"palette": PALETTE, "root": {"type": "screen", "id": "root"}}
    base.update(change)
    with pytest.raises(SpecError) as error:
        validate(base)
    assert any(d.path == path and d.severity == "error" for d in error.value.diagnostics)


def test_duplicate_json_and_source_location():
    with pytest.raises(SpecError, match="duplicate JSON key"):
        validate('{"root":{"type":"screen","id":"x","id":"y"}}')
    with pytest.raises(SpecError) as error:
        validate('{\n "root": {\n "type": "bad", "id": "u"\n }\n}')
    assert any(d.line >= 2 and d.column > 0 for d in error.value.diagnostics)


def test_contrast_is_warning_not_error():
    result = compile_ui({"palette": {"same": "#888888"}, "root": {
        "type": "screen", "id": "root", "children": [
            {"type": "text", "id": "caption", "background": "same",
             "textColor": "same"}]}})
    assert len(result.warnings) == 1
    assert result.warnings[0].severity == "warning"


def test_escape_and_no_client_authority():
    code = compile_ui({"root": {"type": "screen", "id": "root", "children": [{
        "type": "text", "id": "notice", "text": '"; RemoteEvent:FireServer(1) --'
    }]}}).source
    assert 'Text = "\\\"; RemoteEvent:FireServer(1) --"' in code
    assert "loadstring" not in code
    assert "FireServer(" not in code.replace('Text = "\\\"; RemoteEvent:FireServer(1) --"', "")
    assert "GetAsync(" not in code
    assert "LocalPlayer" in code
    assert "GetService(\"Players\")" in code
    assert "DataStore" not in code


def test_unknown_state_key_and_nested_dimension():
    with pytest.raises(SpecError) as exc:
        compile_ui({"root": {"type": "screen", "id": "root", "children": [
            {"type": "button", "id": "btn", "size": {"x": {"scale": 99}, "y": {}},
             "states": {"hover": {"script": "print(1)"}}}]}})
    paths = {d.path for d in exc.value.diagnostics}
    assert "$.root.children[0].size.x.scale" in paths
    assert "$.root.children[0].size.y" in paths
    assert "$.root.children[0].states.hover.script" in paths


@pytest.mark.parametrize("field,kind,value,prop", [
    ("name", "text", "a\\x01é9", "Name"),
    ("text", "text", "Hello\\x01x", "Text"),
    ("placeholder", "input", "x\\n☃", "PlaceholderText"),
])
def test_luau_string_escaping(field, kind, value, prop):
    child = {"type": kind, "id": "child", field: value}
    code = compile_ui({"root": {"type": "screen", "id": "root", "children": [child]}}).source
    encoded = '"' + "".join(
        chr(byte) if 32 <= byte < 127 and byte not in (34, 92)
        else "\\\\" + chr(byte) if byte in (34, 92)
        else f"\\\\{byte:03d}"
        for byte in value.encode("utf-8")
    ) + '"'
    assert f"n2.{prop} = {encoded}" in code
    assert "\\\\u0001" not in code


def test_local_variable_limit():
    root = {"type": "screen", "id": "root", "children": [
        {"type": "text", "id": f"node{i}", "text": "Hi"} for i in range(149)
    ]}
    code = compile_ui({"root": root}).source
    assert len(re.findall(r"^local n\\d+ = Instance.new", code, re.MULTILINE)) == 150
    root["children"].extend({"type": "text", "id": f"node{i}"} for i in range(149, 250))
    with pytest.raises(SpecError) as error:
        compile_ui({"root": root})
    assert any("node limit" in d.message for d in error.value.diagnostics)


@pytest.mark.parametrize("kind,property_name,value", [
    ("screen", "background", "black"), ("screen", "transparency", 0.5),
    ("screen", "visible", False), ("screen", "corner", 4),
    ("screen", "stroke", {"color": "white"}),
    ("screen", "size", {"x": {"offset": 1}, "y": {"offset": 1}}),
    ("frame", "image", "rbxassetid://123"), ("text", "image", "rbxassetid://123"),
    ("button", "placeholder", "bad"), ("frame", "placeholder", "bad"),
    ("frame", "text", "bad"), ("frame", "enabled", True),
    ("text", "value", 0.3), ("image", "states", {"hover": {}}),
])
def test_class_restrictions(kind, property_name, value):
    node = {"type": kind, "id": "target", property_name: value}
    root = node if kind == "screen" else {
        "type": "screen", "id": "root", "children": [node]
    }
    path = "$.root" if kind == "screen" else "$.root.children[0]"
    with pytest.raises(SpecError) as error:
        compile_ui({"palette": PALETTE, "root": root})
    assert any(d.path == path + "." + property_name for d in error.value.diagnostics)


def test_screen_enabled_is_not_guiobject_visible():
    code = compile_ui({"root": {"type": "screen", "id": "ui", "enabled": False}}).source
    assert "n1.Enabled = false" in code
    assert "n1.Visible" not in code


@pytest.mark.parametrize("field,bad", [
    ("horizontalAlignment", "Top"), ("verticalAlignment", "Left"),
    ("verticalAlignment", "Right"), ("horizontalAlignment", ["Left"]),
    ("verticalAlignment", {"Top": True}),
])
def test_wrong_axis_and_unhashable_alignment(field, bad):
    frame = {"type": "frame", "id": "list", "layout": {"kind": "list", field: bad}}
    with pytest.raises(SpecError) as error:
        compile_ui({"root": {"type": "screen", "id": "root", "children": [frame]}})
    assert any(d.path == "$.root.children[0].layout." + field for d in error.value.diagnostics)


def test_valid_axis_enums():
    frame = {"type": "frame", "id": "list", "layout": {
        "kind": "list", "horizontalAlignment": "Left", "verticalAlignment": "Bottom"
    }}
    code = compile_ui({"root": {"type": "screen", "id": "root", "children": [frame]}}).source
    assert "Enum.HorizontalAlignment.Left" in code
    assert "Enum.VerticalAlignment.Bottom" in code


def test_interactive_state_returns_to_base_style():
    code = compile_ui({"palette": PALETTE, "root": {
        "type": "screen", "id": "root", "children": [{
            "type": "button", "id": "go", "background": "black", "textColor": "white",
            "states": {"hover": {"background": "muted"},
                       "pressed": {"textColor": "muted"},
                       "disabled": {"transparency": 0.5}}
        }]
    }}).source
    assert "local baseBackground = n2.BackgroundColor3" in code
    assert "local baseText = n2.TextColor3" in code
    assert "local baseTransparency = n2.BackgroundTransparency" in code
    assert "local goals = {BackgroundColor3 = baseBackground, TextColor3 = baseText, BackgroundTransparency = baseTransparency}" in code
    assert "if state == '' then return end" not in code
    assert "animate(n2, goals, duration, easing, direction)" in code


@pytest.mark.parametrize("location,bad", [
    ("type", ["button"]), ("font", {"value": "Gotham"}),
    ("layout.kind", ["list"]), ("layout.direction", {"value": "Vertical"}),
    ("layout.sortOrder", ["Name"]), ("states.hover.easing", {"Quad": True}),
    ("states.hover.direction", ["Out"]),
])
def test_unhashable_values_are_spec_errors(location, bad):
    node = {"type": "button", "id": "go"}
    if location == "type":
        node["type"] = bad
    elif location == "font":
        node["font"] = bad
    elif location.startswith("layout."):
        node = {"type": "frame", "id": "go", "layout": {"kind": "list"}}
        node["layout"][location.split(".")[1]] = bad
    else:
        node["states"] = {"hover": {location.split(".")[2]: bad}}
    with pytest.raises(SpecError) as error:
        compile_ui({"root": {"type": "screen", "id": "root", "children": [node]}})
    assert any(d.path == "$.root.children[0]." + location for d in error.value.diagnostics)


def test_invalid_palette_has_no_raw_contrast_exception():
    with pytest.raises(SpecError) as error:
        compile_ui({"palette": {"bad": "red", "fg": "#FFFFFF"}, "root": {
            "type": "screen", "id": "root", "children": [
                {"type": "text", "id": "notice", "background": "bad", "textColor": "fg"}
            ]}})
    assert any(d.path == "$.palette.bad" for d in error.value.diagnostics)


def test_extremely_deep_dict_is_spec_error():
    node = {"type": "text", "id": "inner"}
    for _ in range(1500):
        node = {"children": [node]}
    with pytest.raises(SpecError):
        validate({"root": node})


def test_touch_constraint_is_merged_with_size_constraints():
    button = {"type": "button", "id": "go", "minSize": {
        "x": {"offset": 60}, "y": {"offset": 20}},
        "maxSize": {"x": {"offset": 120}, "y": {"offset": 120}}}
    code = compile_ui({"mobile": {"minTouchSize": 50}, "root": {
        "type": "screen", "id": "ui", "children": [button]}}).source
    assert code.count('Instance.new("UISizeConstraint")') == 1
    assert "constraint.MinSize = Vector2.new(60, 50)" in code
    assert "constraint.MaxSize = Vector2.new(120, 120)" in code
    for change in [
        {"maxSize": {"x": {"offset": 30}, "y": {"offset": 100}}},
        {"minSize": {"x": {"scale": .5}, "y": {"offset": 60}}},
    ]:
        with pytest.raises(SpecError):
            compile_ui({"root": {"type": "screen", "id": "ui",
                                "children": [{**button, **change}]}})


def test_viewport_scaling_compensates_full_screen_host():
    code = compile_ui({"root": {"type": "screen", "id": "ui"}}).source
    assert "local scale = math.clamp(camera.ViewportSize.X / 1280, 0.5, 2)" in code
    assert "screenScale.Scale = scale" in code
    assert "host.Size = UDim2.fromScale(1 / scale, 1 / scale)" in code
    off = compile_ui({"root": {"type": "screen", "id": "ui"},
                      "mobile": {"scaleByViewport": False}}).source
    assert 'Instance.new("UIScale")' not in off


def test_full_file_golden_minimal_screen():
    source = compile_ui({"root": {"type": "screen", "id": "root"},
                         "mobile": {"safeArea": False, "scaleByViewport": False}}).source
    expected = """-- Generated by STAR Roblox UI compiler. Client-side presentation only.
-- Never use LocalPlayer UI data as authority for purchases or gameplay.
local TweenService = game:GetService("TweenService")
local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
local handles, connections, tweens = {}, {}, {}
local destroyed = false
local function track(connection)
    table.insert(connections, connection)
end
local function animate(target, goals, duration, easing, direction)
    if destroyed then return end
    if tweens[target] then tweens[target]:Cancel() end
    local tween = TweenService:Create(target, TweenInfo.new(duration, easing, direction), goals)
    tweens[target] = tween
    tween:Play()
end
local n1 = Instance.new("ScreenGui")
n1.Name = "root"
n1.ResetOnSpawn = false
n1.ScreenInsets = Enum.ScreenInsets.None
handles["root"] = n1
n1.Parent = playerGui
local host = Instance.new("Frame")
host.Name = "ResponsiveRoot"
host.Size = UDim2.fromScale(1, 1)
host.BackgroundTransparency = 1
host.Parent = n1
local function destroy()
    if destroyed then return end
    destroyed = true
    for _, connection in ipairs(connections) do connection:Disconnect() end
    for _, tween in pairs(tweens) do tween:Cancel() end
    n1:Destroy()
    table.clear(connections)
    table.clear(tweens)
    table.clear(handles)
end
return {handles = handles, destroy = destroy}
"""
    assert source == expected

