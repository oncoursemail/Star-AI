"""Execute unchanged generated code with Lua 5.4 + deterministic Roblox doubles.

Optional compatibility coverage, not native Luau checking or Studio rendering.
No downloaded executables, network, keyring or GPU are required.
"""
import ctypes
import ctypes.util
import json
from pathlib import Path

import pytest

from star.roblox_vfx_compiler import compile_vfx

FIXTURES = Path(__file__).parent / "fixtures" / "vfx"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
DOUBLES = (FIXTURES / "service_doubles.luau").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def run_lua():
    name = ctypes.util.find_library("lua5.4")
    if not name:
        pytest.skip("optional Lua 5.4 shared library unavailable; not a native Luau test")
    lib = ctypes.CDLL(name)
    lib.luaL_newstate.restype = ctypes.c_void_p
    lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lib.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
    lib.luaL_loadbufferx.restype = ctypes.c_int
    lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
    lib.lua_pcallk.restype = ctypes.c_int
    lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    lib.lua_tolstring.restype = ctypes.c_char_p
    lib.lua_close.argtypes = [ctypes.c_void_p]

    def execute(source):
        state = lib.luaL_newstate()
        assert state, "failed to allocate Lua state"
        try:
            lib.luaL_openlibs(state)
            data = source.encode("utf-8")
            result = lib.luaL_loadbufferx(state, data, len(data), b"vfx-compatibility", b"t")
            if result == 0:
                result = lib.lua_pcallk(state, 0, 0, 0, 0, None)
            if result != 0:
                message = lib.lua_tolstring(state, -1, None)
                raise AssertionError(message.decode("utf-8", errors="replace") if message else "Lua failed")
        finally:
            lib.lua_close(state)
    return execute


def execute(run, data, assertions, *, mutation=None):
    source = compile_vfx(data)
    if mutation:
        old, new = mutation
        assert old in source
        source = source.replace(old, new, 1)
    run(DOUBLES + "\nlocal Effect = (function()\n" + source + "\nend)()\n" + assertions)


@pytest.mark.parametrize("name", tuple(CASES))
def test_all_eight_generated_effects_lifecycle(run_lua, name):
    execute(run_lua, CASES[name], '''
        local cancel = Effect.Play(part)
        advance(1000)
        assert(#objects > baseline)
        assert(#warnings == 0, warnings[1])
        clean()
        assert(not part._destroyed and part.Parent == world)
        cancel(); cancel()
        clean()
    ''')


def test_cancel_before_delayed_creation_is_idempotent(run_lua):
    execute(run_lua, CASES["portal"], '''
        local cancel = Effect.Play(part)
        cancel(); cancel()
        advance(1000)
        assert(#objects == baseline and #warnings == 0)
        clean()
    ''')


def test_cancel_active_tweens_and_instances_without_recreation(run_lua):
    execute(run_lua, CASES["heal_aura"], '''
        local cancel = Effect.Play(part)
        advance(0.1)
        assert(find("PointLight") and #allTweens == 1 and allTweens[1].playing)
        local count = #objects
        cancel(); clean()
        advance(1000)
        assert(#objects == count and not part._destroyed and #warnings == 0)
        clean()
    ''')


def test_staggered_burst_parenting_disable_and_tail_retirement(run_lua):
    data = {"version": 1, "name": "Tail", "effects": [{"id": "spark", "class": "ParticleEmitter", "at": 1,
        "duration": .25, "emit": 7, "properties": {"Rate": 4, "Lifetime": 1}}]}
    execute(run_lua, data, '''
        local cancel = Effect.Play(part)
        advance(0.99); assert(#objects == baseline)
        advance(1)
        local emitter = find("ParticleEmitter")
        assert(emitter._emitted == 7 and emitter.Enabled and emitter.Parent:IsA("Attachment"))
        assert(emitter.Parent.Parent == part)
        advance(1.25); assert(not emitter.Enabled and not emitter._destroyed)
        advance(2.24); assert(not emitter._destroyed)
        advance(2.27); assert(emitter._destroyed)
        advance(2.3); clean()
        assert(not part._destroyed)
    ''')


@pytest.mark.parametrize("target", ("part", "adornee"))
def test_destroying_caller_target_cancels_every_resource(run_lua, target):
    execute(run_lua, CASES["level_up_burst"], '''
        local adornee = Instance.new("Model")
        adornee.Parent = world
        baseline = #objects
        local cancel = Effect.Play(part, adornee)
        advance(0.1)
        assert(find("Highlight").Adornee == adornee)
        TARGET:Destroy()
        clean()
        advance(1000)
        clean()
        assert(#warnings == 0)
    '''.replace("TARGET", target))


def test_detached_parent_and_bad_runtime_arguments(run_lua):
    execute(run_lua, CASES["hit_spark"], '''
        assert(not pcall(Effect.Play, nil))
        assert(not pcall(Effect.Play, {}))
        assert(not pcall(Effect.Play, world))
        assert(not pcall(Effect.Play, part, world))
        part.Parent = nil
        assert(not pcall(Effect.Play, part))
        assert(#objects == baseline and services == 0)
        part.Parent = world
        local cancel = Effect.Play(part)
        advance(0)
        part.Parent = nil
        advance(1000)
        clean()
        assert(not part._destroyed)
    ''')


