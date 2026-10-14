# VFX compiler golden fixtures

`cases.json` defines eight authored input specifications. For each case, the
complete expected ModuleScript is the byte-for-byte concatenation of the frozen
`runtime.luau` fixture and `<case>.luau`. The runtime is factored once to make
lifecycle changes inspectable without eight duplicate diffs. These expected
files are not generated during a test and do not import the compiler's runtime.

To inspect an entire expected file locally:

```sh
cat tests/fixtures/vfx/runtime.luau tests/fixtures/vfx/hit_spark.luau
```

Review runtime changes and each changed golden tail before updating snapshots.
A failing snapshot is not a reason to bless new output automatically. Keep the
independent validation/range and runtime behavior assertions intact.

`service_doubles.luau` is a deterministic Lua 5.4 compatibility harness. It checks
class/property allowlists, disabled-before-parenting, attachment relationships,
scheduler/tween lifecycle, disposal and injected failures. It is not a Roblox
engine implementation: in particular, it does not render, integrate particle
physics or model all tween interpolation/heartbeat semantics. Its CFrame double
only covers the translation-times-Euler-rotation composition used by this module.

The fixtures are unit-test data, not live evaluation evidence or approved visual
assets. Native Luau/Studio and real-device review remain separate acceptance steps.
