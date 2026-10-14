# Slang for STAR (research, checked 2026-10-13)

Status: verified on 2026-10-13: latest compiler release **v2026.19** (2026-09-29) on github.com/shader-slang/slang; the project ships roughly weekly with versions `vYYYY.N[.patch]` (v2026.18.1 and v2026.18.2 on 2026-09-22 contained breaking changes) [1]. Language versions: `legacy` (default when nothing is specified), **2025**, **2026** (alias `latest`, stable), and `202c`/`next` (in development) [2]. Khronos hosts Slang since 2024-11-21 under the Slang Initiative (Apache 2.0 licence) [3]. Targets: D3D11, D3D12, Vulkan, OpenGL, Metal, CUDA/OptiX, CPU, WebGPU [4]. Unverified as of 2026-10-13: console back-ends (Khronos slides mention GDC 2026 proof-of-concept PS5/Xbox support; not public) and the exact Vulkan SDK version bundling v2026.19.

Slang is a shading language and compiler that is largely **HLSL-compatible** and adds modules, generics with interfaces, automatic differentiation, and a single front-end that emits **SPIR-V, DXIL, HLSL, GLSL, Metal, WGSL, CUDA, C++**. Use it when one shader codebase must serve several graphics APIs, or when you need differentiable rendering/neural graphics.

## 1. Mental model

- Write HLSL-style code (`float3`, `Texture2D`, `SV_Position`, `[numthreads]`) inside a **module system**: each module is compiled once and type-checked **before** specialization, unlike C-preprocessor permutations [4][5].
- **Generics + interfaces** replace `#ifdef` permutation soup: `interface ILight { float3 illuminate(SurfaceData s); }`, `float3 shade<L : ILight>(L light, ...)`. The compiler specializes generics at link time (static dispatch); `dyn` interfaces give dynamic dispatch (2026 language version requires the `dyn` keyword) [2].
- **Entry points** are marked with `[shader("vertex")]`, `[shader("fragment")]`, `[shader("compute")]`, `[shader("raygeneration")]`, etc., so one file can hold many stages.
- **ParameterBlock<T>** groups resources into one descriptor set (Vulkan), descriptor table (D3D12), argument buffer (Metal) or bind group (WebGPU) - Slang computes the layout and the reflection API tells the host where everything lives.
- **Automatic differentiation**: mark functions `[Differentiable]` and call `fwd_diff(f)` or `bwd_diff(f)` to get forward/backward derivatives - used for neural shaders, inverse rendering, Gaussian splatting training, and with **SlangPy** from Python [4][6].
- Compilation is via the `slangc` CLI or the C++ **compilation API** (`slang::IGlobalSession`, `ISession`, `IModule`, `IComponentType::link()`, `getTargetCode()`), with **link-time specialization** and precompiled modules [4].

## 2. Type system

- Everything HLSL has: scalars (`bool`, `int`, `uint`, `float`, `half`, `double`, `int8_t`..`uint64_t`, `float16_t`), `vector<T,N>`, `matrix<T,R,C>`, structs, arrays, HLSL resource types (`Texture2D<float4>`, `RWStructuredBuffer<T>`, `SamplerState`, `RaytracingAccelerationStructure`).
- Additions: **generics** (`T`, generic value parameters `<let N : int>`), **interfaces** with associated types and static members, **extensions** (`extension float3 : IFoo { ... }`), **tuples** (2026: `(a, b)` creates a tuple, no longer the comma operator) [2], **optional** (`Optional<T>`), `enum` classes, properties (`property float x { get; set; }`), operator overloading, `__subscript`, `This` type, `where` clauses.
- Pointers: `T*` for buffer device addresses on SPIR-V/CUDA; `ConstBufferPointer<T>`, `DescriptorHandle<T>` for bindless.
- Access control: `public`, `internal` (default since 2025), `private`. In 2026 an unmodified member inherits its enclosing struct's visibility [5].
- 2026 removals: struct-from-struct inheritance (use composition), default-initializing interface-typed variables, `volatile`, some `float4(float2, float)`-style constructors [2].
- **Capabilities** system: functions declare required capabilities (e.g. `[require(spirv, sm_6_5)]`), and the compiler reports when a target cannot satisfy them [4].
- Matrix layout follows HLSL conventions (`mul(M, v)`, `M[i]` is a row); default packing is column-major and selectable with `-matrix-layout-row-major` / `-matrix-layout-column-major` (verify per target; GLSL/SPIR-V mapping flips naming) [4].

