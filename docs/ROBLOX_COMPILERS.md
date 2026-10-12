# Roblox compilers

## VFX compiler v1

`star.roblox_vfx_compiler` is a standalone, standard-library-only Python compiler.
It has no application, agent, Studio, network, filesystem or asset-download wiring.
It returns one deterministic Luau ModuleScript, not a claim of an executed or
visually approved effect. No scripts, callbacks, instance paths or raw Luau
expressions can be supplied in the JSON.

```python
from star.roblox_vfx_compiler import compile_vfx, validate_vfx_spec, VFXCompileError

spec = {
    "version": 1,
    "name": "Hit spark",
    "effects": [{
        "id": "spark", "class": "ParticleEmitter", "duration": 0.05, "emit": 12,
        "properties": {
            "Lifetime": [0.15, 0.35], "Speed": [8, 18],
            "Color": [[0, [1, 0.8, 0.3]], [1, [1, 0.3, 0.1]]],
            "Size": [[0, 0.25], [1, 0]], "Transparency": [[0, 0], [1, 1]]
        }
    }]
}
source = compile_vfx(spec)       # Also accepts a UTF-8 JSON string; no file reads.
plan = validate_vfx_spec(spec)   # Fresh normalized plan; does not mutate spec.
assert plan["cleanup_after"] == 0.45
```

The caller chooses where to save `source` and reviews it before installation.
`VFXCompileError` subclasses `ValueError` and includes a JSON-style error path.
The normalized plan contains defaults and internal `tail`, tween `span` and
`cleanup_after` fields; it is diagnostic output, **not** another input schema.
Compile the original specification, not the normalized plan.

### Generated ModuleScript API

```lua
local Effect = require(pathToReviewedModule)
local cancel = Effect.Play(character.HumanoidRootPart, character)
-- Optional explicit teardown, for example when the ability is interrupted:
cancel()
cancel() -- Idempotent.
```

`Play(part, adornee?)` requires a parented `BasePart`; the optional adornee must
be a parented `BasePart` or `Model`, and defaults to `part`. Rendering requires
appropriate placement in the world. The caller owns those inputs and chooses
whether to invoke the module on the client or server. The compiler adds no
remotes, gameplay authority, damage, replication protocol or client binding.
Each call returns its own cancellation function. Multiple calls have independent
resource ownership; they do not share mutable effect state.

`CameraShake(elapsedSeconds)` is a pure function returning a `CFrame` offset.
It does not inspect a clock, random generator, camera, service or render event.
For absent shake configuration, invalid/non-finite time, or time outside the
configured interval, it returns identity. Inside the interval, seeded sine waves
with a smooth sine-squared envelope produce bounded per-axis translations and
Euler angles. `position` is in studs; `rotation` is in degrees. Equal inputs give
equal outputs; seeds are reduced modulo 10000, so distinct seeds can coincide.

The caller's existing camera controller may apply
`camera.CFrame = unshakenCFrame * Effect.CameraShake(elapsedSeconds)` each frame.
Use a fresh unshaken camera transform rather than accumulating offsets. The
caller supplies elapsed time, owns and disconnects any render connection, and
stops sampling/resets its camera when cancelling. `cancel()` owns the instance
playback only; it deliberately does not mutate the pure camera function.

### Root and timeline schema

Unknown fields are rejected at every level. Numbers must be finite, with no
boolean-to-number coercion. Integer fields require JSON integers (`1`, not
`1.0`). Duplicate JSON keys, invalid UTF-8, malformed shapes and out-of-range
values are errors; nothing is silently clamped, repaired or ignored.

| Field | Contract |
| --- | --- |
| `version` | Required integer `1`. |
| `name` | Required nonempty UTF-8 string, at most 128 bytes. Escaped as data in Luau. |
| `effects` | Required array of 0-32 effects. At least one effect or camera shake is required. |
| `camera_shake` | Optional object described below. Explicit `null` is rejected. |

JSON text has a 131072-byte input budget. For a Python dictionary input, the
structural limits apply directly; the compiler does not serialize it to measure
a text budget. Only built-in JSON-compatible types are accepted. Object key
order does not change output; effect array order is retained for scheduling ties.

