# GLSL for STAR (research, checked 2026-10-13)

Status: verified on 2026-10-13: the latest desktop specification listed by Khronos is **GLSL 4.60** (document dated 2023-08-14, revision 4.60.8) with **OpenGL 4.6** (2022-05-05 document) [1]; **GLSL ES 3.20** is the latest ES language (OpenGL ES 3.2; WebGL 2 uses GLSL ES 3.00) [2]. Vulkan consumes **SPIR-V**, not GLSL; GLSL reaches Vulkan through glslang/shaderc using the `GL_KHR_vulkan_glsl` dialect [3][4]. Unverified as of 2026-10-13: no new core GLSL version beyond 4.60 was found; new features arrive as `GL_EXT_*`/`GL_KHR_*` extensions in the GLSL repository [5].

GLSL (OpenGL Shading Language) is Khronos' C-like shading language for OpenGL, OpenGL ES, WebGL and (via SPIR-V) Vulkan. It is also the base of the **Godot shading language** and of Shadertoy code.

## 1. Mental model

- Each shader **stage** is a separate compilation unit with its own `void main()`: vertex, tessellation control/evaluation, geometry, fragment, compute (4.3+), and in Vulkan GLSL also mesh/task (`GL_EXT_mesh_shader`) and ray-tracing stages (`GL_EXT_ray_tracing`).
- Data flows through **qualified globals**, not function parameters: `in`, `out`, `uniform`, `buffer`, `shared`, plus built-ins (`gl_Position`, `gl_FragCoord`, `gl_VertexIndex`/`gl_VertexID`, `gl_GlobalInvocationID`).
- Every file begins with `#version`: `#version 460 core` (desktop), `#version 300 es`/`#version 310 es`/`#version 320 es` (ES/WebGL 2), `#version 450` + Vulkan rules for SPIR-V. Missing or wrong `#version` silently selects GLSL 1.10 on desktop.
- In **OpenGL**, the driver compiles GLSL source at runtime (`glCompileShader`, `glLinkProgram`); every vendor has its own front-end, so code that compiles on NVIDIA may fail on AMD/Intel/Mesa. Use **glslang** as the reference validator. In **Vulkan**, compile offline to SPIR-V.
- Linking matches outputs of one stage to inputs of the next by name (GL) or by `layout(location = N)` (recommended, required in Vulkan).

## 2. Type system

- Scalars: `bool`, `int`, `uint`, `float`, `double` (4.0+, desktop). Explicit-size types through extensions: `GL_EXT_shader_explicit_arithmetic_types` (`float16_t`, `int8_t`, `int64_t`, `f16vec3`) [5].
- Vectors: `vec2..4`, `ivec`, `uvec`, `bvec`, `dvec`. Swizzle sets `xyzw`, `rgba`, `stpq` (cannot mix sets).
- Matrices: `mat2..4`, `mat2x3` (**columns x rows**, opposite naming to HLSL `float2x3`). Storage is **column-major**; `m[i]` returns the **i-th column**. `M * v` is the standard transform; `v * M` multiplies by the transpose.
- Constructors are explicit and strict: `vec3(1.0)` splats, `vec4(v3, 1.0)`; GLSL ES (1.00, 3.00, 3.20) has **no implicit int -> float conversion**, so `float x = 1;` is a compile error there; desktop GLSL 1.20+ allows it. Always write `1.0`.
- Arrays: fixed-size `float a[4];`, unsized last member of an SSBO (`float data[];` with `.length()`), arrays of arrays in 4.3+.
- Opaque types: `sampler2D`, `samplerCube`, `sampler2DShadow`, `isampler2D`, `image2D` (with format layout `rgba8`, `r32f`), and in Vulkan separate `texture2D` + `sampler` combined as `sampler2D(tex, samp)`.
- Precision qualifiers (`lowp`, `mediump`, `highp`) matter on **GLSL ES**: the fragment stage has **no default float precision** in ES 1.00/3.00, so a declaration such as `precision highp float;` (or `mediump`) is mandatory [2]. Desktop GLSL accepts and ignores them.
- Memory layouts for blocks: `std140` (uniform blocks; vec3 aligned to 16 bytes, array elements and struct members rounded to 16 bytes), `std430` (SSBOs and push constants; arrays of scalars are tightly packed, but `vec3` is still 16-byte aligned), `scalar` (`GL_EXT_scalar_block_layout`, Vulkan only) [1][6].