```slang
module lighting;

public interface ILight
{
    public float3 illuminate(float3 position, float3 normal);
}

public struct DirectionalLight : ILight
{
    public float3 direction;
    public float3 color;
    public float3 illuminate(float3 p, float3 n) { return color * max(dot(n, -direction), 0.0); }
}

public struct PointLight : ILight
{
    public float3 position;
    public float3 color;
    public float3 illuminate(float3 p, float3 n)
    {
        float3 l = position - p;
        float d2 = max(dot(l, l), 1e-4);
        return color * max(dot(n, l * rsqrt(d2)), 0.0) / d2;
    }
}
```

## 3. Runtime, concurrency and async model

- Same execution model as the target API: graphics stages, compute (`[numthreads(x,y,z)]`), mesh/amplification, ray tracing, and (target-permitting) work graphs. Slang does not add a runtime; it generates target code.
- Barriers and wave operations use HLSL names (`GroupMemoryBarrierWithGroupSync`, `WaveActiveSum`, `WavePrefixSum`), mapped to SPIR-V/GLSL subgroup ops, Metal SIMD-group functions, WGSL subgroups, CUDA warp intrinsics.
- Uniformity and derivative rules are those of the target: on WGSL the generated code must still pass Tint/naga uniformity analysis; on all targets, barriers must be in uniform control flow.
- **Host-side async** is the API's business. SlangPy runs kernels from Python (on Vulkan/D3D12/CUDA/Metal) and integrates with PyTorch autograd for differentiable shaders [6].
- `slang-rhi` (render hardware interface used by SlangPy and samples) abstracts devices across APIs [6].

## 4. Tooling and package management

- **slangc** CLI examples [4]:
  - `slangc shader.slang -target spirv -profile spirv_1_5 -entry psMain -stage fragment -o ps.spv`
  - `slangc shader.slang -target dxil -profile sm_6_6 -entry csMain -o cs.dxil`
  - `slangc shader.slang -target wgsl -o shader.wgsl`, `-target metal`, `-target glsl`, `-target cuda`, `-target hlsl`
  - `-std 2026` or `#language slang 2026` on line 1 selects the language version [2]; `-g` debug info; `-O3`; `-warnings-as-errors all`; `-reflection-json out.json`.
- Distribution: GitHub release archives (Windows/Linux/macOS), included in the **LunarG Vulkan SDK**, NuGet/vcpkg ports, pip `slangpy` (SlangPy), npm/wasm build used by the **Slang Playground** (in-browser compile to all targets) [7].
- Language server: `slangd` with the VS Code "Slang" extension (go to definition across modules, completion, diagnostics).
- Modules are the "package" unit: `import mylib;` resolves `mylib.slang` or a precompiled `mylib.slang-module` on the search path (`-I`). No registry or package manager exists; vendor modules as files.
- Reflection API (`slang::ProgramLayout`, `TypeLayoutReflection`) or `-reflection-json` gives set/binding/offset for host code; this replaces hand-matching bindings.
- Consumes most existing HLSL directly; can also read GLSL (`-lang glsl`, GLSL source-language selection was normalized in v2026.18.1) [1].

## 5. Testing

- Inspect generated target code (`-target hlsl`/`glsl`/`wgsl`) to debug semantics; validate SPIR-V with `spirv-val` and DXIL with the DXC validator.
- RenderDoc/PIX/Nsight debug the generated code; `-g` emits SPIR-V NonSemantic debug info (function-level inlining info improved in v2026.18.3) [1] so RenderDoc can step through Slang source on Vulkan.
- `printf` works on SPIR-V/CUDA/CPU targets.
- Unit tests: **CPU target** (`-target cpp` / host-callable) or **SlangPy** with pytest: call a Slang function on NumPy arrays and assert results; ideal for testing shared math modules [6].
- Slang's own repo uses `slang-test` with `//TEST:` directives; useful as a pattern for compute-shader regression tests.

## 6. Idiomatic patterns

Generic shading with interfaces (specialized per light type, no `#ifdef`):

```slang
import lighting;

struct Material { float3 albedo; };
ParameterBlock<Material> gMaterial;          // one descriptor set / bind group

float3 shade<L : ILight>(L light, float3 p, float3 n)
{
    return gMaterial.albedo * light.illuminate(p, n);
}

ConstantBuffer<DirectionalLight> gSun;

[shader("fragment")]
float4 psMain(float3 worldPos : POSITION, float3 normal : NORMAL) : SV_Target
{
    return float4(shade(gSun, worldPos, normalize(normal)), 1.0);
}
```