Each effect requires unique `id` matching `[A-Za-z][A-Za-z0-9_-]{0,47}` and
`class` in `ParticleEmitter`, `Beam`, `Trail`, `PointLight`, `Highlight`.

| Field | Range / default |
| --- | --- |
| `at` | 0-60 seconds from `Play`, default 0. |
| `duration` | 0.01-30 seconds of active emission/visibility, default 0.25. |
| `properties` | Optional allowlisted property object; omitted properties receive the defaults below. |
| `emit` | ParticleEmitter only: integer 0-1000, default 0. A burst in addition to `Rate`. |
| `offset` | ParticleEmitter/PointLight only: local `[x,y,z]`, each -100 to 100, default `[0,0,0]`. |
| `attachments` | Beam/Trail only: two distinct local `[x,y,z]` positions, each component -100 to 100; default `[[0,0,0],[0,1,0]]`. |
| `tweens` | Array of 0-8 tween objects, default empty. |

The per-plan estimated particle budget is
`sum(emit + Rate * duration) <= 10000`. This is a static estimate, not a frame-rate
promise or a global cap on concurrent plays. Callers must rate-limit abilities
and select smaller budgets for mobile and crowded scenes. A zero `Rate` makes a
burst-only emitter; `Rate` and `emit` both zero is valid but emits nothing.
There is no infinite emitter, unlimited lifetime, time-scale change or loop.

### Value types and property ranges

These are **v1 compiler limits and defaults**, not a complete Roblox API or a
claim that every range endpoint is a recommended artistic/performance setting.
Properties not listed here are rejected, including `Parent`, `Enabled`,
`Adornee`, raw attachment references, script source and particle `TimeScale`.

`RGB` is `[r,g,b]` with components in 0-1, not 0-255 or hex. `NR` is a scalar or
`[minimum,maximum]` with minimum <= maximum. `NS` is a constant scalar or 2-20
keypoints `[time,value,envelope?]`, with envelope default 0. `CS` is constant RGB
or 2-20 `[time,RGB]` keypoints. The compiler sorts keypoints without changing
input, then requires unique finite times in 0-1 and endpoints **exactly** 0 and 1.
Missing endpoints and duplicates are errors. `NS` envelopes must be nonnegative
and both `value-envelope` and `value+envelope` must fit the property's range.

Shared ParticleEmitter/Beam/Trail properties:

| Property | Type / bounds | Default |
| --- | --- | --- |
| `Color` | CS, RGB components 0-1 | white |
| `Transparency` | NS, values 0-1 | 0 |
| `LightEmission`, `LightInfluence` | number 0-1 | 0 |
| `Texture` | Built-in sparkle below, or positive `rbxassetid://N`, N <= 2^53-1 | built-in sparkle |
| `Brightness` | ParticleEmitter/Beam only, number 0-20 | 1 |

The one built-in texture is `rbxasset://textures/particles/sparkles_main.dds`.
Asset ID syntax is checked, **not** existence, ownership, licensing, permission
or availability. General URLs, leading-zero/negative IDs and expression strings
are rejected. Texture loading/rendering is for a later real-engine review.

| ParticleEmitter property | Type / bounds | Default |
| --- | --- | --- |
| `Rate` | number 0-400 | 0 |
| `Lifetime` | NR 0-20 seconds | [0.5,1] |
| `Speed` | NR 0-200 | 0 |
| `Rotation` | NR -360 to 360 degrees | 0 |
| `RotSpeed` | NR -720 to 720 degrees/second | 0 |
| `Size` | NS 0-100 | 1 |
| `Acceleration` | vector3, each -1000 to 1000 | [0,0,0] |
| `SpreadAngle` | vector2, each 0-180 degrees | [0,0] |
| `Drag` | number 0-100 | 0 |
| `VelocityInheritance` | number 0-1 | 0 |
| `LockedToPart` | boolean | false |
| `EmissionDirection` | Top, Bottom, Front, Back, Left, Right | Top |
| `Orientation` | FacingCamera, FacingCameraWorldUp, VelocityParallel, VelocityPerpendicular | FacingCamera |