```glsl
layout(std140, binding = 0) uniform Frame {
    mat4  viewProj;     // offset 0
    vec3  cameraPos;    // offset 64, occupies 12 bytes, aligned 16
    float time;         // offset 76: fits in the vec3's padding
    float weights[4];   // std140: stride 16 per element -> 64 bytes
};
layout(std430, binding = 1) buffer Particles {
    vec4 posLife[];     // prefer vec4 over vec3 in buffers to avoid padding surprises
};
```

## 3. Runtime, concurrency and async model

- Graphics pipeline: vertex -> (tess control -> tess eval) -> (geometry) -> rasterization -> fragment -> per-sample operations. Compute is dispatched separately (`glDispatchCompute`, `vkCmdDispatch`).
- Compute: `layout(local_size_x = 64) in;` built-ins `gl_LocalInvocationID`, `gl_WorkGroupID`, `gl_GlobalInvocationID`, `gl_LocalInvocationIndex`; shared memory `shared float tile[256];`.
- Barriers: `barrier()` (execution + shared memory in compute), `memoryBarrierShared()`, `memoryBarrierBuffer()`, `memoryBarrierImage()`, `groupMemoryBarrier()`. Like HLSL, `barrier()` must be in **uniform control flow** (all invocations of the workgroup reach it); in tessellation control shaders GLSL 4.60 only allows it in `main` outside any control flow, and in compute it must be reached in uniform control flow [1].
- Cross-dispatch visibility in OpenGL needs `glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT | ...)` on the CPU side; in Vulkan, pipeline barriers.
- Subgroups: `GL_KHR_shader_subgroup_basic/vote/arithmetic/ballot/shuffle/clustered/quad` give `subgroupAdd`, `subgroupBallot`, `subgroupElect`, `gl_SubgroupSize`, `gl_SubgroupInvocationID` [5].
- Fragment derivatives `dFdx`, `dFdy`, `fwidth` and implicit-LOD `texture()` are undefined in non-uniform control flow; use `textureLod`/`textureGrad`.
- `discard` in fragment shaders (Vulkan: `demote` via `GL_EXT_demote_to_helper_invocation` keeps derivatives valid).
- No async. The application controls overlap with fences/sync objects (`glFenceSync`) or Vulkan semaphores.

## 4. Tooling and package management

- **glslang** (`glslangValidator` / `glslang`): Khronos reference front-end; validates and emits SPIR-V: `glslang -V --target-env vulkan1.3 shader.frag -o frag.spv`. Shader stage from extension (`.vert .frag .comp .geom .tesc .tese .mesh .task .rgen .rchit .rmiss`) [3].
- **shaderc / glslc** (Google, in Vulkan SDK): `glslc -O -fshader-stage=comp in.glsl -o out.spv`; `#include` support via `GL_GOOGLE_include_directive` [7].
- **SPIRV-Tools**: `spirv-val`, `spirv-opt -O`, `spirv-dis`. **SPIRV-Cross**: SPIR-V -> GLSL/ESSL/HLSL/MSL and reflection (`--reflect`). **SPIRV-Reflect** for descriptor reflection [8].
- **naga** (Rust, wgpu) reads GLSL (subset, Vulkan-flavoured) and SPIR-V and writes WGSL/MSL/HLSL/GLSL [9]. **Tint** reads SPIR-V and WGSL.
- Package management: none. Includes via `#include` with `GL_GOOGLE_include_directive` or `GL_ARB_shading_language_include`; engines handle permutations with `#define` injection after `#version`.
- Editors: glsl_analyzer, glslls; Shadertoy for prototyping fragment shaders.

## 5. Testing

- **RenderDoc** (OpenGL 3.2+ core, GLES, Vulkan): pixel history, shader debugging for Vulkan SPIR-V, mesh viewer, resource inspector.
- **Vulkan validation layers** catch descriptor/layout mismatches; **debug printf** via `GL_EXT_debug_printf` and `debugPrintfEXT("x=%f", x);` routed by `VK_LAYER_KHRONOS_validation` [10].
- OpenGL: enable `GL_KHR_debug` (`glDebugMessageCallback`), check `glGetShaderInfoLog` and `glGetProgramInfoLog` after every compile/link.
- Validate every shader with `glslang` in CI against all target versions (`#version 300 es` for WebGL 2 and mobile) because runtime drivers differ.
- Unit test compute: dispatch on known inputs, read back SSBO, compare with tolerance. For fragment math, render to a 1x1 or NxM float framebuffer and read pixels.
- Nsight Graphics, Radeon GPU Profiler, Android GPU Inspector, Xcode GPU tools (through MoltenVK/Metal) for profiling.

