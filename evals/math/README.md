# Game-math development fixtures, v1

This NEW catalog is harness-owned and independent of the existing Roblox suites,
baselines, evaluation gate and scoring code. Nothing here enables a skill pack.
`roblox-game-math` stays OFF by default; explicit opt-in uses
`STAR_SKILL_PACKS=roblox-game-math`.

## Catalog contract

`golden-tasks-v1.json` is an object with `schema_version`, `name`, `harness_owned`,
`scope` and exactly twenty ordered `tasks`. Each task contains a pure-function
prompt, stated absolute/relative tolerances, a `unit_test` body and expected
check count, a reference answer, a plausible mathematically wrong answer, and
named assertions that must reject the wrong answer. Answer strings are raw Luau
modules returning one function, not fenced prose. The fixtures use numbers and
plain tables, not mock Roblox engine objects.

Bodies follow `evals/roblox/tests/` conventions: `load_answer()` loads the module,
then harness-owned `check(name, condition)` calls record individual assertions.
The body is separate from both answers. The standalone wrapper executes every
named check in order; an exception or truncated run is an infrastructure/fixture
failure, not successful rejection of the intended bad answer. There are 187
assertions per complete answer set, 374 observations across both sets.

Coverage: safe vectors, facing/dot, oriented cross products, noncommutative rigid
composition, -Z look-at with parallel-up handling, unclamped lerp, power easing,
sine/exponential easing, analytical critical springs, quadratic/cubic Bezier,
gravity position/velocity, launch velocity, angle wrapping, shortest-angle lerp,
ray-plane, ray-sphere, strict weighted intervals, explicit seeded state and
capped fixed-step accumulation that preserves time.

Float comparisons use absolute tolerance 1e-9, relative tolerance 0. Integer
states/indices and boolean/nil results are exact. Degenerate-vector thresholds,
angle tie direction, ray ranges, RNG endpoints and accumulator overload policy
are specified in each prompt. Frame-boundary tests use binary-exact steps.

## Offline validation

From the repository root:

```sh
python -m pytest -q tests/test_game_math_catalog.py tests/test_game_math_pack.py
```

The catalog validator always runs. Runtime tests prefer an already installed
`luau` CLI. Otherwise an installed Lua 5.4 shared library executes the exact same
source, without transpilation, as a compatibility check of the deliberately
shared syntax/math subset. Lua 5.4 success is **not** native Luau validation or
Roblox Studio/physics verification. No test downloads a runtime, accesses a
network, opens a keyring, uses a GPU, or invokes a model.

To require native Luau for a release-gate run:

```sh
STAR_MATH_REQUIRE_LUAU=1 python -m pytest -q tests/test_game_math_catalog.py
```

That command fails if native Luau is absent; it cannot silently substitute the
compatibility runtime. Without the requirement, missing both runtimes yields
explicit runtime-test skips, never a claim that answers executed.

`check_fixtures.py` executes only the catalog's two reviewed answers for a known
task ID, in a disposable child process with a ten-second wall timeout. It is a
fixture-development helper, **not a security sandbox** and not a local path for
running arbitrary model submissions. Production answer evaluation remains in
the existing server-side sandbox; no existing suite or scoring rule is changed.

The only adjustment to the pre-existing skill-pack test is its expected pack
inventory. New tests exercise the real registry, default-off behavior, explicit
routing and rendering; no shared chat/runtime/frontend file is changed.
