# Shader pitfalls and translation tables (HLSL, GLSL, WGSL, Slang)

Checked 2026-10-13. Error texts vary by compiler version; match on the key words.

## Error -> cause -> fix

| Language | Error or symptom | Cause | Fix |
|---|---|---|---|
| WGSL | `'textureSample' must only be called from uniform control flow` | implicit-derivative sample inside a branch on per-fragment data | sample before the branch, or `textureSampleLevel` / `textureSampleGrad` |
| WGSL | `'workgroupBarrier' must only be called from uniform control flow` + `builtin 'local_id' may be non-uniform` | barrier inside `if (lid.x < k)` or after early return | move barrier outside the branch; guard the work |
| WGSL (naga) | `Required uniformity of control flow for IMPLICIT_LEVEL ... is not fulfilled` | same rule, wgpu/Firefox wording | same fix |
| WGSL | `no matching overload` / `cannot convert` between `i32`, `u32`, `f32` | no implicit conversions | `f32(i)`, `u32(x)`, suffixes `1u`, `1i`, `1.0` |
| WGSL | uniform array element alignment must be 16 bytes | `array<f32, N>` in `var<uniform>` | `array<vec4f, N/4>` or `var<storage, read>` |
| WGSL | `Binding size ... is smaller than the minimum binding size` | buffer smaller than the struct | size buffers from the WGSL layout (vec3 aligned to 16) |
| WGSL | `@workgroup_size` exceeds `maxComputeInvocationsPerWorkgroup` | default limit 256 | reduce or request a higher limit |
| WGSL | `f16` used without extension | missing `enable f16;` or device feature | request `shader-f16`, add `enable f16;` |
| GLSL ES | `No precision specified for (float)` | fragment stage has no default float precision | `precision highp float;` |
| GLSL ES | `cannot convert from 'const int' to 'float'` | no implicit int to float | write `1.0`, `float(i)` |
| GLSL | `#version directive must occur on the first line` | BOM or injected text first | `#version` on line 1, defines after |
| GLSL | `'gl_FragColor' : undeclared identifier` | removed in core / ES 3.00 | `out vec4 fragColor;` |
| GLSL | `'texture2D' : no matching overloaded function` | GLSL 1.x name | `texture()` |
| GLSL Vulkan | `SPIR-V requires location for user input/output` | missing `layout(location = N)` | add locations |
| GLSL Vulkan | `non-opaque uniforms outside a block are not allowed` | loose `uniform float x;` | uniform block or push constant |
| Vulkan | `descriptor ... not compatible with pipeline layout` (VUID) | set/binding/type mismatch | reflect with SPIRV-Reflect, match layouts |
| GLSL | `barrier() may only be used in ... uniform` control flow / GPU hang | barrier in divergent code | hoist barrier, remove early return |
| HLSL | `operator cannot be used with built-in type 'vector<bool, N>'` | HLSL 2021 removed elementwise `&&`, `||`, `?:` | `and()`, `or()`, `select()` |
| HLSL | `implicit truncation of vector type` | `float4` assigned to `float3` | explicit swizzle, `-WX` |
| HLSL | cbuffer array reads garbage | each array element is 16-byte aligned | `float4 arr[N/4]` and index `[i/4][i%4]` |
| HLSL | `Root Signature doesn't match` shader | register not covered by root signature | align root signature ranges |
| HLSL to Vulkan | binding collisions between t0, s0, u0, b0 | DXC maps all register classes to the same binding numbers | `[[vk::binding(b, s)]]` or `-fvk-t-shift` etc. |
| HLSL | `DXGI_ERROR_DEVICE_REMOVED` / `DEVICE_HUNG` | infinite loop, divergent barrier, bad bindless index | DRED, GPU-based validation, bound loops |
| HLSL | wrong texels on AMD with bindless | per-lane index without `NonUniformResourceIndex` | wrap the index |
| Slang | `undefined identifier` across modules | `internal` default visibility since language 2025 | mark `public` |
| Slang | errors after `-std 2026` | tuples for `(a, b)`, `dyn` required, no struct inheritance | update code per language-version notes |
| Slang | breakage after compiler upgrade | weekly releases with occasional breaking changes | pin version in CI |
| All | object transposed / rotates wrong | matrix packing and multiply order mismatch | one convention end to end |
| All | NaN, black or white pixels | `normalize(0)`, `pow(neg, p)`, `x/0`, `acos(>1)` | `max(x, 1e-6)`, `pow(max(x,0),p)`, `clamp` |
| All | blocky mips inside branches | derivatives in non-uniform flow | explicit LOD or gradients |

## Syntax translation