## 6. Idiomatic patterns

Vulkan-flavoured vertex + fragment:

```glsl
// mesh.vert
#version 460
layout(set = 0, binding = 0) uniform Camera { mat4 viewProj; } cam;
layout(push_constant) uniform Push { mat4 model; } pc;
layout(location = 0) in vec3 inPos;
layout(location = 1) in vec3 inNormal;
layout(location = 0) out vec3 vNormal;
void main() {
    vNormal = mat3(pc.model) * inNormal;      // use the normal matrix if non-uniform scale
    gl_Position = cam.viewProj * pc.model * vec4(inPos, 1.0);
}
```

```glsl
// mesh.frag
#version 460
layout(set = 1, binding = 0) uniform sampler2D albedo;
layout(location = 0) in vec3 vNormal;
layout(location = 0) out vec4 outColor;
void main() {
    float ndl = max(dot(normalize(vNormal), normalize(vec3(0.3, 1.0, 0.2))), 0.0);
    outColor = vec4(vec3(0.1 + 0.9 * ndl), 1.0);
}
```

WebGL 2 / GLES fragment shader (note `precision`):

```glsl
#version 300 es
precision highp float;
uniform sampler2D uTex;
in vec2 vUv;
out vec4 fragColor;
void main() { fragColor = texture(uTex, vUv); }
```

Compute with subgroup reduction:

```glsl
#version 460
#extension GL_KHR_shader_subgroup_arithmetic : require
layout(local_size_x = 256) in;
layout(std430, binding = 0) readonly buffer In  { float values[]; };
layout(std430, binding = 1) writeonly buffer Out { float sums[]; };
shared float partial[64];
void main() {
    uint i = gl_GlobalInvocationID.x;
    float v = i < values.length() ? values[i] : 0.0;
    float s = subgroupAdd(v);
    if (subgroupElect()) partial[gl_SubgroupID] = s;
    barrier();
    if (gl_LocalInvocationIndex == 0) {
        float total = 0.0;
        for (uint w = 0; w < gl_NumSubgroups; ++w) total += partial[w];
        sums[gl_WorkGroupID.x] = total;
    }
}
```

Shadertoy-style SDF circle with anti-aliasing:

```glsl
float circle(vec2 p, float r) { return length(p) - r; }
void mainImage(out vec4 o, in vec2 fragCoord) {
    vec2 p = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
    float d = circle(p, 0.5);
    float aa = fwidth(d);
    o = vec4(vec3(1.0 - smoothstep(-aa, aa, d)), 1.0);
}
```

## 7. Top pitfalls and error-message fixes

