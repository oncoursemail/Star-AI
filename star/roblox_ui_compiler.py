"""Deterministic, offline compiler for a small declarative Roblox UI format.

Input is JSON text (or a parsed mapping); no executable Luau is accepted as input.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

KINDS = {
    "screen": "ScreenGui", "frame": "Frame", "scroll": "ScrollingFrame",
    "grid": "Frame", "text": "TextLabel", "button": "TextButton",
    "image": "ImageLabel", "input": "TextBox", "toggle": "TextButton",
    "progress": "Frame",
}
TEXT_KINDS = {"text", "button", "input", "toggle"}
CONTAINERS = {"screen", "frame", "scroll", "grid"}
EASING = {"Linear", "Sine", "Quad", "Cubic", "Quart", "Quint", "Exponential", "Circular", "Back", "Bounce", "Elastic"}
DIRECTIONS = {"In", "Out", "InOut"}
STATE_NAMES = {"hover", "pressed", "disabled", "selected"}
NODE_KEYS = {"type", "id", "name", "size", "position", "anchor", "background", "transparency",
             "visible", "padding", "corner", "stroke", "text", "font", "textSize",
             "textColor", "textWrapped", "image", "layout", "states", "children",
             "minSize", "maxSize", "aspectRatio", "value", "placeholder", "enabled"}
ROOT_KEYS = {"palette", "mobile", "root"}
MOBILE_KEYS = {"safeArea", "minTouchSize", "referenceWidth", "scaleByViewport"}
LAYOUT_KEYS = {"kind", "direction", "spacing", "columns", "cellSize", "cellPadding",
               "horizontalAlignment", "verticalAlignment", "sortOrder"}
STYLE_KEYS = {"background", "textColor", "transparency", "duration", "easing", "direction"}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
FONTS = {"Gotham", "GothamBold", "GothamMedium", "SourceSans", "Arial", "Code",
         "Roboto", "Ubuntu", "Cartoon", "FredokaOne"}
ALIGNMENTS = {"Left", "Center", "Right", "Top", "Bottom"}
SORT_ORDERS = {"LayoutOrder", "Name"}

@dataclass(frozen=True)
class Diagnostic:
    severity: str
    path: str
    message: str
    line: int = 1
    column: int = 1

    def __str__(self) -> str:
        return f"{self.line}:{self.column}: {self.severity}: {self.path}: {self.message}"


class SpecError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__("\n".join(map(str, diagnostics)))


@dataclass(frozen=True)
class Compilation:
    source: str
    warnings: tuple[Diagnostic, ...]


def _location(raw: str, path: str) -> tuple[int, int]:
    # Search for the last property token, retaining useful source locations
    # even for nested fields and arrays without requiring a JSON dependency.
    segments = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", path)
    token = json.dumps(segments[-1]) if segments else '"root"'
    at = raw.find(token)
    if at < 0:
        at = 0
    return raw.count("\n", 0, at) + 1, at - raw.rfind("\n", 0, at)


def _color(rgb: str) -> tuple[int, int, int]:
    return tuple(int(rgb[i:i + 2], 16) for i in (1, 3, 5))


def _luminance(rgb: str) -> float:
    def channel(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4
    return sum(w * channel(v) for w, v in zip((.2126, .7152, .0722), _color(rgb)))


def _contrast(a: str, b: str) -> float:
    x, y = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (x + .05) / (y + .05)


def validate(spec: str | dict[str, Any]) -> tuple[dict[str, Any], tuple[Diagnostic, ...]]:
    """Validate a spec, raising SpecError for errors and returning contrast warnings."""
    raw = spec if isinstance(spec, str) else json.dumps(spec)
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, json.JSONDecodeError):
            raise SpecError([Diagnostic("error", "$", exc.msg, exc.lineno, exc.colno)]) from exc
        raise SpecError([Diagnostic("error", "$", str(exc))]) from exc
    issues: list[Diagnostic] = []

    def issue(severity: str, path: str, message: str) -> None:
        line, col = _location(raw, path)
        issues.append(Diagnostic(severity, path, message, line, col))

    def keys(obj: Any, allowed: set[str], path: str) -> bool:
        if not isinstance(obj, dict):
            issue("error", path, "expected object")
            return False
        for k in obj:
            if k not in allowed:
                issue("error", path + "." + k, "unknown key")
        return True

    def number(value: Any, path: str, lo: float, hi: float) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            issue("error", path, f"expected finite number from {lo:g} to {hi:g}")
            return False
        return True

    def dimension(value: Any, path: str) -> None:
        if not keys(value, {"scale", "offset"}, path):
            return
        if not value or any(not number(v, path + "." + k, -100000 if k == "offset" else -10,
                                   100000 if k == "offset" else 10) for k, v in value.items()):
            if not value:
                issue("error", path, "dimension cannot be empty")

    def vector(value: Any, path: str) -> None:
        if not keys(value, {"x", "y"}, path):
            return
        for axis in ("x", "y"):
            if axis not in value:
                issue("error", path + "." + axis, "required")
            else:
                dimension(value[axis], path + "." + axis)

    if not keys(data, ROOT_KEYS, "$"):
        raise SpecError(issues)
    palette = data.get("palette", {})
    if isinstance(palette, dict):
        for name, color in palette.items():
            if not ID_RE.fullmatch(name) or not isinstance(color, str) or not COLOR_RE.fullmatch(color):
                issue("error", "$.palette." + str(name), "expected named #RRGGBB colour")
    else:
        issue("error", "$.palette", "expected object")
        palette = {}
    mobile = data.get("mobile", {})
    if keys(mobile, MOBILE_KEYS, "$.mobile"):
        for name in ("safeArea", "scaleByViewport"):
            if name in mobile and not isinstance(mobile[name], bool):
                issue("error", "$.mobile." + name, "expected boolean")
        if "minTouchSize" in mobile:
            number(mobile["minTouchSize"], "$.mobile.minTouchSize", 44, 200)
        if "referenceWidth" in mobile:
            number(mobile["referenceWidth"], "$.mobile.referenceWidth", 320, 3840)

    def palette_color(value: Any, path: str) -> str | None:
        if not isinstance(value, str) or value not in palette:
            issue("error", path, "expected a defined palette colour name")
            return None
        return palette[value]

    seen: set[str] = set()

    def node(obj: Any, path: str, depth: int, inherited_bg: str | None) -> None:
        if depth > 32:
            issue("error", path, "tree depth limit (32) exceeded")
            return
        if not keys(obj, NODE_KEYS, path):
            return
        kind = obj.get("type")
        if kind not in KINDS:
            issue("error", path + ".type", "unknown or missing element type")
            return
        ident = obj.get("id")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            issue("error", path + ".id", "id must match [A-Za-z][A-Za-z0-9_]*")
        elif ident in seen:
            issue("error", path + ".id", "duplicate id")
        else:
            seen.add(ident)
        if kind == "screen" and depth != 0:
            issue("error", path + ".type", "screen must be root")
        if depth == 0 and kind != "screen":
            issue("error", path + ".type", "root must be screen")
        for k in ("name", "text", "placeholder", "image"):
            if k in obj and (not isinstance(obj[k], str) or len(obj[k]) > 4096):
                issue("error", path + "." + k, "expected string up to 4096 characters")
        if "image" in obj and not re.fullmatch(r"rbxassetid://[0-9]+", str(obj["image"])):
            issue("error", path + ".image", "image must be rbxassetid://<digits>")
        for k in ("size", "position", "anchor", "minSize", "maxSize"):
            if k in obj:
                vector(obj[k], path + "." + k)
        for k in ("padding", "corner", "textSize", "aspectRatio", "value", "transparency"):
            if k in obj:
                bounds = {"padding": (0, 1000), "corner": (0, 1000), "textSize": (1, 200),
                          "aspectRatio": (.01, 100), "value": (0, 1), "transparency": (0, 1)}
                number(obj[k], path + "." + k, *bounds[k])
        for k in ("visible", "textWrapped", "enabled"):
            if k in obj and not isinstance(obj[k], bool):
                issue("error", path + "." + k, "expected boolean")
        if "font" in obj and obj["font"] not in FONTS:
            issue("error", path + ".font", "unsupported font enum")
        background = inherited_bg
        if "background" in obj:
            background = palette_color(obj["background"], path + ".background")
        foreground = palette_color(obj["textColor"], path + ".textColor") if "textColor" in obj else None
        if kind in TEXT_KINDS and foreground and background and _contrast(foreground, background) < 4.5:
            issue("warning", path + ".textColor", "text contrast is below 4.5:1")
        stroke = obj.get("stroke")
        if stroke is not None and keys(stroke, {"color", "thickness", "transparency"}, path + ".stroke"):
            if "color" in stroke:
                palette_color(stroke["color"], path + ".stroke.color")
            for k, lo, hi in (("thickness", 0, 20), ("transparency", 0, 1)):
                if k in stroke:
                    number(stroke[k], path + ".stroke." + k, lo, hi)
        layout = obj.get("layout")
        if layout is not None and keys(layout, LAYOUT_KEYS, path + ".layout"):
            if kind not in CONTAINERS:
                issue("error", path + ".layout", "layout requires a container")
            if layout.get("kind") not in {"list", "grid"}:
                issue("error", path + ".layout.kind", "expected list or grid")
            if "direction" in layout and layout["direction"] not in {"Horizontal", "Vertical"}:
                issue("error", path + ".layout.direction", "expected Horizontal or Vertical")
            for k in ("spacing", "cellPadding"):
                if k in layout:
                    number(layout[k], path + ".layout." + k, 0, 1000)
            if "columns" in layout and (type(layout["columns"]) is not int or not 1 <= layout["columns"] <= 50):
                issue("error", path + ".layout.columns", "expected integer 1..50")
            if "cellSize" in layout:
                vector(layout["cellSize"], path + ".layout.cellSize")
            for k in ("horizontalAlignment", "verticalAlignment"):
                if k in layout and layout[k] not in ALIGNMENTS:
                    issue("error", path + ".layout." + k, "invalid alignment")
            if "sortOrder" in layout and layout["sortOrder"] not in SORT_ORDERS:
                issue("error", path + ".layout.sortOrder", "invalid sort order")
        states = obj.get("states", {})
        if keys(states, STATE_NAMES, path + ".states"):
            for state, settings in states.items():
                sp = path + ".states." + state
                if keys(settings, STYLE_KEYS, sp):
                    for k in ("background", "textColor"):
                        if k in settings:
                            palette_color(settings[k], sp + "." + k)
                    for k, lo, hi in (("transparency", 0, 1), ("duration", 0, 5)):
                        if k in settings:
                            number(settings[k], sp + "." + k, lo, hi)
                    if settings.get("easing", "Quad") not in EASING:
                        issue("error", sp + ".easing", "unsupported TweenService easing")
                    if settings.get("direction", "Out") not in DIRECTIONS:
                        issue("error", sp + ".direction", "unsupported easing direction")
            if states and kind not in {"button", "toggle", "input"}:
                issue("error", path + ".states", "states require an interactive element")
        children = obj.get("children", [])
        if not isinstance(children, list):
            issue("error", path + ".children", "expected array")
        elif children and kind not in CONTAINERS:
            issue("error", path + ".children", "children require a container")
        else:
            for i, child in enumerate(children):
                node(child, path + f".children[{i}]", depth + 1, background)
    if "root" not in data:
        issue("error", "$.root", "required")
    else:
        node(data["root"], "$.root", 0, None)
    errors = [d for d in issues if d.severity == "error"]
    if errors:
        raise SpecError(errors + [d for d in issues if d.severity == "warning"])
    return data, tuple(d for d in issues if d.severity == "warning")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _lua_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _udim(vec: dict[str, Any]) -> str:
    def part(axis: str) -> str:
        dim = vec[axis]
        return f"{dim.get('scale', 0):g}, {dim.get('offset', 0):g}"
    return f"UDim2.new({part('x')}, {part('y')})"


def _emit(spec: dict[str, Any]) -> str:
    palette = spec.get("palette", {})
    mobile = spec.get("mobile", {})
    lines = [
        "-- Generated by STAR Roblox UI compiler. Client-side presentation only.",
        "-- Never use LocalPlayer UI data as authority for purchases or gameplay.",
        'local TweenService = game:GetService("TweenService")',
        'local GuiService = game:GetService("GuiService")',
        'local Players = game:GetService("Players")',
        'local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")',
        "local handles, connections, tweens = {}, {}, {}",
        "local destroyed = false",
        "local function track(connection)",
        "    table.insert(connections, connection)",
        "end",
        "local function animate(target, goals, duration, easing, direction)",
        "    if destroyed then return end",
        "    if tweens[target] then tweens[target]:Cancel() end",
        "    local tween = TweenService:Create(target, TweenInfo.new(duration, easing, direction), goals)",
        "    tweens[target] = tween",
        "    tween:Play()",
        "end",
    ]
    if mobile.get("safeArea", True):
        lines.extend([
            "-- ScreenGui.ScreenInsets uses the engine's GuiService safe-area information.",
            "local safeTopLeft, safeBottomRight = GuiService:GetGuiInset()",
            "-- Retained for custom inset-aware positioning by consumers.",
            "local guiInsets = {safeTopLeft, safeBottomRight}",
        ])
    root = spec["root"]
    count = 0

    def put(s: str) -> None:
        lines.append(s)

    def color(name: str) -> str:
        rgb = _color(palette[name])
        return f"Color3.fromRGB({rgb[0]}, {rgb[1]}, {rgb[2]})"

    def walk(node: dict[str, Any], parent: str | None) -> None:
        nonlocal count
        count += 1
        var = f"n{count}"
        kind = node["type"]
        put(f'local {var} = Instance.new("{KINDS[kind]}")')
        put(f'{var}.Name = {_lua_string(node.get("name", node["id"]))}')
        if kind == "screen":
            put(f"{var}.ResetOnSpawn = false")
            put(f"{var}.ScreenInsets = Enum.ScreenInsets.{('CoreUISafeInsets' if mobile.get('safeArea', True) else 'None')}")
        else:
            put(f"{var}.BorderSizePixel = 0")
            if "size" in node:
                put(f"{var}.Size = {_udim(node['size'])}")
            if "position" in node:
                put(f"{var}.Position = {_udim(node['position'])}")
            if "anchor" in node:
                a = node["anchor"]
                put(f"{var}.AnchorPoint = Vector2.new({a['x'].get('scale', 0):g}, {a['y'].get('scale', 0):g})")
        props = (("background", "BackgroundColor3", color),
                 ("textColor", "TextColor3", color),
                 ("transparency", "BackgroundTransparency", str),
                 ("visible", "Visible", lambda v: str(v).lower()),
                 ("textWrapped", "TextWrapped", lambda v: str(v).lower()),
                 ("textSize", "TextSize", str),
                 ("text", "Text", _lua_string),
                 ("placeholder", "PlaceholderText", _lua_string),
                 ("image", "Image", _lua_string),
                 ("font", "Font", lambda v: f"Enum.Font.{v}"))
        for key, prop, render in props:
            if key in node and (key not in {"textColor", "text", "textWrapped", "textSize", "font"} or kind in TEXT_KINDS):
                put(f"{var}.{prop} = {render(node[key])}")
        if kind in {"frame", "scroll", "grid", "progress"} and "background" not in node:
            put(f"{var}.BackgroundTransparency = 1")
        if kind == "scroll":
            put(f"{var}.AutomaticCanvasSize = Enum.AutomaticSize.Y")
            put(f"{var}.CanvasSize = UDim2.fromOffset(0, 0)")
        if kind == "input":
            put(f"{var}.ClearTextOnFocus = false")
        if "enabled" in node and kind in {"button", "toggle", "input"}:
            put(f"{var}.Interactable = {str(node['enabled']).lower()}")
        if "corner" in node:
            put('do')
            put('    local corner = Instance.new("UICorner")')
            put(f"    corner.CornerRadius = UDim.new(0, {node['corner']:g})")
            put(f"    corner.Parent = {var}")
            put('end')
        if "stroke" in node:
            stroke = node["stroke"]
            put('do')
            put('    local stroke = Instance.new("UIStroke")')
            if "color" in stroke:
                put(f"    stroke.Color = {color(stroke['color'])}")
            if "thickness" in stroke:
                put(f"    stroke.Thickness = {stroke['thickness']:g}")
            if "transparency" in stroke:
                put(f"    stroke.Transparency = {stroke['transparency']:g}")
            put(f"    stroke.Parent = {var}")
            put("end")
        if "padding" in node:
            put('do')
            put('    local padding = Instance.new("UIPadding")')
            for edge in ("Top", "Bottom", "Left", "Right"):
                put(f"    padding.Padding{edge} = UDim.new(0, {node['padding']:g})")
            put(f"    padding.Parent = {var}")
            put("end")
        if "aspectRatio" in node:
            put('do')
            put('    local aspect = Instance.new("UIAspectRatioConstraint")')
            put(f"    aspect.AspectRatio = {node['aspectRatio']:g}")
            put(f"    aspect.Parent = {var}")
            put("end")
        if "minSize" in node or "maxSize" in node:
            put('do')
            put('    local constraint = Instance.new("UISizeConstraint")')
            for key, prop in (("minSize", "MinSize"), ("maxSize", "MaxSize")):
                if key in node:
                    x = node[key]["x"].get("offset", 0)
                    y = node[key]["y"].get("offset", 0)
                    put(f"    constraint.{prop} = Vector2.new({x:g}, {y:g})")
            put(f"    constraint.Parent = {var}")
            put("end")
        layout = node.get("layout")
        if layout:
            grid = layout["kind"] == "grid"
            put('do')
            put(f'    local layout = Instance.new("{"UIGridLayout" if grid else "UIListLayout"}")')
            if grid:
                if "cellSize" in layout:
                    put(f"    layout.CellSize = {_udim(layout['cellSize'])}")
                put(f"    layout.CellPadding = UDim2.fromOffset({layout.get('cellPadding', 0):g}, {layout.get('cellPadding', 0):g})")
                if "columns" in layout:
                    put(f"    layout.FillDirectionMaxCells = {layout['columns']}")
            else:
                put(f"    layout.FillDirection = Enum.FillDirection.{layout.get('direction', 'Vertical')}")
                put(f"    layout.Padding = UDim.new(0, {layout.get('spacing', 0):g})")
            for key, prop in (("horizontalAlignment", "HorizontalAlignment"),
                              ("verticalAlignment", "VerticalAlignment"),
                              ("sortOrder", "SortOrder")):
                if key in layout:
                    put(f"    layout.{prop} = Enum.{prop}.{layout[key]}")
            put(f"    layout.Parent = {var}")
            put("end")
        if kind in {"button", "toggle", "input"}:
            states = node.get("states", {})
            if states:
                put("do")
                put("    local hovering, pressing, selected = false, false, false")
                put(f"    local function refresh()")
                put(f"        local state = not {var}.Interactable and 'disabled' or pressing and 'pressed' or selected and 'selected' or hovering and 'hover' or ''")
                put("        if state == '' then return end")
                put("        local goals = {}")
                for state, style in states.items():
                    put(f"        if state == {_lua_string(state)} then")
                    for field, prop in (("background", "BackgroundColor3"), ("textColor", "TextColor3"), ("transparency", "BackgroundTransparency")):
                        if field in style:
                            val = color(style[field]) if field in {"background", "textColor"} else str(style[field])
                            put(f"            goals.{prop} = {val}")
                    put(f"            if next(goals) then animate({var}, goals, {style.get('duration', .15):g}, Enum.EasingStyle.{style.get('easing', 'Quad')}, Enum.EasingDirection.{style.get('direction', 'Out')}) end")
                    put("        end")
                put("    end")
                put(f"    track({var}.MouseEnter:Connect(function() hovering = true; refresh() end))")
                put(f"    track({var}.MouseLeave:Connect(function() hovering = false; pressing = false; refresh() end))")
                put(f"    track({var}.MouseButton1Down:Connect(function() pressing = true; refresh() end))" if kind != "input" else f"    track({var}.Focused:Connect(function() pressing = true; refresh() end))")
                put(f"    track({var}.MouseButton1Up:Connect(function() pressing = false; refresh() end))" if kind != "input" else f"    track({var}.FocusLost:Connect(function() pressing = false; refresh() end))")
                if kind == "toggle":
                    put(f"    track({var}.Activated:Connect(function() selected = not selected; refresh() end))")
                put(f"    track({var}:GetPropertyChangedSignal('Interactable'):Connect(refresh))")
                put("    refresh()")
                put("end")
        if kind == "progress":
            value = node.get("value", 0)
            put('do')
            put('    local fill = Instance.new("Frame")')
            put('    fill.Name = "Fill"')
            put(f"    fill.Size = UDim2.fromScale({value:g}, 1)")
            put("    fill.BorderSizePixel = 0")
            put("    fill.Parent = " + var)
            put("end")
        put(f'handles[{_lua_string(node["id"])}] = {var}')
        if kind in {"button", "toggle", "input"} and mobile.get("minTouchSize", 44) >= 44:
            put('do')
            put('    local touch = Instance.new("UISizeConstraint")')
            put(f"    touch.MinSize = Vector2.new({mobile.get('minTouchSize', 44):g}, {mobile.get('minTouchSize', 44):g})")
            put(f"    touch.Parent = {var}")
            put("end")
        # Set Parent after all local properties and decorations.
        put(f"{var}.Parent = {parent or 'playerGui'}")
        for child in node.get("children", []):
            walk(child, var)

    walk(root, None)
    ref_width = mobile.get("referenceWidth", 1280)
    if mobile.get("scaleByViewport", True):
        lines.extend([
            'local screenScale = Instance.new("UIScale")',
            "screenScale.Name = 'ViewportScale'",
            f"local function rescale() screenScale.Scale = math.clamp(n1.AbsoluteSize.X / {ref_width:g}, 0.5, 2) end",
            "screenScale.Parent = n1",
            "rescale()",
            "track(n1:GetPropertyChangedSignal('AbsoluteSize'):Connect(rescale))",
        ])
    lines.extend([
        "local function destroy()",
        "    if destroyed then return end",
        "    destroyed = true",
        "    for _, connection in ipairs(connections) do connection:Disconnect() end",
        "    for _, tween in pairs(tweens) do tween:Cancel() end",
        "    n1:Destroy()",
        "    table.clear(connections)",
        "    table.clear(tweens)",
        "    table.clear(handles)",
        "end",
        "return {handles = handles, destroy = destroy}",
    ])
    return "\n".join(lines) + "\n"


def compile_ui(spec: str | dict[str, Any]) -> Compilation:
    """Compile validated JSON into a deterministic LocalScript-ready Luau module."""
    data, warnings = validate(spec)
    return Compilation(_emit(data), warnings)
