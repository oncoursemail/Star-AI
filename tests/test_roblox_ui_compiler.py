"""Executable compiler tests; no Roblox Studio, network, GPU, or keyring."""
import json

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