| Error / symptom (glslang or driver text) | Cause | Fix |
|---|---|---|
| `ERROR: 0:1: '' : No precision specified for (float)` (or `declaration must include a precision qualifier for type`) | GLSL ES fragment shader without default precision [2] | Add `precision highp float;` (or `mediump`) after `#version` |
| `'=' : cannot convert from 'const int' to 'temp highp float'` | GLSL ES / strict compilers forbid implicit int->float | Write float literals: `1.0`, `float(i)` |
| `#version directive must occur on the first line` / `'#version' : must occur first in shader` | Text (or a BOM, or an injected `#define`) before `#version` | Put `#version` on line 1; inject defines after it |
| Object appears transposed / wrong rotation | Uploaded a row-major CPU matrix with `transpose = GL_FALSE`, or mixed `v * M` / `M * v` | Upload column-major (GLM default) or pass `GL_TRUE`; use `M * v` |
| `vec3` array in a UBO/SSBO reads shifted values | std140/std430 align `vec3` to 16 bytes; std140 pads array stride to 16 [6] | Use `vec4` or pad explicitly; mirror with `alignas(16)` in C++; or `scalar` layout in Vulkan |
| `'location' : SPIR-V requires location for user input/output` | Vulkan GLSL needs explicit `layout(location = N)` [4] | Add locations to every `in`/`out` |
| `'uniform' : non-opaque uniforms outside a block are not allowed (vulkan)` | Loose `uniform float x;` is not allowed for Vulkan targets | Put it in a `uniform` block or push constant |
| Vulkan: `Validation Error: [ VUID-...-layout-07990 ]` / `descriptor ... not compatible with pipeline layout` | Shader `set`/`binding`/type differs from VkDescriptorSetLayout | Reflect with SPIRV-Reflect or match by hand; same descriptor type and stage flags |
| `'barrier' : barrier() may only be used in control flow which is uniform` or GPU hang | `barrier()` inside a branch some invocations skip or after an early `return` | Remove early returns before barriers; guard work, not the barrier |
| Blocky or wrong mip textures inside an `if` | Implicit derivatives in non-uniform control flow | Use `textureLod`/`textureGrad`, or move `texture()` outside the branch |
| `'texture2D' : no matching overloaded function found` in `#version 330`+ | Old GLSL 1.x function names | Use `texture()`; `gl_FragColor` becomes a declared `out vec4` |
| `'gl_FragColor' : undeclared identifier` in `#version 300 es` | Removed in ES 3.00/core profile | Declare `out vec4 fragColor;` |
| NaN / black pixels after lighting | `normalize(vec3(0))`, `pow(neg, p)`, `0.0/0.0`, `acos(1.0001)` | Clamp inputs: `max(len, 1e-6)`, `pow(max(x,0.0),p)`, `acos(clamp(x,-1.0,1.0))` |
| Shader compiles on NVIDIA, fails on Mesa/Intel/mobile | NVIDIA front-end accepts non-standard code (Cg-isms like `float3`, `saturate`, implicit casts) | Validate with `glslang` in CI; avoid vendor leniency |
| Integer `%` with negatives or `mod()` on negative floats differs from Luau | `mod(x,y) = x - y*floor(x/y)` (like Luau `%`), but integer `%` on negatives is undefined in GLSL | Use `mod()` for floats; keep integer operands non-negative |

## 8. Performance

- Prefer `mediump` on mobile GLES for colors/UVs (16-bit ALU, halved register pressure); keep positions/depth `highp`.
- Minimise state changes and program switches in OpenGL; use UBOs/SSBOs with persistent mapping, multi-draw indirect (`glMultiDrawElementsIndirect`), bindless textures (`GL_ARB_bindless_texture`) where supported.
- Workgroup size 64 or 256; use subgroup ops before shared memory.
- Avoid dynamic indexing into local arrays (spills to memory on many GPUs) and large uniform arrays indexed per pixel.
- Branch on uniforms (cheap) rather than per-pixel data; flatten small branches.
- In WebGL, shader compile and link are expensive: use `KHR_parallel_shader_compile` and compile at load, not during gameplay.

## 9. Security

- WebGL runs untrusted GLSL from any web page; browsers translate and validate it through **ANGLE** (shader translator) before the driver sees it, add bounds checks and loop limits where needed [11]. Native OpenGL apps that accept user shaders (mods, Shadertoy-like tools) have none of that protection: validate with glslang, limit loop counts, and expect driver crashes.
- `robustBufferAccess` / `robustness2` in Vulkan and `GL_KHR_robustness` in GL make out-of-bounds reads return zero or defined values; enable them when running untrusted content.
- GPU hangs trigger TDR (Windows, ~2 s) or context loss (`GL_CONTEXT_LOST`, WebGL `webglcontextlost`); handle loss and recreate resources.
- Shared memory and uninitialized variables can leak data from previous workloads; initialise before use.

## 10. Game-dev usage

- **Godot**: Godot shading language (`shader_type spatial; void fragment() { ALBEDO = ...; }`) is GLSL-like and compiles to GLSL/SPIR-V; compute shaders in Godot 4 are written in GLSL with a `#[compute]` header and run through `RenderingDevice` [12].
- **Vulkan engines** (custom, id Tech, many indies) author GLSL or HLSL and ship SPIR-V.
- **Web games** (three.js, Babylon.js, PlayCanvas): GLSL ES 3.00 for WebGL 2; these engines increasingly also emit WGSL for WebGPU (three.js TSL node system).
- **Unity**: accepts `GLSLPROGRAM` only for OpenGL targets; normal path is HLSL cross-compiled. **Unreal**: HLSL source, GLSL generated for OpenGL ES/Vulkan Android.
- **Roblox**: there is **no user shader language**; use ParticleEmitter, Beam, Trail, SurfaceAppearance, Highlight and post-processing instances. Do not offer GLSL as a Roblox solution.