| Beam property | Type / bounds | Default |
| --- | --- | --- |
| `Width0`, `Width1` | number 0-20 | 1 |
| `CurveSize0`, `CurveSize1` | number -100 to 100 | 0 |
| `Segments` | integer 1-100 | 10, raised for sequence keypoints |
| `FaceCamera` | boolean | true |
| `TextureLength` | number 0.01-100 | 1 |
| `TextureSpeed` | number -100 to 100 | 1 |
| `TextureMode` | Wrap, Static, Stretch | Wrap |

Beam segments must be at least `max(Color keypoints, Transparency keypoints)-1`.
An explicitly smaller `Segments` value is rejected; only the default is raised.

| Trail property | Type / bounds | Default |
| --- | --- | --- |
| `Lifetime` | number 0-10 seconds | 0.5 |
| `MinLength` | number 0-1, <= MaxLength | 0.1 |
| `MaxLength` | number 0.01-100 (no unlimited zero mode) | 10 |
| `WidthScale` | NS 0-1 | 1 |
| `FaceCamera` | boolean | true |
| `TextureLength` | number 0.01-100 | 1 |
| `TextureMode` | Wrap, Static, Stretch | Stretch |

| Other class | Property | Type / bounds | Default |
| --- | --- | --- | --- |
| PointLight | `Brightness` | number 0-20 | 1 |
| PointLight | `Range` | number 0-60 | 8 |
| PointLight | `Color` | RGB | white |
| PointLight | `Shadows` | boolean | false |
| Highlight | `FillColor`, `OutlineColor` | RGB | white |
| Highlight | `FillTransparency` | number 0-1 | 0.5 |
| Highlight | `OutlineTransparency` | number 0-1 | 0 |
| Highlight | `DepthMode` | Occluded, AlwaysOnTop | Occluded |

### Tweens

A tween requires `duration` (0.01-30 seconds) and a nonempty `to` object.
Optional fields: `at` (0-30 seconds relative to **that effect's start**, default
0), `easing` (Linear/Sine/Quad/Cubic, default Sine), `direction` (In/Out/InOut,
default InOut), `reverses` (boolean, default false), `repeat_count` (integer 0-8,
default 0, additional cycles). Overshooting easing styles are intentionally absent.

The full span is `duration * (reverses ? 2 : 1) * (repeat_count + 1)`.
`at + span` must fit the effect's duration. Decimal timing comparisons are exact,
so `.1 + .2` may end at `.3` without a rounding-slack exception. Same-property
overlapping intervals are rejected; adjacent intervals and simultaneous tweens
of different properties are allowed. Goals use the same property validators.

| Class | Tweenable properties |
| --- | --- |
| ParticleEmitter | Brightness, LightEmission, LightInfluence |
| Beam | Brightness, LightEmission, LightInfluence, Width0, Width1, CurveSize0, CurveSize1, TextureSpeed, TextureLength |
| Trail | LightEmission, LightInfluence, TextureLength |
| PointLight | Brightness, Range, Color |
| Highlight | FillColor, OutlineColor, FillTransparency, OutlineTransparency |

No tween can change class, lifetime, emission budget, booleans, enums or sequences.
Use multiple timed effects for successive bursts, and NS/CS for per-particle
appearance changes rather than trying to tween those datatypes.

### Camera configuration

`camera_shake` requires `duration` in 0.01-10 seconds. Optional `at`: 0-60, default
0; `position`: three amplitudes 0-2 studs, default zeros; `rotation`: three
amplitudes 0-15 degrees, default zeros; `frequency`: 0.1-60, default 12; `seed`:
integer 0-(2^31-1), default 0. No camera input, path, script or callback is accepted.
See the API section for caller-owned camera integration and cancellation.

### Ownership and timed teardown

All instances are registered as owned immediately after construction, before
property writes or service calls. Visuals start disabled, receive all properties
and correct attachments/adornee, then activate or emit. Beam/Trail attachments
are separate children of the caller's part; particles/lights receive an origin
attachment. No caller instance is added to the owned set or Debris.