@pytest.mark.parametrize("fault", ("failNewAt = baseline + 2", 'failProperty = "Color"',
    "failDebris = true", "failTweenCreate = true", "failTweenPlay = true"))
def test_delayed_setup_faults_are_visible_and_cleaned(run_lua, fault):
    execute(run_lua, CASES["heal_aura"], fault + '''
        local cancel = Effect.Play(part)
        advance(1000)
        assert(#warnings == 1, "fault was not reported")
        assert(not part._destroyed)
        clean()
    ''')


@pytest.mark.parametrize("fault", ("failConnect = true", "failDelay = true"))
def test_synchronous_setup_faults_raise_and_clean(run_lua, fault):
    execute(run_lua, CASES["portal"], fault + '''
        assert(not pcall(Effect.Play, part))
        assert(#objects == baseline)
        advance(1000)
        clean()
    ''')


def test_camera_shake_is_deterministic_bounded_and_has_no_side_effects(run_lua):
    data = {"version": 1, "name": "Camera", "effects": [], "camera_shake": {
        "at": .5, "duration": 1, "position": [2, 1, .5], "rotation": [15, 10, 5], "frequency": 60, "seed": 1234}}
    execute(run_lua, data, '''
        local function zero(value)
            for i=1,6 do assert(value[i] == 0) end
        end
        zero(Effect.CameraShake(-1)); zero(Effect.CameraShake(0.5)); zero(Effect.CameraShake(1.5))
        zero(Effect.CameraShake(math.huge)); zero(Effect.CameraShake(-math.huge))
        zero(Effect.CameraShake(0/0)); zero(Effect.CameraShake({})); zero(Effect.CameraShake(true))
        local bounds = {2,1,.5,math.rad(15),math.rad(10),math.rad(5)}
        local changed = false
        for n=1,999 do
            local a, b = Effect.CameraShake(.5+n/1000), Effect.CameraShake(.5+n/1000)
            for i=1,6 do
                assert(a[i] == b[i] and math.abs(a[i]) <= bounds[i])
                if a[i] ~= 0 then changed = true end
            end
        end
        assert(changed and #objects == baseline and services == 0 and #jobs == 0 and #links == 0)
    ''')


def test_absent_camera_shake_returns_identity_and_caller_name_is_data(run_lua):
    data = {"version": 1, "name": '"\\\n\x001é★; error("not code") --', "effects": [{"id": "end", "class": "PointLight"}]}
    execute(run_lua, data, '''
        for i=1,6 do assert(Effect.CameraShake(.1)[i] == 0) end
        local cancel = Effect.Play(part)
        advance(0)
        local name = find("PointLight").Name
        assert(string.sub(name, 1, 1) == '"')
        assert(string.find(name, "error", 1, true) and string.find(name, "é★", 1, true))
        assert(string.byte(name, 4) == 0)
        cancel(); clean()
    ''')


def test_two_simultaneous_plays_have_isolated_ownership(run_lua):
    execute(run_lua, CASES["hit_spark"], '''
        local cancelA = Effect.Play(part)
        local cancelB = Effect.Play(part)
        advance(0)
        local count = #objects
        cancelA()
        local alive = 0
        for i=baseline+1,#objects do if not objects[i]._destroyed then alive=alive+1 end end
        assert(alive == 2)
        cancelB(); clean()
        advance(1000)
        assert(#objects == count and not part._destroyed)
    ''')


def test_mutation_removed_initial_disable_is_detected(run_lua):
    execute(run_lua, CASES["hit_spark"], '''
        local cancel = Effect.Play(part)
        advance(1000)
        assert(#warnings == 1 and string.find(warnings[1], "configured disabled", 1, true))
        clean()
    ''', mutation=('            visual.Enabled = false\n', ''))


def test_mutation_removed_connection_cleanup_is_detected(run_lua):
    with pytest.raises(AssertionError, match="leaked connection"):
        execute(run_lua, CASES["hit_spark"], '''
            local cancel = Effect.Play(part)
            advance(1000)
            clean()
        ''', mutation=('                pcall(function() connection:Disconnect() end)', '                -- deliberately broken'))


@pytest.mark.parametrize("start,duration", [(0, .5), (.2, .3)])
def test_tween_reaches_goal_at_active_end_before_retirement(run_lua, start, duration):
    data = {"version": 1, "name": "Final tween", "effects": [{"id": "light", "class": "PointLight",
        "duration": .5, "tweens": [{"at": start, "duration": duration, "to": {"Brightness": 9}}]}]}
    execute(run_lua, data, '''
        local cancel = Effect.Play(part)
        advance(.5)
        local light = find("PointLight")
        assert(light.Brightness == 9, "tween cancelled before its terminal goal")
        assert(not light.Enabled and not light._destroyed)
        advance(1); clean()
    ''')
