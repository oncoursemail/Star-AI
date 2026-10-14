# WGSL for STAR (research, checked 2026-10-13)

Status: verified on 2026-10-13: WGSL and WebGPU are W3C **Candidate Recommendation** documents (first CR snapshots invited implementations with comments due 2025-02-28; WGSL CR Draft 2025-07-14; WebGPU CR Drafts 2026-01-29 and 2026-08-10) [1][2][3]. WebGPU ships by default in Chrome/Edge (since 113, desktop; Android since 121), in **Firefox 141 on Windows** (2025-07-22), and in **Safari 26** (macOS, iOS, iPadOS, visionOS) [4][5][6]. Chrome shipped `subgroups` in 134 (2025-02), the WGSL `subgroup_id` extension in 144, `subgroup_uniformity` in 145, and subgroup size control (`@subgroup_size`) in a 2026-08 post covering Chrome 151-152 [7][8]. Unverified as of 2026-10-13: whether Firefox has shipped WebGPU by default on macOS/Linux, and the exact Chrome version numbers in the 151-152 post (the page could not be fetched).

WGSL (WebGPU Shading Language) is the only shader language WebGPU accepts. It is also the native language of **wgpu**/**Bevy** in Rust and of **Dawn** in C++, so it is used far beyond browsers.

## 1. Mental model

- A **module** contains declarations and one or more **entry points** marked `@vertex`, `@fragment`, or `@compute @workgroup_size(...)`. The host chooses the entry point by name when creating the pipeline.
- Syntax is Rust-flavoured: `fn`, `let` (immutable), `var` (mutable), `const` (compile-time), `override` (pipeline-creation-time constants), types after names (`let x: f32 = 1.0;`), `->` return types.
- **No implicit conversions**, no implicit fall-through, no recursion, no pointers to arbitrary memory, no undefined behaviour in the classic C sense: the spec defines results of out-of-bounds accesses and integer division by zero, so the language is safe to run from untrusted web pages [1].
- Resources are module-scope `var` declarations decorated with `@group(g) @binding(b)`, matched against `GPUBindGroupLayout` entries.
- Implementations translate WGSL to the platform language: **Tint** (Dawn/Chrome) -> HLSL/DXIL, MSL, SPIR-V, GLSL; **naga** (wgpu/Firefox) -> HLSL, MSL, SPIR-V, GLSL; WebKit has its own compiler (WGSL -> MSL) [9][10].
- The compiler runs a static **uniformity analysis** that rejects code where derivative or barrier operations could execute in non-uniform control flow [1][11].

## 2. Type system

- Scalars: `bool`, `i32`, `u32`, `f32`, `f16` (needs `enable f16;` and the `shader-f16` device feature). Abstract numeric types for literals: `1` is AbstractInt, `1.0` AbstractFloat, which concretise on use; suffixes `1u`, `1i`, `1f`, `1h` [1].
- Vectors: `vec2<f32>`, `vec3<u32>`, with predeclared aliases `vec3f`, `vec4i`, `vec2u`, `vec3h`. Swizzles `.xyz`/`.rgb` (read; component assignment `v.x = 1.0` allowed on `var`, but no multi-component swizzle assignment).
- Matrices: `mat4x4<f32>` / `mat4x4f` (columns x rows, **column-major**), float only. `m[i]` is a column. `M * v` transforms a column vector.
- Arrays: `array<f32, 8>` fixed; `array<f32>` runtime-sized (only as the last member of a storage buffer, `arrayLength(&buf.data)`).
- Structs with explicit layout attributes `@align(n)`, `@size(n)`. **Memory layout rules**: `vec3<f32>` has size 12 and **alignment 16**; in the **uniform** address space arrays need a stride that is a multiple of 16 and struct alignment rounds up to 16; the storage space is closer to std430 [1].
- Address spaces: `function`, `private`, `workgroup`, `uniform`, `storage` (with access `read` or `read_write`), `handle` (textures/samplers). Pointers `ptr<function, f32>` exist for passing to functions, with restrictions (relaxed by the `unrestricted_pointer_parameters` language extension).
- Textures: `texture_2d<f32>`, `texture_cube<f32>`, `texture_depth_2d`, `texture_multisampled_2d<f32>`, `texture_storage_2d<rgba8unorm, write>`, `texture_external` (video). Samplers: `sampler`, `sampler_comparison`.
- Atomics: `atomic<u32>`, `atomic<i32>` only in `storage` (read_write) or `workgroup` space; `atomicAdd(&a, 1u)`.
- Language features are opt-in with directives at the top of the module:
  - `enable f16;`, `enable dual_source_blending;`, `enable clip_distances;`, `enable subgroups;` (device-feature gated "enable extensions").
  - `requires readonly_and_readwrite_storage_textures;`, `requires packed_4x8_integer_dot_product;`, `requires unrestricted_pointer_parameters;`, `requires pointer_composite_access;` (language extensions, discoverable through `navigator.gpu.wgslLanguageFeatures`) [12].
  - `diagnostic(off, derivative_uniformity);` global directive or `@diagnostic(warning, derivative_uniformity)` attribute on a function or statement.

```wgsl
struct Camera {
    view_proj : mat4x4f,   // offset 0, size 64
    position  : vec3f,     // offset 64, align 16
    time      : f32,       // offset 76: fills vec3 padding
};
@group(0) @binding(0) var<uniform> camera : Camera;

struct Particle { pos_life : vec4f, vel : vec4f };   // vec4 avoids vec3 padding surprises
@group(0) @binding(1) var<storage, read_write> particles : array<Particle>;
```

## 3. Runtime, concurrency and async model

- Pipelines: **render** (vertex -> rasterizer -> fragment) and **compute**. No geometry/tessellation/mesh/ray-tracing stages in core WebGPU.
- Compute built-ins: `@builtin(global_invocation_id)`, `local_invocation_id`, `local_invocation_index`, `workgroup_id`, `num_workgroups`; with subgroups, `subgroup_invocation_id`, `subgroup_size` (and `subgroup_id`/`num_subgroups` with the `subgroup_id` extension) [7].
- Default limits: `maxComputeInvocationsPerWorkgroup` 256, `maxComputeWorkgroupSizeX/Y` 256, `Z` 64, `maxComputeWorkgroupStorageSize` 16384 bytes, `maxStorageBuffersPerShaderStage` 8, `maxBindGroups` 4 [2]. Request higher limits on the device if the adapter allows.
- Barriers: `workgroupBarrier()`, `storageBarrier()`, `textureBarrier()`, and `workgroupUniformLoad(&p)` (loads a workgroup variable and returns a uniform value, with an implied barrier).
- **Uniformity analysis** (WGSL spec section on uniformity): `textureSample`, `textureSampleBias`, `textureSampleCompare`, `dpdx`/`dpdy`/`fwidth` must be in uniform control flow in fragment shaders; barriers and `workgroupUniformLoad` must be in uniform control flow in compute. Non-uniform sources include builtins like `local_invocation_id`, `position`, vertex outputs/fragment inputs, storage `read_write` loads, and results of `textureSample` itself [1][11]. The rule `derivative_uniformity` defaults to **error**; it can be lowered with a diagnostic filter, but barrier violations cannot.
- The **host side is async** in JavaScript: `await navigator.gpu.requestAdapter()`, `await adapter.requestDevice()`, `await buffer.mapAsync(GPUMapMode.READ)`, `await device.queue.onSubmittedWorkDone()`, `await shaderModule.getCompilationInfo()`, `await device.createRenderPipelineAsync(...)`. Errors are **asynchronous**: use `device.pushErrorScope('validation')` / `popErrorScope()` and `device.addEventListener('uncapturederror', ...)`; `device.lost` is a promise.

## 4. Tooling and package management

- Browsers: Chrome/Edge (Dawn + Tint), Firefox (wgpu + naga), Safari (WebKit). Error messages differ per implementation.
- Native: **wgpu** (Rust; also `wgpu-native` C API), **Dawn** (C++; `webgpu.h`), **Deno** (`navigator.gpu` built on wgpu).
- **naga CLI** (`cargo install naga-cli`): `naga shader.wgsl` validates; `naga shader.wgsl out.spv`/`out.metal`/`out.hlsl`/`out.glsl` translates; also converts SPIR-V/GLSL to WGSL [10].
- **Tint** (in Dawn): `tint --format spirv shader.wgsl` / `--format wgsl` from SPIR-V; used by Chrome.
- **Slang** emits WGSL (`slangc -target wgsl`) so you can author in Slang/HLSL-like syntax [13].
- **wgsl_analyzer** (language server), **WGSL syntax in VS Code**, `naga_oil` (Bevy) for `#import`, `#define`/`#ifdef` composition. TypeScript libraries: `webgpu-utils` (computes struct offsets from WGSL source), `wgpu-matrix`; TypeGPU generates typed bindings.
- Package management: none in the language; JS bundlers import `.wgsl` as strings (`?raw` in Vite), Rust embeds with `include_str!`/`wgpu::include_wgsl!`.

## 5. Testing

- `await shaderModule.getCompilationInfo()` returns messages with line/column; print them in development builds.
- Wrap pipeline creation in `pushErrorScope('validation')`; log `popErrorScope()` results; listen for `uncapturederror`.
- Browser tools: Chrome `chrome://gpu`, WebGPU Inspector extension (captures, buffer/texture viewer), Firefox `about:support`; RenderDoc can capture native wgpu/Dawn apps (and Chrome with flags) on Vulkan/D3D12.
- Unit-test compute shaders headlessly with Deno, Node (`webgpu` npm package based on Dawn), Rust `wgpu` tests, or Puppeteer/Playwright with GPU flags: write input buffers, dispatch, `copyBufferToBuffer` into a `MAP_READ` buffer, `mapAsync`, compare with a CPU reference using tolerances.
- There is no `printf`. Write debug values into a storage buffer.
- The **WebGPU CTS** (conformance test suite, gpuweb/cts) is the reference for behaviour questions.

## 6. Idiomatic patterns

Vertex + fragment pair:

```wgsl
struct VsOut {
    @builtin(position) pos : vec4f,
    @location(0) uv : vec2f,
};

@vertex
fn vs_main(@builtin(vertex_index) i : u32) -> VsOut {
    // fullscreen triangle
    let uv = vec2f(f32((i << 1u) & 2u), f32(i & 2u));
    var out : VsOut;
    out.pos = vec4f(uv * vec2f(2.0, -2.0) + vec2f(-1.0, 1.0), 0.0, 1.0);
    out.uv = uv;
    return out;
}

@group(0) @binding(0) var scene_tex : texture_2d<f32>;
@group(0) @binding(1) var scene_smp : sampler;

@fragment
fn fs_main(in : VsOut) -> @location(0) vec4f {
    let c = textureSample(scene_tex, scene_smp, in.uv).rgb;
    return vec4f(c / (vec3f(1.0) + c), 1.0);
}
```

Fixing a uniformity error (sample first, branch after; or use explicit LOD):

```wgsl
@fragment
fn fs(@location(0) uv : vec2f, @location(1) mask : f32) -> @location(0) vec4f {
    // BAD: if (mask > 0.5) { return textureSample(t, s, uv); }  -> uniformity error
    let c = textureSample(t, s, uv);                 // uniform control flow
    if (mask > 0.5) { return c; }
    let far = textureSampleLevel(t, s, uv, 0.0);     // explicit LOD: allowed anywhere
    return far * 0.5;
}
```

Compute with workgroup memory:

```wgsl
@group(0) @binding(0) var<storage, read> input : array<f32>;
@group(0) @binding(1) var<storage, read_write> output : array<f32>;
var<workgroup> tile : array<f32, 256>;

@compute @workgroup_size(256)
fn reduce(@builtin(global_invocation_id) gid : vec3u,
          @builtin(local_invocation_index) li : u32,
          @builtin(workgroup_id) wg : vec3u) {
    let n = arrayLength(&input);
    tile[li] = select(0.0, input[gid.x], gid.x < n);   // no early return before barriers
    workgroupBarrier();
    for (var stride = 128u; stride > 0u; stride = stride >> 1u) {
        if (li < stride) { tile[li] += tile[li + stride]; }
        workgroupBarrier();                             // outside the if: uniform
    }
    if (li == 0u) { output[wg.x] = tile[0]; }
}
```

Pipeline-overridable constants:

```wgsl
override WORKGROUP : u32 = 64;
override use_fog : bool = true;
@compute @workgroup_size(WORKGROUP) fn main() { }
```

JavaScript host with error scopes:

```js
const module = device.createShaderModule({ code: wgslSource });
const info = await module.getCompilationInfo();
for (const m of info.messages) console[m.type === 'error' ? 'error' : 'warn'](`${m.lineNum}:${m.linePos} ${m.message}`);
device.pushErrorScope('validation');
const pipeline = device.createComputePipeline({ layout: 'auto', compute: { module, entryPoint: 'reduce' } });
const err = await device.popErrorScope();
if (err) console.error(err.message);
```

## 7. Top pitfalls and error-message fixes

| Error text (Tint unless noted) | Cause | Fix |
|---|---|---|
| `'textureSample' must only be called from uniform control flow` with `note: control flow depends on possibly non-uniform value` | Implicit-derivative sample inside a branch/loop that depends on per-fragment data [11] | Sample before branching; or `textureSampleLevel`/`textureSampleGrad`; last resort `diagnostic(off, derivative_uniformity)` if you know the branch is uniform |
| `'workgroupBarrier' must only be called from uniform control flow` + `note: builtin 'local_id' may be non-uniform` [11] | Barrier inside `if (lid.x < k)` or after an early `return` | Move the barrier out of the branch; guard the work instead |
| naga: `Required uniformity of control flow for IMPLICIT_LEVEL ... is not fulfilled` (Firefox/wgpu wording) | Same derivative uniformity rule | Same fix |
| `type mismatch` / `no matching overload for operator * (f32, i32)` / `cannot convert` | No implicit conversions; `1` and `1.0` concretise differently | Cast: `f32(i)`, `u32(x)`; use literal suffixes `1u`, `2.0` |
| `uniform storage requires that array elements are aligned to 16 bytes` / `... number of bytes between ... must be a multiple of 16` | `array<f32, N>` or misaligned struct in the `uniform` address space [1] | Use `array<vec4f, N/4>`, add `@align(16)`, or move to `var<storage, read>` |
| Data shifted by 4 bytes when written from JS `Float32Array` | `vec3f` is 12 bytes but 16-aligned in structs | Pad to vec4 on both sides; compute offsets with webgpu-utils |
| `Binding size (X) is smaller than the minimum binding size (Y)` | Buffer bound is smaller than the WGSL struct | Allocate per WGSL layout (multiples of 16 for uniform); set `minBindingSize` correctly |
| `Binding doesn't exist in [BindGroupLayout]` / `Bind group layout ... is incompatible` | `@group/@binding` or resource type differs from the layout; with `layout: 'auto'` unused bindings are stripped | Match exactly; use explicit layouts when sharing bind groups between pipelines |
| `entry point ... not found` / `Entry point "main" doesn't exist in the shader module` | Wrong `entryPoint` name or stage attribute missing | Use the exact `fn` name with `@vertex`/`@fragment`/`@compute` |
| `@workgroup_size ... exceeds maxComputeInvocationsPerWorkgroup (256)` | Default limit is 256 invocations [2] | Reduce, or request a higher limit on the device |
| `'f16' type used without 'f16' extension enabled` | Missing `enable f16;` or device lacks `shader-f16` | Check `adapter.features.has('shader-f16')`, request it, add `enable f16;` |
| `recursion is not permitted` / `cyclic dependency found` | Recursive function calls | Rewrite iteratively with an explicit stack array |
| `unresolved call target 'texture'` / `unresolved call target 'mod'` (ported GLSL) | GLSL names that WGSL lacks (`texture()`, `mod()`, `texelFetch`; `mix`, `fract`, `clamp` do exist) | Use `textureSample`, `vec3f`, `x - y * floor(x / y)` for floored mod (`%` on floats truncates) |
| Integer division by zero gives a value, not a crash; `i32` overflow wraps | WGSL defines these results for safety [1] | Validate inputs; do not rely on traps |

## 8. Performance

- Keep bind group changes low; group resources by update frequency (group 0 per frame, 1 per material, 2 per draw); use dynamic offsets for per-draw uniforms.
- `writeBuffer` for small updates; staging/mapped buffers for streams; avoid `mapAsync` round-trips in the frame loop (they stall).
- Use `createRenderPipelineAsync`/`createComputePipelineAsync` and create pipelines at load to avoid hitches.
- Workgroup size 64 is a portable default; use subgroups when the adapter supports them, falling back gracefully.
- `f16` halves bandwidth/registers on supported hardware; `packed_4x8_integer_dot_product` for int8 ML kernels.
- Translation layers add bounds checks on storage arrays; keep indices provably in range (`min(i, n - 1u)`) and prefer fixed-size arrays where possible so compilers can elide checks.
- Indirect draws/dispatches (`drawIndirect`, `dispatchWorkgroupsIndirect`) and render bundles reduce JS overhead.

## 9. Security

- WGSL was designed for **untrusted web content**: no undefined behaviour, bounds-checked or clamped memory accesses, no pointers to arbitrary memory, uniformity rules to avoid undefined derivatives, timeouts via browser GPU process watchdogs [1][2].
- Out-of-bounds reads may return any in-bounds value or zero; writes may be discarded - correct results are not guaranteed, only safety. Do not depend on a specific behaviour.
- Cross-origin textures cannot be used unless CORS-cleared; `GPUExternalTexture` follows video security rules.
- Long-running shaders can still cause device loss (`device.lost` resolves with reason); handle it by recreating the device.
- Timing precision: `timestamp-query` results are quantised in browsers to limit side channels.

## 10. Game-dev usage

- **Bevy** (Rust): WGSL is the primary language (`.wgsl` assets with `#import bevy_pbr::...` via naga_oil); custom materials implement `Material` with a WGSL fragment shader.
- **wgpu**-based engines and tools (Fyrox, Veloren renderer, Ruffle, Zed's renderer use wgpu or similar stacks).
- **Web engines**: three.js WebGPURenderer with **TSL** (node graph -> WGSL), Babylon.js WebGPU engine (WGSL shaders or GLSL translated), PlayCanvas (WGSL with capability-gated `requires`) [12].
- **Godot/Unity/Unreal** web exports still mostly target WebGL 2; Unity 6 has WebGPU web export (experimental status as of last check; unverified for 2026).
- **Roblox**: **no user shader language**; WGSL is irrelevant for Roblox experiences. Use Roblox effect instances.

## 11. Cheat sheet vs Luau

| Concept | Luau (Roblox) | WGSL |
|---|---|---|
| Variables | `local x = 1` | `let x = 1.0;` (immutable), `var y = 0u;` (mutable), `const`, `override` |
| Function | `local function f(a: number): number` | `fn f(a: f32) -> f32 { ... }` |
| Vector | `Vector3.new(1,2,3)` | `vec3f(1.0, 2.0, 3.0)` |
| Transform | `CFrame` | `mat4x4f`, `M * vec4f(p, 1.0)` |
| Dot / cross | `a:Dot(b)`, `a:Cross(b)` | `dot(a, b)`, `cross(a, b)` |
| Magnitude / unit | `v.Magnitude`, `v.Unit` | `length(v)`, `normalize(v)` |
| Clamp | `math.clamp(x, 0, 1)` | `clamp(x, 0.0, 1.0)`, `saturate(x)` |
| Lerp | `a:Lerp(b, t)` | `mix(a, b, t)` |
| Ternary | `if c then a else b` | `select(b, a, c)` (note argument order: false value first) |
| Modulo | `%` floored | `%` on floats truncates (like C `fmod`); floored: `x - y * floor(x / y)` |
| Indexing | 1-based | 0-based; arrays fixed or runtime-sized storage |
| Integers | `number` (f64) | `i32`, `u32` distinct types, no implicit mixing |
| Recursion / tables | allowed / dynamic | forbidden / no allocation |
| Async | `task.wait`, events | host JS uses promises (`mapAsync`); shader code is synchronous |
| Errors | `pcall` | compile-time diagnostics; runtime is defined-but-garbage, no exceptions |

## 12. Recent changes and version notes

- 2025-2026 additions shipped in Chrome: `subgroups` (134), `clip_distances`, `dual_source_blending`, texture-tier and storage-texture access extensions, WGSL `subgroup_id` (144), `subgroup_uniformity` (145), subgroup size control `@subgroup_size(n)` with `enable subgroup_size_control;` (151-152 post, 2026-08) [7][8].
- WGSL language extensions (`requires`): `readonly_and_readwrite_storage_textures`, `packed_4x8_integer_dot_product`, `unrestricted_pointer_parameters`, `pointer_composite_access`; support differs between naga versions and browsers - query `navigator.gpu.wgslLanguageFeatures` [12].
- Firefox 141 shipped WebGPU on Windows (2025-07); Safari 26 enabled WebGPU by default (2025-09) [5][6].
- Spec: WGSL CR Draft 2025-07-14; WebGPU CR Drafts in 2026 [1][3].

## Sources

1. https://www.w3.org/TR/WGSL/ (accessed 2026-10-13; latest CR Draft seen: https://www.w3.org/TR/2025/CRD-WGSL-20250714/)
2. https://www.w3.org/TR/webgpu/ (accessed 2026-10-13)
3. https://www.w3.org/TR/2026/CRD-webgpu-20260810/ (accessed 2026-10-13)
4. https://developer.chrome.com/blog/webgpu-release (accessed 2026-10-13)
5. https://windowsreport.com/firefox-141-finally-brings-webgpu-support-on-windows/ (secondary report of Firefox 141; accessed 2026-10-13)
6. https://webkit.org/blog/ (Safari 26 WebKit features; accessed 2026-10-13)
7. https://developer.chrome.com/blog/new-in-webgpu-134 (accessed 2026-10-13)
8. https://developer.chrome.com/blog/new-in-webgpu-151-152 (search result only; page fetch failed; accessed 2026-10-13)
9. https://dawn.googlesource.com/dawn (accessed 2026-10-13)
10. https://github.com/gfx-rs/wgpu/tree/trunk/naga (accessed 2026-10-13)
11. https://dawn.googlesource.com/dawn/+/HEAD/docs/tint/uniformity_analysis.md (accessed 2026-10-13)
12. https://developer.mozilla.org/en-US/docs/Web/API/WGSLLanguageFeatures (accessed 2026-10-13)
13. https://shader-slang.org/ (accessed 2026-10-13)
14. https://github.com/gpuweb/cts (accessed 2026-10-13)
15. https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API (accessed 2026-10-13)