Automatic differentiation:

```slang
[Differentiable]
float loss(float x, no_diff float target)
{
    float y = x * x * 0.5;
    return (y - target) * (y - target);
}

void step(inout float x, float target, float lr)
{
    var dp = diffPair(x);                    // primal + derivative pair
    bwd_diff(loss)(dp, target, 1.0);          // dL/dx written into dp.d
    x -= lr * dp.d;
}
```

Compute with wave intrinsics, compiled to SPIR-V, DXIL, Metal or WGSL from one source:

```slang
RWStructuredBuffer<float> data;

[shader("compute")]
[numthreads(64, 1, 1)]
void csMain(uint3 tid : SV_DispatchThreadID)
{
    float v = data[tid.x];
    float s = WaveActiveSum(v);
    if (WaveIsFirstLane()) data[tid.x] = s;
}
```

Module split:

```slang
// lighting.slang
module lighting;
__include "lighting-brdf";      // lighting-brdf.slang starts with: implementing lighting;
public float3 lambert(float3 albedo) { return albedo / 3.14159265; }
```

## 7. Top pitfalls and error-message fixes

| Error / symptom | Cause | Fix |
|---|---|---|
| `undefined identifier 'X'` for a function defined in another module | Default visibility is `internal` since language 2025 [2][5] | Mark it `public`, or keep both files in the same module via `__include`/`implementing` |
| `module declaration expected` style errors under `#language slang 2025/2026` | 2025+ requires a `module` declaration at the start of each module file [2] | Add `module name;` as the first declaration (after `#language`) |
| Old code breaks after `-std 2026`: comma expression became a tuple | `(a, b)` is a tuple in 2026 [2] | Split statements; do not rely on the comma operator |
| `struct` inheritance error in 2026 | Struct-from-struct inheritance removed [2] | Compose: store the base struct as a field; use interfaces for polymorphism |
| Error about interface-typed variable without initializer (2026) | Default-initialization of interface-typed locals removed [2] | Initialize with a concrete value or use generics |
| Dynamic dispatch error requiring `dyn` (2026) | Implicit existential types are stricter [2] | Write `dyn ILight` or make the function generic `<L : ILight>` |
| Breaking change after compiler upgrade (e.g. v2026.18.1 rejects some `ResourceDescriptorHeap` conversions) [1] | Fast weekly releases with occasional breaking changes | Pin `slangc` version in CI and the Vulkan SDK; read release notes before upgrading |
| `capability ... not supported by target` | Using SM 6.x/ray-tracing/wave features on a target lacking them | Add `[require(...)]` and target-specific code paths with `__target_switch`, or change profile |
| WGSL output rejected by the browser with a uniformity error | Slang emits correct WGSL but the source branches on non-uniform data before a sample/barrier | Restructure source (sample before branching, `SampleLevel`) |
| Matrix appears transposed on Vulkan vs D3D | Layout options and row/column naming differ across targets | Set `-matrix-layout-*` explicitly and keep one CPU convention; verify with reflection |
| Bindings differ from what host code assumes | Slang assigns bindings automatically when not specified | Use reflection (`-reflection-json`) or explicit `[[vk::binding]]`/`register()` |
| HLSL code using `#include` permutations recompiles slowly | Not using modules | Convert headers to modules (`import`), precompile `.slang-module` |
| NaN after autodiff | Non-differentiable ops (`floor`, comparisons) or division by zero in backward pass | Mark non-differentiable params `no_diff`, add `[BackwardDerivative]` custom derivatives, clamp denominators |
| Non-void function missing a return compiles (warning) but fails in 202c | 202c turns the warning into an error [2] | Return or `throw` on every path now |

## 8. Performance

- Generated code quality tracks the downstream compiler (DXC, the SPIR-V driver compilers, Metal, Tint). Inspect output (`-target hlsl`/`spirv-asm`) when profiling.
- Generics are specialized statically: no runtime cost. `dyn` interfaces generate a switch-based dispatch; avoid them in hot paths.
- Precompiled modules and link-time specialization cut build times compared with preprocessor permutations [4].
- `[ForceUnroll]` replaces `$for` (deprecated in 2025, removed in 202c) [2]; unroll only small fixed loops.
- Use `half`/`float16_t` with appropriate capabilities on mobile and Metal targets.

