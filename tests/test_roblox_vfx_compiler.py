"""Offline schema/range regressions and eight full-output, factored goldens."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from star.roblox_vfx_compiler import VFXCompileError, compile_vfx, validate_vfx_spec

FIXTURES = Path(__file__).parent / "fixtures" / "vfx"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
NAMES = ("hit_spark", "heal_aura", "level_up_burst", "dash_trail", "explosion", "rain", "portal", "coin_pickup")


def spec(cls="ParticleEmitter", **effect):
    return {"version": 1, "name": "Test", "effects": [{"id": "effect", "class": cls, **effect}]}


@pytest.mark.parametrize("name", NAMES)
def test_full_output_golden(name):
    # Expected bytes come only from committed fixtures, never production constants.
    expected = (FIXTURES / "runtime.luau").read_text(encoding="utf-8")
    expected += (FIXTURES / (name + ".luau")).read_text(encoding="utf-8")
    assert compile_vfx(CASES[name]) == expected
    assert compile_vfx(json.dumps(CASES[name])) == expected


def test_exactly_eight_named_golden_cases():
    assert set(CASES) == set(NAMES)
    assert {p.stem for p in FIXTURES.glob("*.luau")} == {*NAMES, "runtime", "service_doubles"}


# Independent acceptance table: do not derive expected ranges from compiler rules.
RANGES = []
for cls in ("ParticleEmitter", "Beam", "Trail"):
    RANGES.extend((cls, key, kind, lo, hi) for key, kind, lo, hi in (
        ("LightEmission", "number", 0, 1), ("LightInfluence", "number", 0, 1),
        ("Transparency", "sequence", 0, 1), ("Color", "colors", 0, 1)))
for cls in ("ParticleEmitter", "Beam", "PointLight"):
    RANGES.append((cls, "Brightness", "number", 0, 20))
RANGES += [
    ("ParticleEmitter", "Rate", "number", 0, 400),
    ("ParticleEmitter", "Lifetime", "range", 0, 20),
    ("ParticleEmitter", "Speed", "range", 0, 200),
    ("ParticleEmitter", "Rotation", "range", -360, 360),
    ("ParticleEmitter", "RotSpeed", "range", -720, 720),
    ("ParticleEmitter", "Size", "sequence", 0, 100),
    ("ParticleEmitter", "Acceleration", "vector3", -1000, 1000),
    ("ParticleEmitter", "SpreadAngle", "vector2", 0, 180),
    ("ParticleEmitter", "Drag", "number", 0, 100),
    ("ParticleEmitter", "VelocityInheritance", "number", 0, 1),
    ("Beam", "Width0", "number", 0, 20), ("Beam", "Width1", "number", 0, 20),
    ("Beam", "CurveSize0", "number", -100, 100), ("Beam", "CurveSize1", "number", -100, 100),
    ("Beam", "Segments", "integer", 1, 100), ("Beam", "TextureLength", "number", .01, 100),
    ("Beam", "TextureSpeed", "number", -100, 100),
    ("Trail", "Lifetime", "number", 0, 10), ("Trail", "MinLength", "number", 0, 1),
    ("Trail", "MaxLength", "number", .01, 100), ("Trail", "WidthScale", "sequence", 0, 1),
    ("Trail", "TextureLength", "number", .01, 100),
    ("PointLight", "Range", "number", 0, 60), ("PointLight", "Color", "vector3", 0, 1),
    ("Highlight", "FillTransparency", "number", 0, 1),
    ("Highlight", "OutlineTransparency", "number", 0, 1),
    ("Highlight", "FillColor", "vector3", 0, 1), ("Highlight", "OutlineColor", "vector3", 0, 1),
]


def wrapped(kind, value):
    if kind in ("number", "integer"):
        return value
    if kind == "sequence":
        return [[0, value], [1, value]]
    if kind == "colors":
        return [[0, [value] * 3], [1, [value] * 3]]
    return [value] * (3 if kind == "vector3" else 2)


def ranged_spec(cls, key, kind, value):
    props = {"MinLength": 0} if cls == "Trail" else {}
    props[key] = wrapped(kind, value)
    return spec(cls, properties=props)


@pytest.mark.parametrize("cls,key,kind,low,high", RANGES)
@pytest.mark.parametrize("boundary", (0, 1))
def test_property_range_inclusive_boundaries(cls, key, kind, low, high, boundary):
    compile_vfx(ranged_spec(cls, key, kind, (low, high)[boundary]))


@pytest.mark.parametrize("cls,key,kind,low,high", RANGES)
@pytest.mark.parametrize("bad", ("under", "over", "nan", "infinity", "boolean", "string", "null"))
def test_property_range_rejects_bad_values(cls, key, kind, low, high, bad):
    value = {"under": low - 1, "over": high + 1, "nan": float("nan"), "infinity": float("inf"),
             "boolean": True, "string": "1", "null": None}[bad]
    with pytest.raises(VFXCompileError, match=key):
        compile_vfx(ranged_spec(cls, key, kind, value))


@pytest.mark.parametrize("cls,key,kind,low,high", RANGES)
def test_seeded_samples_stay_in_property_ranges(cls, key, kind, low, high):
    rng = random.Random(761)
    for _ in range(12):
        value = rng.randint(low, high) if kind == "integer" else rng.uniform(low, high)
        compile_vfx(ranged_spec(cls, key, kind, value))


@pytest.mark.parametrize("raw", [None, [], 1, True, b"{}", "not json", "[]", "null", "true",
    '{"version": 1, "version": 1}', '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}',
    "[" * 2000 + "]" * 2000, pytest.param(" " * 131073, id="oversize-json"), '"\\ud800"',
    '{"n":' + '1' * 5000 + '}', '{"version":1,"name":"x","effects":[{"id":"a","id":"b"}]}'])
def test_invalid_json_and_root_shapes(raw):
    with pytest.raises(VFXCompileError):
        compile_vfx(raw)


@pytest.mark.parametrize("field,value", [
    ("version", 0), ("version", 2), ("version", True), ("version", 1.0),
    ("name", ""), ("name", 9), ("name", "x" * 129), ("name", "é" * 65), ("name", "\ud800"),
    ("effects", None), ("effects", {}), ("effects", []),
    ("camera_shake", None), ("unknown", 1),
])
def test_root_validation_table(field, value):
    data = spec()
    data[field] = value
    with pytest.raises(VFXCompileError):
        compile_vfx(data)


@pytest.mark.parametrize("field", ["version", "name", "effects"])
def test_required_root_fields(field):
    data = spec()
    del data[field]
    with pytest.raises(VFXCompileError, match="missing field"):
        compile_vfx(data)


@pytest.mark.parametrize("changes", [
    {"id": ""}, {"id": "9bad"}, {"id": "a" * 49}, {"id": []}, {"id": "end);evil()"},
    {"class": "Script"}, {"class": []}, {"class": None}, {"at": -1}, {"at": 61},
    {"at": True}, {"duration": 0}, {"duration": 30.1}, {"duration": float("inf")},
    {"emit": -1}, {"emit": 1001}, {"emit": 1.5}, {"emit": True}, {"emit": 1.0},
    {"properties": []}, {"properties": {1: 1}}, {"properties": {"Parent": "workspace"}},
    {"properties": {"Enabled": True}}, {"properties": {"TimeScale": 0}},
    {"properties": {"Texture": 'rbxassetid://1";error("injected")'}},
    {"properties": {"Texture": "https://example.invalid/a.png"}},
    {"properties": {"Texture": "rbxassetid://0"}},
    {"properties": {"Texture": "rbxassetid://9007199254740992"}},
    {"properties": {"Speed": [2, 1]}}, {"properties": {"Lifetime": [1]}},
    {"properties": {"Lifetime": [0, 1, 2]}}, {"properties": {"LockedToPart": 1}},
    {"properties": {"EmissionDirection": "Up"}}, {"properties": {"Orientation": None}},
    {"offset": [1, 2]}, {"offset": [0, 0, 101]}, {"attachments": [[0, 0, 0], [0, 1, 0]]},
    {"tweens": {}}, {"tweens": [{"duration": .1, "to": {"Rate": 100}}]},
    {"run": "print('unsafe')"},
])
def test_effect_validation_table(changes):
    data = spec()
    data["effects"][0].update(changes)
    with pytest.raises(VFXCompileError):
        compile_vfx(data)


@pytest.mark.parametrize("cls,changes", [
    ("Beam", {"offset": [0, 0, 0]}), ("Highlight", {"offset": [0, 0, 0]}),
    ("PointLight", {"attachments": [[0, 0, 0], [1, 0, 0]]}),
    ("Trail", {"emit": 1}), ("Beam", {"emit": 1}), ("Highlight", {"emit": 0}),
    ("Trail", {"attachments": [[0, 0, 0], [0, 0, 0]]}),
    ("Beam", {"attachments": [[0, 0, 0]]}),
    ("Trail", {"properties": {"MinLength": 1, "MaxLength": .5}}),
    ("Beam", {"properties": {"Segments": 1.0}}),
    ("Highlight", {"properties": {"DepthMode": "ThroughWalls"}}),
    ("Trail", {"properties": {"TextureMode": "unknown"}}),
    ("Beam", {"properties": {"FaceCamera": "true"}}),
    ("PointLight", {"properties": {"Shadows": 1}}),
])
def test_class_specific_rejections(cls, changes):
    with pytest.raises(VFXCompileError):
        compile_vfx(spec(cls, **changes))


@pytest.mark.parametrize("key,points", [
    ("Size", [[.1, 1], [1, 1]]), ("Size", [[0, 1], [.9, 1]]),
    ("Size", [[0, 1], [.5, 1], [.5, 2], [1, 1]]), ("Size", [[0, 1], [True, 1]]),
    ("Size", [[0, 1, -1], [1, 1]]), ("Size", [[0, 0, 1], [1, 1]]),
    ("Size", [[0, 100, 1], [1, 1]]), ("Transparency", [[0, .5, .51], [1, 1]]),
    ("Size", [[0, 1, 0, 9], [1, 1]]), ("Size", [[0, 1]]),
    ("Size", [[i / 20, 1] for i in range(21)]),
    ("Color", [[0, [1, 1, 1]], [.5, [1, 0, 0]]]),
    ("Color", [[0, [1, 1, 1]], [1, [1, 0, 0]], [1, [0, 1, 0]]]),
    ("Color", [[0, [1, 1]], [1, [1, 1, 1]]]),
    ("Color", [[0, [1, 1, 1], 0], [1, [1, 1, 1]]]),
])
def test_sequence_validation_table(key, points):
    with pytest.raises(VFXCompileError, match=key):
        compile_vfx(spec(properties={key: points}))


def test_sequences_sorted_without_mutating_input_and_close_times_preserved():
    data = spec(properties={"Size": [[1, 0], [.5000000000000001, 2], [0, 0], [.5, 1]]})
    before = deepcopy(data)
    normalized = validate_vfx_spec(data)
    assert data == before
    assert [p[0] for p in normalized["effects"][0]["properties"]["Size"]] == [0, .5, .5000000000000001, 1]
    source = compile_vfx(data)
    assert source.index("NumberSequenceKeypoint.new(0.5, 1") < source.index("NumberSequenceKeypoint.new(0.5000000000000001, 2")


def test_twenty_keypoints_beam_segment_requirement():
    points = [[i / 19, i / 19] for i in range(20)]
    data = spec("Beam", properties={"Transparency": points})
    assert validate_vfx_spec(data)["effects"][0]["properties"]["Segments"] == 19
    data["effects"][0]["properties"]["Segments"] = 18
    with pytest.raises(VFXCompileError, match="Segments"):
        compile_vfx(data)


@pytest.mark.parametrize("tween", [
    {}, {"duration": .1, "to": {}}, {"duration": .1, "to": {"Shadows": True}},
    {"duration": .1, "to": {"Brightness": 21}},
    {"duration": .1, "to": {"Brightness": 1}, "at": -.1},
    {"duration": .3, "to": {"Brightness": 1}},
    {"duration": .1, "to": {"Brightness": 1}, "repeat_count": 9},
    {"duration": .1, "to": {"Brightness": 1}, "repeat_count": -1},
    {"duration": .1, "to": {"Brightness": 1}, "repeat_count": True},
    {"duration": .1, "to": {"Brightness": 1}, "reverses": 1},
    {"duration": .1, "to": {"Brightness": 1}, "easing": "Elastic"},
    {"duration": .1, "to": {"Brightness": 1}, "direction": "up"},
    {"duration": .1, "to": {"Brightness": 1}, "callback": "evil()"},
])
def test_tween_validation_table(tween):
    with pytest.raises(VFXCompileError):
        compile_vfx(spec("PointLight", tweens=[tween]))


def test_tween_order_overlap_and_exact_decimal_timeline():
    first = {"at": .1, "duration": .2, "to": {"Brightness": 1}}
    second = {"at": .3, "duration": .2, "to": {"Brightness": 0}}
    data = spec("PointLight", duration=.5, tweens=[second, first])
    assert [t["at"] for t in validate_vfx_spec(data)["effects"][0]["tweens"]] == [.1, .3]
    data["effects"][0]["tweens"][0]["at"] = .299
    with pytest.raises(VFXCompileError, match="overlapping"):
        compile_vfx(data)
    # No 1e-9 slack that silently admits an out-of-bounds tween.
    with pytest.raises(VFXCompileError, match="extends"):
        compile_vfx(spec("PointLight", duration=.3, tweens=[{"at": .2000000001, "duration": .1, "to": {"Range": 1}}]))


def test_reverse_repeat_budget_and_parallel_distinct_properties():
    tween = {"duration": .1, "repeat_count": 8, "reverses": True, "to": {"Brightness": 2}}
    data = spec("PointLight", duration=1.8, tweens=[tween, {"duration": 1.8, "to": {"Range": 4}}])
    assert validate_vfx_spec(data)["effects"][0]["tweens"][0]["span"] == 1.8
    data["effects"][0]["duration"] = 1.79
    with pytest.raises(VFXCompileError, match="extends"):
        compile_vfx(data)


def test_effect_and_particle_budgets_and_duplicate_ids():
    data = spec()
    data["effects"] *= 2
    with pytest.raises(VFXCompileError, match="unique"):
        compile_vfx(data)
    data["effects"] = [{"id": f"item{i}", "class": "PointLight"} for i in range(32)]
    compile_vfx(data)
    data["effects"].append({"id": "last", "class": "PointLight"})
    with pytest.raises(VFXCompileError, match="32"):
        compile_vfx(data)
    data = spec(duration=25, properties={"Rate": 400})
    compile_vfx(data)  # 10,000 total emitted particles, inclusive.
    data["effects"][0]["emit"] = 1
    with pytest.raises(VFXCompileError, match="particle budget"):
        compile_vfx(data)
    data = spec("PointLight", duration=30, tweens=[{"at": i, "duration": .1, "to": {"Range": i}} for i in range(9)])
    with pytest.raises(VFXCompileError, match="8"):
        compile_vfx(data)


@pytest.mark.parametrize("field,value", [("duration", 0), ("duration", 11), ("at", -1), ("at", 61),
    ("position", [2.01, 0, 0]), ("rotation", [0, -1, 0]), ("rotation", [16, 0, 0]),
    ("frequency", 0), ("frequency", 61), ("frequency", float("nan")),
    ("seed", -1), ("seed", 2**31), ("seed", 1.0), ("seed", True), ("callback", "evil()")])
def test_camera_shake_validation_table(field, value):
    data = {"version": 1, "name": "Shake", "effects": [], "camera_shake": {"duration": .5, field: value}}
    with pytest.raises(VFXCompileError):
        compile_vfx(data)


def test_camera_only_plan_limits_and_cleanup_uses_latest_tail():
    data = {"version": 1, "name": "Shake", "effects": [], "camera_shake": {
        "at": 60, "duration": 10, "position": [2, 2, 2], "rotation": [15, 15, 15], "frequency": 60, "seed": 2**31-1}}
    assert validate_vfx_spec(data)["cleanup_after"] == 70.05
    data = spec(at=60, duration=30, properties={"Lifetime": [0, 20]})
    data["effects"].append({"id": "trail", "class": "Trail", "at": 60, "duration": 30, "properties": {"Lifetime": 10}})
    assert validate_vfx_spec(data)["cleanup_after"] == 110.05


def test_normalization_is_detached_and_compilation_deterministic():
    data = deepcopy(CASES["heal_aura"])
    before = deepcopy(data)
    one = compile_vfx(data)
    normalized = validate_vfx_spec(data)
    normalized["effects"][0]["properties"]["Color"][0][1][0] = .99
    normalized["effects"][0]["offset"][0] = 99
    assert data == before
    assert compile_vfx(data) == one
    reordered = json.loads(json.dumps(data, sort_keys=True))
    assert compile_vfx(reordered) == one
    assert compile_vfx(spec(properties={"Rate": 1.0})) == compile_vfx(spec(properties={"Rate": 1}))


def test_luau_safe_utf8_and_control_escapes_and_no_user_code_slots():
    data = spec()
    data["name"] = '"\\\n\x001é★; error("not code") --'
    source = compile_vfx(data)
    assert 'name = "\\034\\092\\010\\0001\\195\\169\\226\\152\\133; error(\\034not code\\034) --"' in source
    assert "\\u00e9" not in source
    with pytest.raises(VFXCompileError):
        compile_vfx(spec(properties={"Size": "NumberSequence.new(1)"}))
    compile_vfx(spec(properties={"Texture": "rbxassetid://9007199254740991"}))


def test_hostile_python_shapes_fail_as_validation_errors():
    data = spec()
    data["effects"][0]["properties"] = {object(): 1}
    with pytest.raises(VFXCompileError):
        compile_vfx(data)
    data = spec(properties={"Rate": 10**10000})
    with pytest.raises(VFXCompileError):
        compile_vfx(data)
    cycle = []
    cycle.extend([cycle, cycle])
    with pytest.raises(VFXCompileError):
        compile_vfx(spec(properties={"Size": cycle}))


def test_compiler_is_offline_and_does_not_read_write_or_launch(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("I/O attempted")
    import builtins
    import socket
    import subprocess
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for data in CASES.values():
        assert compile_vfx(data).endswith("})\n")