Each effect stops emission/visibility after its active duration. ParticleEmitter
retirement allows its maximum Lifetime tail; Trail allows its Lifetime tail;
other classes have no tail. Node retirement occurs after `duration + tail + .01`.
Tween disposal has a small post-span grace, and retirement cancels any remaining
tweens before removing their target. In particular, stopping visibility does
not prematurely cancel a tween whose final value is due at the same boundary.
The plan's final cleanup is the latest effect end including its tail, or the
shake end, plus .05 seconds. Those are requested scheduler times, not exact
frame deadlines: engine load can delay callbacks or truncate a late tween.

Every owned instance also has a Debris fallback at `duration + tail + 1` after
creation. This fallback is independent of the calling script's later execution,
but Roblox's shared Debris queue can expire items early under load. There is no
promise that an effect remains visible for exactly its requested lifetime.
Explicit cancellation and automatic cleanup disconnect the owned Destroying
connections, cancel outstanding task timers, cancel/destroy tweens and destroy
owned instances. Calls are idempotent; they do not destroy the part or adornee.
Debris's engine-owned queue entries may remain until their deadline after an
already-destroyed instance is cancelled.

Destroying the part or a separate adornee triggers teardown. Detachment is also
checked before delayed actions. Setup errors clean resources and rethrow;
delayed-action errors clean resources and warn. Individual teardown operations
are protected so one failure does not prevent attempts to release other objects.
This does not grant sandbox permissions or guarantee recovery from arbitrary
engine failures. Callers should not mutate or reuse generated child instances.

### Offline tests and real-engine acceptance

```sh
python -m pytest -q tests/test_roblox_vfx_compiler.py tests/test_roblox_vfx_runtime.py
python -m pytest -q
python -m compileall -q star main.py
```

`tests/fixtures/vfx/cases.json` contains the eight goldens: hit spark, heal aura,
level-up burst, dash trail, explosion, rain, portal and coin pickup. Expected
complete output is factored into an independently committed `runtime.luau` plus
each named configuration tail; tests compare every output byte, not selected
substrings or hashes. The test never imports the production runtime as its
expected value. See the fixture README for inspection and update policy.

The validation suite includes independent range tables, sequence sorting and
endpoints, bounded timelines, malformed JSON, injection/UTF-8, non-mutation and
I/O rejection. Optional runtime tests execute the **unchanged** generated code
with an installed Lua 5.4 shared library and deterministic service doubles. They
exercise resource ownership, cancellation, faults, scheduled goals, particle
tails, pure camera bounds and deliberately broken cleanup mutations. They skip
explicitly if that library is unavailable; no dependency is downloaded by tests.

Lua 5.4 compatibility is **not** native Luau typechecking, Roblox Studio execution,
rendering, actual TweenService interpolation, texture verification or GPU/mobile
performance testing. Real-engine acceptance must cover all eight authored
fixtures, attachment placement/motion, effect fades, cancellation, character
removal, camera-controller integration and concurrent-play budgets. Nothing in
this compiler automatically enables a feature or changes evaluation fixtures.

### API references

Contracts were checked against Roblox's primary reference documentation. The
numeric/compiler resource caps above are local design choices where the API
permits a broader domain; they are not inferred engine guarantees.

- [ParticleEmitter](https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter), [Beam](https://create.roblox.com/docs/reference/engine/classes/Beam), [Trail](https://create.roblox.com/docs/reference/engine/classes/Trail)
- [PointLight](https://create.roblox.com/docs/reference/engine/classes/PointLight), [Highlight](https://create.roblox.com/docs/reference/engine/classes/Highlight)
- [NumberSequence](https://create.roblox.com/docs/reference/engine/datatypes/NumberSequence), [ColorSequence](https://create.roblox.com/docs/reference/engine/datatypes/ColorSequence)
- [TweenService](https://create.roblox.com/docs/reference/engine/classes/TweenService), [TweenInfo](https://create.roblox.com/docs/reference/engine/datatypes/TweenInfo)
- [Debris](https://create.roblox.com/docs/reference/engine/classes/Debris), [task](https://create.roblox.com/docs/reference/engine/libraries/task)