## 9. Security

- Slang is a compiler; generated shaders inherit the safety properties of their target: WGSL output is sandboxed by the browser, SPIR-V/DXIL are not. Untrusted Slang source should be compiled in a sandboxed process with time/memory limits (compiler hangs have been fixed in point releases, e.g. reverse-mode autodiff hang in v2026.18.3 [1]).
- Bound all buffer indices; enable robustness features on the API side.
- The reflection JSON exposes resource layouts only; no secrets, but do not ship debug info for proprietary shaders unless intended.

## 10. Game-dev usage

- NVIDIA RTX Remix, Falcor, and many research renderers use Slang; Vulkan samples include Slang versions; LunarG's 2026 Vulkan ecosystem survey lists Slang among preferred shading languages (per Khronos slides) [3].
- Engines can adopt Slang as an HLSL superset: same file extension conventions, gradual module migration. Unreal and Unity do not use Slang natively (Unity/Unreal integration is custom; unverified for 2026).
- WebGPU projects can author in Slang and ship WGSL; Rust projects can feed Slang's SPIR-V into wgpu.
- **Roblox**: **no user shader language**; Slang does not apply to Roblox experiences. Use ParticleEmitter, Beam, Trail, SurfaceAppearance and post-processing instances.

## 11. Cheat sheet vs Luau

| Concept | Luau (Roblox) | Slang |
|---|---|---|
| Module | `ModuleScript` + `require(path)` | `module name;` + `import name;` |
| Visibility | returned table fields are public | `public` / `internal` (default) / `private` |
| Interface | type annotations, no runtime interfaces | `interface IFoo { ... }`, `struct S : IFoo` |
| Generics | `function f<T>(x: T): T` (type-check only) | `T f<T : IFoo>(T x)` (specialized code) |
| Vector | `Vector3.new()` | `float3()` |
| Transform | `CFrame` | `float4x4`, `mul(M, v)` |
| Clamp / lerp | `math.clamp`, `a:Lerp(b,t)` | `clamp`, `saturate`, `lerp` |
| Tuples | multiple returns `return a, b` | tuples `(a, b)` in 2026 |
| Optional | `T?` with `nil` | `Optional<T>` |
| Errors | `error`, `pcall` | compile-time diagnostics; `throw`/`try` exist for compile-time-checked error types in limited contexts |
| Indexing | 1-based tables | 0-based fixed arrays and buffers |
| Recursion | allowed | not on GPU targets |
| Derivatives | none | `fwd_diff`, `bwd_diff`, `[Differentiable]` |
| Type check mode | `--!strict` | `#language slang 2026` |
| Runs where | Roblox VM | wherever the target API runs (GPU, CPU, CUDA) |

## 12. Recent changes and version notes

- **Language 2026** stable (alias `latest`): tuples for `(a, b)`, `dyn` required for dynamic dispatch, `volatile` removed, struct inheritance removed, interface-typed default init removed, visibility inherited from enclosing aggregate [2][5].
- **Language 2025**: `internal` default visibility, mandatory `module` declaration, `$for` deprecated [2].
- **202c / next** (in development): no generic-parameter-count overload tie-breaker, `(MyStruct)0` is a normal conversion, `$for` removed, missing returns become errors [2].
- Compiler v2026.18 - v2026.19 (2026-09): `Buffer` conforms to `IArray`, native WGSL loops, `HitObject.GetTriangleVertexPositions`, post-depth `SV_Coverage` attribute, serialized-module version compatibility enforced, agent skills bundled with releases [1].

## Sources

1. https://github.com/shader-slang/slang/releases (accessed 2026-10-13)
2. https://shader-slang.org/slang/user-guide/language-version.html (accessed 2026-10-13)
3. https://www.khronos.org/news/press/khronos-group-launches-slang-initiative-hosting-open-source-compiler-contributed-by-nvidia (accessed 2026-10-13)
4. https://shader-slang.org/slang/user-guide/ (accessed 2026-10-13)
5. https://shader-slang.org/slang/user-guide/modules.html (accessed 2026-10-13)
6. https://github.com/shader-slang/slangpy (accessed 2026-10-13)
7. https://shader-slang.org/slang-playground/ (accessed 2026-10-13)
8. https://shader-slang.org/ (accessed 2026-10-13)
9. https://shader-slang.org/slang/user-guide/autodiff.html (accessed 2026-10-13)
