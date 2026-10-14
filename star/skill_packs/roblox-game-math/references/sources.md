# Sources and verification status

Official documentation reviewed for this pack. The API names below were **not**
verified with the knowledge service /api-lookup during authoring; no such service
was called. This is not a claim of Studio execution or a passed evaluation gate.
The mathematical derivations and compact examples are original, not copied code.

- Vector3: Magnitude, Unit, Dot, Cross, xAxis, yAxis, zero; distinguish a direction
  from a displacement and guard normalization.
  https://create.roblox.com/docs/reference/engine/datatypes/Vector3
- CFrame: multiplication, lookAt, LookVector, ToObjectSpace, PointToWorldSpace,
  VectorToWorldSpace and Lerp; the forward axis is local -Z.
  https://create.roblox.com/docs/reference/engine/datatypes/CFrame
- Coordinate-frame composition and world/local coordinate examples:
  https://create.roblox.com/docs/workspace/cframes
- TweenService: GetValue(alpha, easingStyle, easingDirection); the skill uses
  an engine curve evaluation, not an invented tween API.
  https://create.roblox.com/docs/reference/engine/classes/TweenService
- EasingStyle: Linear, Sine, Back, Quad, Quart, Quint, Bounce, Elastic,
  Exponential, Circular and Cubic.
  https://create.roblox.com/docs/reference/engine/enums/EasingStyle
- Raycasting: Workspace:Raycast(origin, direction, raycastParams); direction
  encodes the cast's length. Geometry functions are not substitutes for engine
  collision filtering or a streamed-world collision query.
  https://create.roblox.com/docs/workspace/raycasting
- Random: new(seed), NextNumber and NextInteger. The explicitly specified
  integer recurrence in math.md is a separate portable teaching example, not a
  reproduction of the engine's Random implementation.
  https://create.roblox.com/docs/reference/engine/datatypes/Random
- RunService: Heartbeat(deltaTime) supplies measured frame time; fixed-step
  accounting and the chosen backlog policy are application mathematics.
  https://create.roblox.com/docs/reference/engine/classes/RunService
- Luau math library: abs, sqrt, cos, exp, floor, clamp, random/randomseed and
  modulo versus fmod; the standalone numerical examples need no engine APIs.
  https://luau.org/library/

The spring formula solves y'' + 2*omega*y' + omega^2*y = 0 with constant target:
y(t)=(y0+(v0+omega*y0)*t)*exp(-omega*t). Differentiation gives the velocity used
in the pack. Bezier functions use Bernstein coefficients; projectile functions
integrate constant acceleration twice. These formulas are not Roblox API calls.

The separate math catalog contains executable reference and counterexample
fixtures. Numerical checks are not visual QA, an engine physics simulation, or
proof that enabling this pack improves model answers. Leave it OFF by default.