| Concept | HLSL | GLSL | WGSL | Slang |
|---|---|---|---|---|
| 3-float vector | `float3` | `vec3` | `vec3f` / `vec3<f32>` | `float3` |
| 4x4 matrix | `float4x4` | `mat4` | `mat4x4f` | `float4x4` |
| transform | `mul(M, v)` | `M * v` | `M * v` | `mul(M, v)` |
| lerp | `lerp(a,b,t)` | `mix(a,b,t)` | `mix(a,b,t)` | `lerp(a,b,t)` |
| saturate | `saturate(x)` | `clamp(x,0.0,1.0)` | `saturate(x)` | `saturate(x)` |
| fraction | `frac(x)` | `fract(x)` | `fract(x)` | `frac(x)` |
| floored mod | `x - y*floor(x/y)` (`fmod` truncates) | `mod(x,y)` | `x - y*floor(x/y)` (`%` truncates) | `x - y*floor(x/y)` |
| ternary | `c ? a : b` (scalar), `select(c,a,b)` | `c ? a : b`, `mix(b,a,bvec)` | `select(b, a, c)` | `select(c,a,b)` |
| derivatives | `ddx`, `ddy`, `fwidth` | `dFdx`, `dFdy`, `fwidth` | `dpdx`, `dpdy`, `fwidth` | `ddx`, `ddy` |
| sample | `t.Sample(s, uv)` | `texture(sampler2D, uv)` | `textureSample(t, s, uv)` | `t.Sample(s, uv)` |
| sample explicit LOD | `t.SampleLevel(s, uv, l)` | `textureLod(tex, uv, l)` | `textureSampleLevel(t, s, uv, l)` | `t.SampleLevel(s, uv, l)` |
| texel fetch | `t.Load(int3(p, mip))` | `texelFetch(tex, p, mip)` | `textureLoad(t, p, mip)` | `t.Load(...)` |
| constant buffer | `cbuffer C : register(b0) {}` | `layout(std140, binding=0) uniform C {}` | `@group(0) @binding(0) var<uniform> c : C;` | `ConstantBuffer<C> c;` / `ParameterBlock<C>` |
| storage buffer | `RWStructuredBuffer<T> b : register(u0);` | `layout(std430, binding=1) buffer B { T b[]; };` | `var<storage, read_write> b : array<T>;` | `RWStructuredBuffer<T> b;` |
| shared memory | `groupshared float s[64];` | `shared float s[64];` | `var<workgroup> s : array<f32, 64>;` | `groupshared float s[64];` |
| workgroup size | `[numthreads(64,1,1)]` | `layout(local_size_x = 64) in;` | `@compute @workgroup_size(64)` | `[shader("compute")] [numthreads(64,1,1)]` |
| barrier | `GroupMemoryBarrierWithGroupSync()` | `barrier()` | `workgroupBarrier()` | `GroupMemoryBarrierWithGroupSync()` |
| global thread id | `SV_DispatchThreadID` | `gl_GlobalInvocationID` | `@builtin(global_invocation_id)` | `SV_DispatchThreadID` |
| clip position out | `SV_Position` | `gl_Position` | `@builtin(position)` | `SV_Position` |
| fragment output | `: SV_Target0` | `layout(location=0) out vec4` | `-> @location(0) vec4f` | `: SV_Target` |
| wave/subgroup sum | `WaveActiveSum(x)` | `subgroupAdd(x)` | `subgroupAdd(x)` (enable subgroups) | `WaveActiveSum(x)` |
| discard | `discard;` / `clip(x)` | `discard;` | `discard;` | `discard;` |
| constants | `static const float K = 1;` | `const float K = 1.0;` | `const K = 1.0;` / `override` | `static const float K = 1;` |
| entry naming | any name, chosen at compile `-E` | `void main()` per file | any name with stage attribute | any name with `[shader(...)]` |

## Luau to shader quick map

| Luau | Shader |
|---|---|
| `Vector3.new(x, y, z)` | `float3` / `vec3` / `vec3f` |
| `CFrame` | 4x4 (or 3x4) matrix |
| `v.Magnitude`, `v.Unit` | `length(v)`, `normalize(v)` |
| `a:Dot(b)`, `a:Cross(b)` | `dot(a, b)`, `cross(a, b)` |
| `math.clamp(x, a, b)` | `clamp(x, a, b)` |
| `a:Lerp(b, t)` | `lerp` (HLSL/Slang) or `mix` (GLSL/WGSL) |
| tables, 1-based | fixed arrays and buffers, 0-based |
| `pcall`, `error` | none: compile errors only, runtime NaN or zeros |
| Roblox visual effects | ParticleEmitter, Beam, Trail, SurfaceAppearance, post-processing; no custom shaders |