## 11. Cheat sheet vs Luau

| Concept | Luau (Roblox) | GLSL |
|---|---|---|
| Vector | `Vector3.new(x,y,z)` | `vec3(x, y, z)` |
| Transform | `CFrame`, `cf * v` | `mat4 M; M * vec4(v, 1.0)` (column-major) |
| Inverse transform | `cf:Inverse()` | `inverse(M)` (expensive; precompute on CPU) |
| Dot / cross | `a:Dot(b)`, `a:Cross(b)` | `dot(a, b)`, `cross(a, b)` |
| Magnitude / unit | `v.Magnitude`, `v.Unit` | `length(v)`, `normalize(v)` |
| Clamp | `math.clamp(x, a, b)` | `clamp(x, a, b)` |
| Lerp | `a:Lerp(b, t)`, `math.lerp` | `mix(a, b, t)` |
| Smooth step | (TweenService easing) | `smoothstep(e0, e1, x)` |
| Modulo | `%` (floored) | `mod(x, y)` (floored, float); `%` int only |
| Floor division | `//` | `int(floor(x / y))` or `/` on ints (truncates) |
| Arrays | 1-based, dynamic tables | 0-based fixed arrays; runtime-sized only as last SSBO member |
| Recursion | allowed | forbidden |
| Literals | `1` and `1.0` are the same number | `1` is int, `1.0` is float; ES forbids mixing |
| Entry point | script runs top to bottom | `void main()` per stage, run per vertex/fragment/invocation |
| Errors | `error`, `pcall` | none at runtime; compile log only |
| Strings | yes | none |

## 12. Recent changes and version notes

- No new core GLSL version after 4.60; the GLSL spec repository still receives revisions and extension specs [1][5].
- Vulkan-era extensions widely used in 2025-2026: `GL_EXT_mesh_shader`, `GL_EXT_ray_tracing`/`GL_EXT_ray_query`, `GL_EXT_buffer_reference` (pointers to device addresses), `GL_EXT_scalar_block_layout`, `GL_EXT_nonuniform_qualifier` (`nonuniformEXT(i)`), `GL_EXT_shader_explicit_arithmetic_types`, `GL_KHR_shader_subgroup_*`, `GL_EXT_debug_printf`, `GL_KHR_cooperative_matrix` [5].
- Many Vulkan projects are moving new code to **Slang** (Khronos-hosted since November 2024, shipped in the Vulkan SDK) or HLSL; GLSL remains the lingua franca for OpenGL/WebGL and Godot [13].
- WebGL 2 is still GLSL ES 3.00; WebGPU uses WGSL, not GLSL.

## Sources

1. https://registry.khronos.org/OpenGL/specs/gl/GLSLangSpec.4.60.pdf (accessed 2026-10-13)
2. https://registry.khronos.org/OpenGL/specs/es/3.2/GLSL_ES_Specification_3.20.pdf (accessed 2026-10-13)
3. https://github.com/KhronosGroup/glslang (accessed 2026-10-13)
4. https://github.com/KhronosGroup/GLSL/blob/main/extensions/khr/GL_KHR_vulkan_glsl.txt (accessed 2026-10-13)
5. https://github.com/KhronosGroup/GLSL (accessed 2026-10-13)
6. https://docs.vulkan.org/guide/latest/shader_memory_layout.html (accessed 2026-10-13)
7. https://github.com/google/shaderc (accessed 2026-10-13)
8. https://github.com/KhronosGroup/SPIRV-Cross (accessed 2026-10-13)
9. https://github.com/gfx-rs/wgpu/tree/trunk/naga (accessed 2026-10-13)
10. https://github.com/KhronosGroup/Vulkan-ValidationLayers/blob/main/docs/debug_printf.md (accessed 2026-10-13)
11. https://registry.khronos.org/webgl/specs/latest/2.0/ (accessed 2026-10-13)
12. https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html (accessed 2026-10-13)
13. https://www.khronos.org/news/press/khronos-group-launches-slang-initiative-hosting-open-source-compiler-contributed-by-nvidia (accessed 2026-10-13)
14. https://registry.khronos.org/OpenGL/index_gl.php (accessed 2026-10-13)
