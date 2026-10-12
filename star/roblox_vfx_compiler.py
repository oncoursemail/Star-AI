"""Offline, standard-library-only JSON-to-Luau VFX compiler. No application wiring.

compile_vfx returns a self-contained ModuleScript with Play(part, adornee?) and
CameraShake(elapsed). See docs/ROBLOX_COMPILERS.md for the bounded v1 schema.
Validation finishes before rendering; neither function performs I/O or runs Luau.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
import re
from typing import Any

MAX_JSON_BYTES = 131_072
MAX_EFFECTS = 32
MAX_KEYPOINTS = 20
MAX_PARTICLES = 10_000
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}")
_TEXTURE = re.compile(r"rbxassetid://([1-9][0-9]{0,15})")
_BUILTIN_TEXTURE = "rbxasset://textures/particles/sparkles_main.dds"


class VFXCompileError(ValueError):
    """Invalid specification, with a JSON-style path to the failing value."""


@dataclass(frozen=True)
class _Rule:
    kind: str
    low: float = 0
    high: float = 1
    default: Any = 0
    choices: tuple[str, ...] = ()


_N = _Rule
_COMMON = {
    "Color": _N("colors", default=[1, 1, 1]),
    "Transparency": _N("sequence", default=0),
    "LightEmission": _N("number", default=0),
    "LightInfluence": _N("number", default=0),
    "Brightness": _N("number", 0, 20, 1),
    "Texture": _N("texture", default=_BUILTIN_TEXTURE),
}
_RULES = {
    "ParticleEmitter": {
        **_COMMON,
        "Rate": _N("number", 0, 400, 0),
        "Lifetime": _N("range", 0, 20, [0.5, 1]),
        "Speed": _N("range", 0, 200, 0),
        "Rotation": _N("range", -360, 360, 0),
        "RotSpeed": _N("range", -720, 720, 0),
        "Size": _N("sequence", 0, 100, 1),
        "Acceleration": _N("vector3", -1000, 1000, [0, 0, 0]),
        "SpreadAngle": _N("vector2", 0, 180, [0, 0]),
        "Drag": _N("number", 0, 100, 0),
        "VelocityInheritance": _N("number", 0, 1, 0),
        "LockedToPart": _N("bool", default=False),
        "EmissionDirection": _N("enum:NormalId", default="Top",
                                choices=("Top", "Bottom", "Front", "Back", "Left", "Right")),
        "Orientation": _N("enum:ParticleOrientation", default="FacingCamera",
                          choices=("FacingCamera", "FacingCameraWorldUp",
                                   "VelocityParallel", "VelocityPerpendicular")),
    },
    "Beam": {
        **_COMMON,
        "Width0": _N("number", 0, 20, 1),
        "Width1": _N("number", 0, 20, 1),
        "CurveSize0": _N("number", -100, 100, 0),
        "CurveSize1": _N("number", -100, 100, 0),
        "Segments": _N("integer", 1, 100, 10),
        "FaceCamera": _N("bool", default=True),
        "TextureLength": _N("number", 0.01, 100, 1),
        "TextureSpeed": _N("number", -100, 100, 1),
        "TextureMode": _N("enum:TextureMode", default="Wrap",
                          choices=("Wrap", "Static", "Stretch")),
    },
    "Trail": {
        **{k: v for k, v in _COMMON.items() if k != "Brightness"},
        "Lifetime": _N("number", 0, 10, 0.5),
        "MinLength": _N("number", 0, 1, 0.1),
        "MaxLength": _N("number", 0.01, 100, 10),
        "WidthScale": _N("sequence", 0, 1, 1),
        "FaceCamera": _N("bool", default=True),
        "TextureLength": _N("number", 0.01, 100, 1),
        "TextureMode": _N("enum:TextureMode", default="Stretch",
                          choices=("Wrap", "Static", "Stretch")),
    },
    "PointLight": {
        "Brightness": _N("number", 0, 20, 1),
        "Range": _N("number", 0, 60, 8),
        "Color": _N("color", default=[1, 1, 1]),
        "Shadows": _N("bool", default=False),
    },
    "Highlight": {
        "FillColor": _N("color", default=[1, 1, 1]),
        "OutlineColor": _N("color", default=[1, 1, 1]),
        "FillTransparency": _N("number", 0, 1, 0.5),
        "OutlineTransparency": _N("number", 0, 1, 0),
        "DepthMode": _N("enum:HighlightDepthMode", default="Occluded",
                        choices=("Occluded", "AlwaysOnTop")),
    },
}
# Only value types TweenService can interpolate, and never emission/lifetime budgets.
_TWEENABLE = {
    "ParticleEmitter": {"Brightness", "LightEmission", "LightInfluence"},
    "Beam": {"Brightness", "LightEmission", "LightInfluence", "Width0", "Width1",
             "CurveSize0", "CurveSize1", "TextureSpeed", "TextureLength"},
    "Trail": {"LightEmission", "LightInfluence", "TextureLength"},
    "PointLight": {"Brightness", "Range", "Color"},
    "Highlight": {"FillColor", "OutlineColor", "FillTransparency", "OutlineTransparency"},
}


def _fail(path: str, message: str) -> None:
    raise VFXCompileError(f"{path}: {message}")


def _object(value: Any, path: str, allowed: set[str], required: set[str] | None = None) -> dict:
    if type(value) is not dict or any(type(k) is not str for k in value):
        _fail(path, "expected an object with string keys")
    unknown = set(value) - allowed
    if unknown:
        _fail(path, f"unknown field {sorted(unknown)[0]!r}")
    missing = (required or set()) - set(value)
    if missing:
        _fail(path, f"missing field {sorted(missing)[0]!r}")
    return value


def _number(value: Any, path: str, low: float, high: float, integer: bool = False) -> int | float:
    if type(value) not in (int, float) or (integer and type(value) is not int):
        _fail(path, "expected an integer" if integer else "expected a number (not boolean)")
    if (type(value) is float and not math.isfinite(value)) or not low <= value <= high:
        _fail(path, f"expected a finite value in [{low}, {high}]")
    # Canonicalize 1 and 1.0 without rounding distinct sequence times together.
    return int(value) if value == int(value) else value


def _array(value: Any, path: str, low: int, high: int) -> list:
    if type(value) is not list or not low <= len(value) <= high:
        _fail(path, f"expected an array with {low}..{high} entries")
    return value


def _vector(value: Any, path: str, size: int, low: float, high: float) -> list:
    return [_number(v, f"{path}[{i}]", low, high)
            for i, v in enumerate(_array(value, path, size, size))]


def _choice(value: Any, path: str, choices: tuple[str, ...]) -> str:
    if type(value) is not str or value not in choices:
        _fail(path, f"expected one of {', '.join(choices)}")
    return value


def _sequence(value: Any, path: str, rule: _Rule) -> list:
    color = rule.kind == "colors"
    if color and type(value) is list and len(value) == 3 and type(value[0]) in (int, float):
        rgb = _vector(value, path, 3, 0, 1)
        return [[0, rgb], [1, rgb.copy()]]
    if not color and type(value) in (int, float):
        n = _number(value, path, rule.low, rule.high)
        return [[0, n, 0], [1, n, 0]]
    result = []
    for i, raw in enumerate(_array(value, path, 2, MAX_KEYPOINTS)):
        p = f"{path}[{i}]"
        point = _array(raw, p, 2, 2 if color else 3)
        t = _number(point[0], p + "[0]", 0, 1)
        if color:
            result.append([t, _vector(point[1], p + "[1]", 3, 0, 1)])
        else:
            n = _number(point[1], p + "[1]", rule.low, rule.high)
            envelope = _number(point[2] if len(point) == 3 else 0, p + "[2]", 0,
                               rule.high - rule.low)
            if n - envelope < rule.low or n + envelope > rule.high:
                _fail(p, "envelope crosses the property's range")
            result.append([t, n, envelope])
    result.sort(key=lambda point: point[0])
    if result[0][0] != 0 or result[-1][0] != 1:
        _fail(path, "sequence must include endpoints at 0 and 1")
    if len({p[0] for p in result}) != len(result):
        _fail(path, "sequence times must be unique")
    return result


def _property(value: Any, path: str, rule: _Rule) -> Any:
    kind = rule.kind
    if kind in ("number", "integer"):
        return _number(value, path, rule.low, rule.high, kind == "integer")
    if kind == "bool":
        if type(value) is not bool:
            _fail(path, "expected a boolean")
        return value
    if kind == "range":
        vals = [value, value] if type(value) in (int, float) else value
        vals = _vector(vals, path, 2, rule.low, rule.high)
        if vals[0] > vals[1]:
            _fail(path, "range minimum exceeds maximum")
        return vals
    if kind in ("sequence", "colors"):
        return _sequence(value, path, rule)
    if kind in ("vector2", "vector3", "color"):
        return _vector(value, path, 2 if kind == "vector2" else 3, rule.low, rule.high)
    if kind == "texture":
        if type(value) is str:
            if value == _BUILTIN_TEXTURE:
                return value
            match = _TEXTURE.fullmatch(value)
            if match and int(match[1]) <= 2**53 - 1:
                return value
        _fail(path, "expected a positive rbxassetid (<= 2^53-1) or the built-in sparkle texture")
    return _choice(value, path, rule.choices)


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("$", f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    _fail("$", f"non-finite JSON constant {value}")


def _load(spec: dict | str) -> dict:
    if type(spec) is str:
        try:
            if len(spec) > MAX_JSON_BYTES or len(spec.encode("utf-8")) > MAX_JSON_BYTES:
                _fail("$", "JSON byte budget exceeded")
            spec = json.loads(spec, object_pairs_hook=_pairs, parse_constant=_constant)
        except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
            raise VFXCompileError("$: invalid UTF-8 JSON or excessive nesting") from exc
        except ValueError as exc:
            if isinstance(exc, VFXCompileError):
                raise
            raise VFXCompileError("$: invalid JSON number") from exc
    return _object(spec, "$", {"version", "name", "effects", "camera_shake"}, {"version", "name", "effects"})


def validate_vfx_spec(spec: dict | str) -> dict:
    """Return a fresh, normalized JSON-compatible plan, or raise VFXCompileError.

    Unknown fields, code expressions, non-finite numbers, excessive budgets and
    ambiguous timelines are rejected, not silently clamped or dropped.
    """
    root = _load(spec)
    _number(root["version"], "$.version", 1, 1, True)
    name = root["name"]
    if type(name) is not str or not name:
        _fail("$.name", "expected a nonempty UTF-8 string of at most 128 bytes")
    try:
        if len(name) > 128 or len(name.encode("utf-8")) > 128:
            _fail("$.name", "name exceeds 128 UTF-8 bytes")
    except UnicodeError as exc:
        raise VFXCompileError("$.name: invalid UTF-8 string") from exc
    effects, ids, particles = [], set(), 0
    deadline = Fraction(0)
    for i, raw in enumerate(_array(root["effects"], "$.effects", 0, MAX_EFFECTS)):
        path = f"$.effects[{i}]"
        raw = _object(raw, path, {"id", "class", "at", "duration", "properties", "emit",
                                  "offset", "attachments", "tweens"}, {"id", "class"})
        ident = raw["id"]
        if type(ident) is not str or not _ID.fullmatch(ident) or ident in ids:
            _fail(path + ".id", "expected a unique ASCII identifier (1..48 characters)")
        ids.add(ident)
        cls = _choice(raw["class"], path + ".class", tuple(_RULES))
        at = _number(raw.get("at", 0), path + ".at", 0, 60)
        duration = _number(raw.get("duration", 0.25), path + ".duration", 0.01, 30)
        props = _object(raw.get("properties", {}), path + ".properties", set(_RULES[cls]))
        normalized = {k: _property(props.get(k, r.default), path + ".properties." + k, r)
                      for k, r in sorted(_RULES[cls].items())}
        item = {"id": ident, "class": cls, "at": at, "duration": duration, "properties": normalized}
        paired = cls in ("Beam", "Trail")
        if "attachments" in raw and not paired:
            _fail(path + ".attachments", "only Beam and Trail accept attachments")
        if "offset" in raw and (paired or cls == "Highlight"):
            _fail(path + ".offset", "offset is only for particles and point lights")
        if paired:
            points = _array(raw.get("attachments", [[0, 0, 0], [0, 1, 0]]), path + ".attachments", 2, 2)
            item["attachments"] = [_vector(v, path + f".attachments[{j}]", 3, -100, 100)
                                   for j, v in enumerate(points)]
            if item["attachments"][0] == item["attachments"][1]:
                _fail(path + ".attachments", "attachment positions must differ")
        elif cls != "Highlight":
            item["offset"] = _vector(raw.get("offset", [0, 0, 0]), path + ".offset", 3, -100, 100)
        if "emit" in raw and cls != "ParticleEmitter":
            _fail(path + ".emit", "emit is only for ParticleEmitter")
        tail = 0
        if cls == "ParticleEmitter":
            item["emit"] = _number(raw.get("emit", 0), path + ".emit", 0, 1000, True)
            particles += item["emit"] + normalized["Rate"] * duration
            tail = normalized["Lifetime"][1]
        elif cls == "Trail":
            tail = normalized["Lifetime"]
            if normalized["MinLength"] > normalized["MaxLength"]:
                _fail(path + ".properties.MinLength", "must not exceed MaxLength")
        elif cls == "Beam":
            minimum = max(len(normalized["Color"]), len(normalized["Transparency"])) - 1
            if "Segments" not in props:
                normalized["Segments"] = max(normalized["Segments"], minimum)
            elif normalized["Segments"] < minimum:
                _fail(path + ".properties.Segments", "too few segments for the sequence keypoints")
        tweens, intervals = [], {}
        for j, tween in enumerate(_array(raw.get("tweens", []), path + ".tweens", 0, 8)):
            p = path + f".tweens[{j}]"
            tween = _object(tween, p, {"at", "duration", "to", "easing", "direction", "reverses", "repeat_count"},
                            {"duration", "to"})
            t = _number(tween.get("at", 0), p + ".at", 0, 30)
            d = _number(tween["duration"], p + ".duration", 0.01, 30)
            repeats = _number(tween.get("repeat_count", 0), p + ".repeat_count", 0, 8, True)
            reverse = _property(tween.get("reverses", False), p + ".reverses", _N("bool"))
            start = Fraction(str(t))
            span = Fraction(str(d)) * (2 if reverse else 1) * (repeats + 1)
            end = start + span
            if end > Fraction(str(duration)):
                _fail(p, "tween extends beyond effect duration")
            goals = _object(tween["to"], p + ".to", _TWEENABLE[cls])
            if not goals:
                _fail(p + ".to", "expected at least one tween goal")
            for key in goals:
                for previous_start, previous_end in intervals.get(key, []):
                    if start < previous_end and previous_start < end:
                        _fail(p + ".to." + key, "overlapping tweens for this property")
                intervals.setdefault(key, []).append((start, end))
            tweens.append({"at": t, "duration": d, "span": float(span), "repeat_count": repeats, "reverses": reverse,
                           "easing": _choice(tween.get("easing", "Sine"), p + ".easing", ("Linear", "Sine", "Quad", "Cubic")),
                           "direction": _choice(tween.get("direction", "InOut"), p + ".direction", ("In", "Out", "InOut")),
                           "to": {k: _property(v, p + ".to." + k, _RULES[cls][k]) for k, v in sorted(goals.items())}})
        item["tweens"] = sorted(tweens, key=lambda t: t["at"])
        item["tail"] = tail
        effects.append(item)
        deadline = max(deadline, sum(Fraction(str(v)) for v in (at, duration, tail)))
    if particles > MAX_PARTICLES:
        _fail("$.effects", f"total particle budget exceeds {MAX_PARTICLES}")
    shake = None
    if "camera_shake" in root:
        p = "$.camera_shake"
        raw = _object(root["camera_shake"], p, {"at", "duration", "position", "rotation", "frequency", "seed"}, {"duration"})
        shake = {"at": _number(raw.get("at", 0), p + ".at", 0, 60),
                 "duration": _number(raw["duration"], p + ".duration", 0.01, 10),
                 "position": _vector(raw.get("position", [0, 0, 0]), p + ".position", 3, 0, 2),
                 "rotation": _vector(raw.get("rotation", [0, 0, 0]), p + ".rotation", 3, 0, 15),
                 "frequency": _number(raw.get("frequency", 12), p + ".frequency", 0.1, 60),
                 "seed": _number(raw.get("seed", 0), p + ".seed", 0, 2**31 - 1, True)}
        deadline = max(deadline, Fraction(str(shake["at"])) + Fraction(str(shake["duration"])))
    if not effects and shake is None:
        _fail("$", "at least one effect or camera_shake is required")
    return {"version": 1, "name": name, "effects": effects, "camera_shake": shake,
            "cleanup_after": float(deadline + Fraction(1, 20))}


def _quote(text: str) -> str:
    # JSON's \\uXXXX escapes are not Luau escapes. Fixed-width UTF-8 decimal bytes
    # also prevent an adjacent digit from extending a control-character escape.
    return '"' + ''.join(chr(b) if 32 <= b <= 126 and b not in (34, 92) else f"\\{b:03d}"
                         for b in text.encode("utf-8")) + '"'


def _literal(value: Any) -> str:
    if type(value) is str:
        return _quote(value)
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return "nil"
    if type(value) is list:
        return "{" + ", ".join(_literal(v) for v in value) + "}"
    return repr(value)


def _value(value: Any, rule: _Rule) -> str:
    kind = rule.kind
    if kind.startswith("enum:"):
        return "Enum." + kind.split(":")[1] + "." + value
    if kind in ("color", "vector2", "vector3", "range"):
        constructor = {"color": "Color3", "vector2": "Vector2", "vector3": "Vector3", "range": "NumberRange"}[kind]
        return constructor + ".new(" + ", ".join(_literal(v) for v in value) + ")"
    if kind in ("sequence", "colors"):
        constructor = "ColorSequence" if kind == "colors" else "NumberSequence"
        points = []
        for point in value:
            args = (_literal(point[0]) + ", " + _value(point[1], _N("color")) if kind == "colors"
                    else ", ".join(_literal(v) for v in point))
            points.append(constructor + "Keypoint.new(" + args + ")")
        return constructor + ".new({" + ", ".join(points) + "})"
    return _literal(value)


def compile_vfx(spec: dict | str) -> str:
    """Compile validated JSON to deterministic, self-contained Luau source."""
    data = validate_vfx_spec(spec)
    lines = ["return build({", "    name = " + _quote(data["name"]) + ",",
             "    cleanup_after = " + _literal(data["cleanup_after"]) + ",", "    effects = {"]
    for item in data["effects"]:
        cls = item["class"]
        lines.append("        {")
        for key in ("id", "class", "at", "duration", "tail", "emit"):
            if key in item:
                lines.append(f"            {key} = {_literal(item[key])},")
        for key in ("offset", "attachments"):
            if key in item:
                vals = item[key] if key == "attachments" else [item[key]]
                rendered = ", ".join(_value(v, _N("vector3")) for v in vals)
                lines.append(f"            {key} = " + ("{" + rendered + "}" if key == "attachments" else rendered) + ",")
        lines.append("            properties = {")
        for key, value in item["properties"].items():
            lines.append("                {" + _quote(key) + ", " + _value(value, _RULES[cls][key]) + "},")
        lines.extend(["            },", "            tweens = {"])
        for tween in item["tweens"]:
            fields = [f"{k} = {_literal(tween[k])}" for k in ("at", "duration", "span", "repeat_count", "reverses")]
            fields += ["easing = Enum.EasingStyle." + tween["easing"], "direction = Enum.EasingDirection." + tween["direction"]]
            goals = ", ".join(k + " = " + _value(v, _RULES[cls][k]) for k, v in tween["to"].items())
            lines.append("                {" + ", ".join(fields) + ", to = {" + goals + "}},")
        lines.extend(["            },", "        },"])
    lines.append("    },")
    if data["camera_shake"] is not None:
        lines.append("    camera_shake = {")
        for key, value in data["camera_shake"].items():
            lines.append(f"        {key} = {_literal(value)},")
        lines.append("    },")
    lines.append("})")
    return _RUNTIME + "\n".join(lines) + "\n"


_RUNTIME = '''--!nonstrict
-- Generated by STAR VFX compiler v1. Caller owns the part and optional adornee.
-- CameraShake is pure: sample using elapsed seconds; no camera/render binding.
local function build(config)
    local function cameraShake(elapsed)
        local s = config.camera_shake
        if not s or type(elapsed) ~= "number" or elapsed ~= elapsed
            or elapsed == math.huge or elapsed == -math.huge then
            return CFrame.new()
        end
        local t = elapsed - s.at
        if t <= 0 or t >= s.duration then return CFrame.new() end
        local envelope = math.sin(math.pi * t / s.duration) ^ 2
        local phase = t * s.frequency * 2 * math.pi
        local seed = s.seed % 10000
        local function wave(axis)
            return math.sin(phase * (1 + axis * 0.07) + seed + axis * 2.1) * envelope
        end
        return CFrame.new(s.position[1] * wave(1), s.position[2] * wave(2), s.position[3] * wave(3))
            * CFrame.Angles(math.rad(s.rotation[1]) * wave(4),
                math.rad(s.rotation[2]) * wave(5), math.rad(s.rotation[3]) * wave(6))
    end

    local function play(part, adornee)
        assert(typeof(part) == "Instance" and part:IsA("BasePart") and part.Parent ~= nil,
            "VFX Play requires a parented BasePart")
        adornee = adornee or part
        assert(typeof(adornee) == "Instance" and (adornee:IsA("BasePart") or adornee:IsA("Model"))
            and adornee.Parent ~= nil, "VFX adornee must be a parented BasePart or Model")
        local Debris = game:GetService("Debris")
        local TweenService = game:GetService("TweenService")
        local closed = false
        local owned, connections, pending, tweens = {}, {}, {}, {}

        local function destroy(item)
            if owned[item] then
                owned[item] = nil
                pcall(function() item:Destroy() end)
            end
        end
        local function finishTween(tween)
            if tweens[tween] then
                tweens[tween] = nil
                pcall(function() tween:Cancel() end)
                pcall(function() tween:Destroy() end)
            end
        end
        local function cleanup()
            if closed then return end
            closed = true
            for connection in pairs(connections) do
                connections[connection] = nil
                pcall(function() connection:Disconnect() end)
            end
            for thread in pairs(pending) do
                pending[thread] = nil
                if thread ~= coroutine.running() then pcall(task.cancel, thread) end
            end
            for tween in pairs(tweens) do finishTween(tween) end
            for item in pairs(owned) do destroy(item) end
        end
        local function later(seconds, action)
            local thread
            thread = task.delay(seconds, function()
                pending[thread] = nil
                if closed then return end
                if part.Parent == nil or adornee.Parent == nil then cleanup(); return end
                local ok, err = pcall(action)
                if not ok then
                    cleanup()
                    warn("STAR VFX stopped: " .. tostring(err))
                end
            end)
            pending[thread] = true
        end
        local function spawnEffect(effect)
            local nodes, activeTweens = {}, {}
            local function new(class)
                local item = Instance.new(class)
                owned[item] = true -- Own before ANY assignment or service call can fail.
                nodes[#nodes + 1] = item
                Debris:AddItem(item, effect.duration + effect.tail + 1)
                return item
            end
            local function attachment(position, suffix)
                local item = new("Attachment")
                item.Name = effect.id .. suffix
                item.Position = position
                item.Parent = part
                return item
            end
            local visual = new(effect.class)
            visual.Enabled = false
            visual.Name = config.name .. "/" .. effect.id
            for _, property in ipairs(effect.properties) do visual[property[1]] = property[2] end
            if effect.attachments then
                local a0 = attachment(effect.attachments[1], "_0")
                local a1 = attachment(effect.attachments[2], "_1")
                visual.Attachment0, visual.Attachment1 = a0, a1
                visual.Parent = a0
            elseif effect.class == "Highlight" then
                visual.Adornee = adornee
                visual.Parent = part
            else
                visual.Parent = attachment(effect.offset, "_origin")
            end
            visual.Enabled = effect.class ~= "ParticleEmitter" or visual.Rate > 0
            if effect.emit and effect.emit > 0 then visual:Emit(effect.emit) end
            for _, pulse in ipairs(effect.tweens) do
                later(pulse.at, function()
                    local info = TweenInfo.new(pulse.duration, pulse.easing, pulse.direction,
                        pulse.repeat_count, pulse.reverses, 0)
                    local tween = TweenService:Create(visual, info, pulse.to)
                    tweens[tween] = true
                    activeTweens[#activeTweens + 1] = tween
                    tween:Play()
                    later(pulse.span + 0.01, function() finishTween(tween) end)
                end)
            end
            later(effect.duration, function()
                visual.Enabled = false
            end)
            later(effect.duration + effect.tail + 0.01, function()
                -- Let a tween ending at duration deliver its final value first.
                for _, tween in ipairs(activeTweens) do finishTween(tween) end
                for i = #nodes, 1, -1 do destroy(nodes[i]) end
            end)
        end
        local ok, err = pcall(function()
            connections[part.Destroying:Connect(cleanup)] = true
            if adornee ~= part then connections[adornee.Destroying:Connect(cleanup)] = true end
            later(config.cleanup_after, cleanup)
            for _, effect in ipairs(config.effects) do
                later(effect.at, function() spawnEffect(effect) end)
            end
        end)
        if not ok then cleanup(); error(err, 0) end
        return cleanup
    end
    return {Play = play, CameraShake = cameraShake}
end

'''
