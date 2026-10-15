# HLSL for STAR (research, checked 2026-10-13)

Status: verified on 2026-10-13: Shader Model 6.9 is retail (Agility SDK 1.619, DXC 1.9.2602.x, announced 2026-02-26) [1][2]; Agility SDK 1.719-preview carries preview-only features (fence barriers, VPblit 3D LUT, extension mechanism) [1]. The DXC SPIR-V backend ships in the same release [2]. Unverified as of 2026-10-13: whether DXC has switched its default language version to HLSL 202x (Microsoft said in 2024 "likely sometime in 2025 or 2026") [3], and the exact date Clang/LLVM HLSL becomes production DXIL [4]. Cooperative Vector (SM 6.9 preview) is deprecated in favour of a redesign targeted at SM 6.10 [1].

HLSL (High-Level Shader Language) is Microsoft's C-like shading language for Direct3D. Today it is also the most common *source* language for Vulkan (via DXC `-spirv`), for Unreal Engine (`.usf`/`.ush`), for Unity (HLSL inside ShaderLab), and it is what Slang grew out of.

## 1. Mental model

- A shader is a **pure-ish function run in massive parallel** by the GPU, once per vertex, pixel, thread or ray. There is no `main` program loop, no heap, no I/O, no recursion (except ray-tracing `TraceRay` which recurses through the driver, bounded by `MaxTraceRecursionDepth`).
- Inputs arrive as **resources bound by the CPU** (constant buffers, textures, buffers, samplers) plus **per-invocation values** tagged with **semantics** (`SV_Position`, `SV_DispatchThreadID`, `TEXCOORD0`). Outputs leave through semantics (`SV_Target0`, `SV_Depth`) or through writes to UAVs (`RWTexture2D`, `RWStructuredBuffer`).
- Compilation is offline (or at load time): **HLSL source -> DXC -> DXIL** (an LLVM-based bytecode, signed/validated) for D3D12, or **-> SPIR-V** for Vulkan. Legacy **FXC** compiles SM 2.0-5.1 to DXBC; use it only for D3D11-era code [5].
- The **Shader Model** (SM 5.0, 5.1, 6.0 ... 6.9) is the feature level contract between compiler and driver. Pick a target profile such as `ps_6_6`, `cs_6_8`, `lib_6_9` [6].
- The **root signature** (D3D12) or **descriptor set layout / pipeline layout** (Vulkan) is the ABI between the CPU binding model and `register(t0, space1)` style declarations in the shader. Most "my shader reads zeros" bugs are binding mismatches, not math bugs.
- Execution is **SIMT**: lanes of a **wave** (32 on NVIDIA/Intel commonly, 32 or 64 on AMD) execute in lockstep; divergent branches serialize. Pixel shaders run in **2x2 quads** so derivatives (`ddx`, `ddy`, implicit mip selection in `Sample`) work.

## 2. Type system

- Scalars: `bool`, `int` (32-bit), `uint`, `float` (32-bit), `double` (optional, slow), `half` (maps to 32-bit unless `-enable-16bit-types`), `min16float`/`min16int` (precision hints), `int16_t`, `uint16_t`, `float16_t` (SM 6.2+ with `-enable-16bit-types`), `int64_t`/`uint64_t` (SM 6.0+; required at SM 6.9) [1][6].
- Vectors: `float3`, `int4`, `vector<float, 3>`. **SM 6.9 long vectors**: `vector<T, N>` with N from 5 up to 1024 for load/store/elementwise ops [1]. Swizzles `.xyzw`/`.rgba`, write masks `v.xz = 0`.
- Matrices: `float4x4`, `matrix<float, 3, 4>` (rows x columns). **Default packing is column_major** for uniform data; declaration `row_major float4x4 M;` or compiler flag `-Zpr` changes it. Indexing `M[i]` returns a **row** regardless of packing. `mul(v, M)` treats `v` as a row vector; `mul(M, v)` as a column vector [7].
- Structs, arrays (fixed-size; `float a[8]`), no pointers in classic HLSL. Templates and operator overloading arrived with **HLSL 2021** (`-HV 2021`, DXC default since 1.7) [8]; HLSL 2021 also changed logical operators: `&&`, `||`, `?:` no longer work elementwise on vectors - use `and()`, `or()`, `select()` [8].
- Resource types: `Texture2D<float4>`, `RWTexture2D<float4>`, `Buffer<uint>`, `StructuredBuffer<T>`, `RWStructuredBuffer<T>`, `ByteAddressBuffer`, `RWByteAddressBuffer`, `ConstantBuffer<T>` / `cbuffer`, `SamplerState`, `SamplerComparisonState`, `RaytracingAccelerationStructure`, `AppendStructuredBuffer`.
- **Bindless** (SM 6.6): `ResourceDescriptorHeap[i]` and `SamplerDescriptorHeap[i]` give dynamic resources; wrap a non-uniform index in `NonUniformResourceIndex(i)` [9].
- Implicit conversions are generous (float->int truncation, vector truncation with warning `implicit truncation of vector type`). Treat truncation warnings as errors (`-WX`).
- Constant buffer packing (legacy cbuffer rules): members pack into 16-byte registers and **may not straddle a 16-byte boundary**; arrays put each element on its own 16-byte register. A `float3` followed by a `float` packs into one register; a `float3` followed by a `float3` does not [10].

```hlsl
cbuffer Frame : register(b0, space0)
{
    float4x4 ViewProj;      // 64 bytes, column_major by default
    float3   CameraPos;     // offset 64
    float    Time;          // offset 76 (shares the register with CameraPos)
    float    Weights[4];    // each element takes a 16-byte register: 64 bytes, not 16!
};
```

## 3. Runtime, concurrency and async model

- **Graphics pipeline**: Input Assembler -> Vertex (VS) -> optional Hull/Domain (tessellation) -> optional Geometry -> Rasterizer -> Pixel (PS) -> Output Merger. **Mesh pipeline** (SM 6.5): Amplification (AS) -> Mesh (MS) -> Rasterizer -> PS. **Compute** (CS), **ray tracing** (lib target: raygen, miss, closest-hit, any-hit, intersection, callable), **work graphs** (SM 6.8, `[NodeLaunch("broadcasting")]`) [6][11].
- Compute: `[numthreads(X,Y,Z)]`, built-ins `SV_DispatchThreadID`, `SV_GroupID`, `SV_GroupThreadID`, `SV_GroupIndex`. Shared memory: `groupshared float tile[256];` (max 32 KB per group in D3D12).
- Barriers: `GroupMemoryBarrierWithGroupSync()` (LDS visibility + execution barrier), `DeviceMemoryBarrier()`, `AllMemoryBarrierWithGroupSync()`. A `...WithGroupSync` barrier must be reached by every thread of the group: **never put it inside divergent control flow** (undefined behaviour / hang).
- **Wave intrinsics** (SM 6.0+): `WaveGetLaneCount`, `WaveGetLaneIndex`, `WaveIsFirstLane`, `WaveActiveSum`, `WaveActiveMin`, `WaveActiveAllTrue`, `WaveActiveBallot`, `WavePrefixSum`, `WaveReadLaneAt`, `WaveReadLaneFirst`, `QuadReadAcrossX` [12]. Do not hardcode wave size; SM 6.6 `[WaveSize(32)]` and SM 6.8 `[WaveSize(min, max, preferred)]` constrain it [11].
- **Uniformity**: values that are the same for all lanes (constant buffer data, `SV_GroupID` within a group) are uniform; per-lane values are divergent. Derivatives (`ddx`, `ddy`, `Sample` without explicit LOD) inside divergent control flow give undefined results; use `SampleLevel`/`SampleGrad` there or hoist the sample.
- Pixel shader helper lanes: pixels outside the triangle still run in a quad for derivatives; `discard`/`clip()` turns a lane into a helper. SM 6.7 `IsHelperLane()`.
- There is no async/await. The "async" layer is the CPU API: command lists, fences, queues. Shader-side asynchrony exists only as **async compute queues** scheduling and **Shader Execution Reordering** (`HitObject`, `MaybeReorderThread`, retail in SM 6.9) [1].

## 4. Tooling and package management

- **DXC** (`dxc.exe`, `dxcompiler.dll`, open source, github.com/microsoft/DirectXShaderCompiler): `dxc -T ps_6_6 -E main -HV 2021 -Zi -Qembed_debug -Fo out.dxil shader.hlsl`. Useful flags: `-O3`/`-Od`, `-WX`, `-enable-16bit-types`, `-Zpr`/`-Zpc` (row/column major), `-spirv -fspv-target-env=vulkan1.3` for Vulkan, `-fvk-use-dx-layout`, `-fvk-bind-register`, `-Fre` reflection, `-Qstrip_reflect` [2][13].
- Distributed via GitHub releases, the Windows SDK, NuGet `Microsoft.Direct3D.DXC`, and the Vulkan SDK (LunarG bundles DXC). The D3D12 runtime itself comes from NuGet `Microsoft.Direct3D.D3D12` (Agility SDK) [1].
- **FXC** (`fxc.exe`, Windows SDK): legacy SM <= 5.1, DXBC. Do not start new D3D12 work with it.
- **Clang HLSL** (LLVM upstream): in development, defaults to HLSL 202x; not yet the production DXIL path (unverified for 2026 status) [3][4].
- Reflection: `IDxcUtils::CreateReflection` -> `ID3D12ShaderReflection`; for SPIR-V use SPIRV-Reflect.
- Cross-compilation: HLSL -> SPIR-V (DXC) -> **SPIRV-Cross** -> GLSL/MSL; HLSL -> Metal via **Metal Shader Converter** (Apple, DXIL -> metallib); **naga** can parse SPIR-V and emit WGSL; **Slang** accepts most HLSL directly and emits DXIL, SPIR-V, Metal, WGSL, CUDA [14].
- Package management: none in the language. Engines manage includes (`#include "Common.ush"`), permutations (`#pragma multi_compile` in Unity, `FShaderPermutationDomain` in Unreal) and caches (PSO caches, `ID3D12PipelineLibrary`).
- Formatting/linting: clang-format works passably on HLSL; DXC warnings with `-WX` are the main lint.

## 5. Testing

- **PIX on Windows**: GPU captures, shader debugging with source stepping (needs `-Zi` and PDBs), timing captures, supports all SM 6.9 features [1].
- **RenderDoc**: D3D11/D3D12/Vulkan captures; pixel history, shader debugging for DXBC/DXIL (DXIL debugging support improved in RenderDoc 1.3x; verify on your version) and SPIR-V.
- **NVIDIA Nsight Graphics**, **AMD Radeon GPU Profiler/Analyzer**, **Intel GPA** for per-vendor counters and ISA.
- `printf` in HLSL: supported for Vulkan targets via `-spirv` (`printf` -> `NonSemantic.DebugPrintf`, read with the validation layer's debug printf) [13]. For D3D12, write debug values into an `RWStructuredBuffer` and read it back.
- **Unit-testing compute**: put pure math in `.hlsli` headers, write a tiny compute shader that runs test vectors and writes results to a UAV, read back on the CPU and compare with a CPU reference (tolerance with ULPs, not `==`). Microsoft's own `HLSLTests`/`ExecutionTests` in the DXC repo follow this pattern [2].
- Enable the **D3D12 debug layer** and **GPU-based validation** (`ID3D12Debug1::SetEnableGPUBasedValidation`) to catch out-of-bounds descriptor access and resource-state bugs; enable **DRED** for post-mortem after TDR.

## 6. Idiomatic patterns

Fullscreen triangle without a vertex buffer:

```hlsl
struct VSOut { float4 pos : SV_Position; float2 uv : TEXCOORD0; };

VSOut FullscreenVS(uint id : SV_VertexID)
{
    VSOut o;
    o.uv  = float2((id << 1) & 2, id & 2);          // (0,0) (2,0) (0,2)
    o.pos = float4(o.uv * float2(2, -2) + float2(-1, 1), 0, 1);
    return o;
}

Texture2D<float4> SceneColor : register(t0);
SamplerState      LinearClamp : register(s0);

float4 TonemapPS(VSOut i) : SV_Target0
{
    float3 c = SceneColor.Sample(LinearClamp, i.uv).rgb;
    c = c / (1.0 + c);                               // Reinhard
    return float4(pow(saturate(c), 1.0 / 2.2), 1);
}
```

Compute with groupshared reduction and wave ops:

```hlsl
StructuredBuffer<float>   Input  : register(t0);
RWStructuredBuffer<float> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };

groupshared float PartialSums[32];   // one slot per wave, assumes >= 8 lanes per wave for 256 threads

[numthreads(256, 1, 1)]
void SumCS(uint3 dtid : SV_DispatchThreadID, uint gi : SV_GroupIndex, uint3 gid : SV_GroupID)
{
    float v = dtid.x < Count ? Input[dtid.x] : 0.0;   // bounds check, no early return before the barrier
    float waveSum = WaveActiveSum(v);
    uint waveIndex = gi / WaveGetLaneCount();
    if (WaveIsFirstLane()) PartialSums[waveIndex] = waveSum;
    GroupMemoryBarrierWithGroupSync();                 // every thread reaches this
    if (gi == 0)
    {
        float total = 0;
        uint waves = (256 + WaveGetLaneCount() - 1) / WaveGetLaneCount();
        for (uint w = 0; w < waves; ++w) total += PartialSums[w];
        Output[gid.x] = total;
    }
}
```

Bindless material fetch (SM 6.6):

```hlsl
struct Material { uint albedoIndex; uint samplerIndex; float roughness; float pad; };
ConstantBuffer<Material> Mat : register(b1);

float4 PS(float2 uv : TEXCOORD0) : SV_Target
{
    Texture2D<float4> albedo = ResourceDescriptorHeap[NonUniformResourceIndex(Mat.albedoIndex)];
    SamplerState s = SamplerDescriptorHeap[Mat.samplerIndex];
    return albedo.Sample(s, uv);
}
```

HLSL 2021 template:

```hlsl
template<typename T> T Square(T x) { return x * x; }
float3 a = Square(float3(1, 2, 3));
bool3 m = and(a > 1, a < 5);            // HLSL 2021: use and()/or()/select() for vectors
float3 r = select(m, a, 0);
```

## 7. Top pitfalls and error-message fixes

| Error / symptom (text as reported by DXC or runtime) | Cause | Fix |
|---|---|---|
| Image is transposed / object rotates the wrong way | Matrix packing (column_major default) and `mul` argument order disagree with CPU layout | Pick one convention: CPU row-major + `row_major` / `-Zpr` + `mul(v, M)`, or transpose on upload and use `mul(M, v)` [7] |
| `error: use of undeclared identifier 'X'` after porting from FXC | DXC is clang-based and stricter; FXC-only intrinsics or implicit declarations | Declare it; replace FXC-only constructs; compile with `-HV 2021` and fix each diagnostic |
| `error: operator cannot be used with built-in type 'vector<bool, 3>'` (or similar for `&&` on vectors) | HLSL 2021 removed elementwise `&&`, `||`, `?:` on vectors [8] | Use `and()`, `or()`, `select()` |
| `warning: implicit truncation of vector type` | Assigning `float4` to `float3` etc. | Swizzle explicitly `.xyz`; build with `-WX` |
| Reads of a cbuffer field return garbage after the first array element | HLSL packs each array element on a 16-byte boundary [10] | Use `float4 arr[N/4]` and index `arr[i/4][i%4]`, or a StructuredBuffer |
| `error: Gradient operations are not affected by wave-sensitive data or control flow` / blurry or noisy sampling in branches | Implicit-derivative `Sample` in divergent flow | `SampleLevel`/`SampleGrad`, or sample before the branch |
| GPU hang / TDR, `DXGI_ERROR_DEVICE_REMOVED` (0x887A0005) or `DXGI_ERROR_DEVICE_HUNG` | Barrier in divergent code, infinite loop, out-of-bounds bindless index, >2 s workload | Enable DRED + GPU-based validation; move barriers to uniform code; bound loops; split dispatches |
| `D3D12 ERROR: ... Root Signature doesn't match Pixel Shader` | `register(tN, spaceM)` not covered by root signature ranges | Make root signature ranges match or use `[RootSignature(...)]` in HLSL |
| Vulkan: `Validation Error: ... descriptor set N binding M ... not declared in pipeline layout` with DXC SPIR-V | DXC maps `register(t0, space1)` to set 1 binding 0; all register classes (t/s/u/b) collapse onto bindings and can collide | Use `[[vk::binding(b, s)]]`, or `-fvk-t-shift`, `-fvk-s-shift`, `-fvk-u-shift`, `-fvk-b-shift` [13] |
| `error: validation errors ... Instructions should not read uninitialized value` | Reading an output or local before writing it on some path | Initialize every local and output (`= (VSOut)0;`) |
| NaN/Inf blowing up bloom, black pixels | `normalize(0)`, `pow(negative, x)`, divide by zero, `sqrt(-eps)` | `max(x, 1e-6)`, `pow(max(x,0), p)`, `rsqrt(max(dot(v,v), eps))`; check with `isnan()` |
| `error: Shader model 6.6 required for ResourceDescriptorHeap` / `invalid profile` | Target profile too low or runtime lacks Agility SDK | Compile `-T ps_6_6` or higher; ship Agility SDK; check `D3D12_FEATURE_SHADER_MODEL` |
| Non-uniform texture index produces corrupted texels on AMD | Missing `NonUniformResourceIndex` | Wrap per-lane indices in `NonUniformResourceIndex()` [9] |
| `half` math is not faster | `half` is 32-bit unless `-enable-16bit-types`; `min16float` is a hint only | Compile with `-enable-16bit-types` and use `float16_t`; profile |
| Depth precision z-fighting | Standard depth with far/near ratio too large | Reversed-Z (`near = 1`, `GREATER` compare) with float depth |

## 8. Performance

- Occupancy is bounded by **register (VGPR) pressure** and **groupshared** use; large local arrays spill to scratch memory. Inspect ISA with RGA/Nsight.
- Prefer `[numthreads]` multiple of 64 (AMD wave64) and 32; 64 or 256 are common.
- Use wave intrinsics over groupshared + barriers for reductions; use `WaveActiveBallot` for compaction.
- Divergent branches cost both sides; `[branch]` vs `[flatten]` hints. Keep pixel-shader branches coherent over screen regions.
- Bandwidth dominates: pack G-buffers, use `R11G11B10_FLOAT`, BC compression for textures, `half` (with 16-bit types) for ALU-bound mobile-class GPUs.
- `rcp`, `rsqrt`, `mad`, `saturate` (free modifier on many GPUs). Avoid `pow` with variable exponent in hot loops; `exp2`/`log2` are native.
- Shader permutations explode PSO compile time: use dynamic branches on uniform values (cheap, coherent) instead of compiling every combination; precompile PSOs and cache.

## 9. Security

- Treat shaders from mods/users as **untrusted code that can hang the GPU** (Denial of service via TDR) or read whatever resources are bound. Never bind other users' data into a shader you did not author.
- D3D12 bounds-checks typed/structured buffer reads to return 0 out of range for bound views, but bindless indices beyond the heap and raw device addresses are undefined; validate indices on the CPU or clamp in the shader.
- Windows TDR resets the GPU after ~2 seconds of a hung queue by default; long compute should be split into chunks.
- DXIL must be signed/validated (`dxil.dll`) to load without developer mode; do not ship unvalidated shaders.
- Uninitialized groupshared memory may contain data from another dispatch: always write before reading.

## 10. Game-dev usage

- **Unreal Engine**: `.usf`/`.ush` HLSL; material graph emits HLSL; Custom node HLSL; global shaders in plugins; cross-compiled to SPIR-V/Metal via DXC + ShaderConductor-like paths.
- **Unity**: ShaderLab wrapping HLSL (`HLSLPROGRAM ... ENDHLSL`), URP/HDRP shader libraries, Shader Graph emits HLSL; compute shaders are `.compute` HLSL.
- **Godot**: uses its own GLSL-like Godot shading language; compute uses GLSL (RenderingDevice). HLSL not native.
- **Bevy/wgpu**: WGSL primary; wgpu also accepts SPIR-V (so DXC-compiled HLSL works) and has a feature for HLSL-sourced SPIR-V passthrough.
- **Roblox**: there is **no user shader language** in Roblox. Visual effects use ParticleEmitter, Beam, Trail, SurfaceAppearance, post-processing effects (Bloom, ColorCorrection, DepthOfField, SunRays), and EditableImage/EditableMesh; do not tell users to write HLSL for Roblox.

## 11. Cheat sheet vs Luau

| Concept | Luau (Roblox) | HLSL |
|---|---|---|
| 3D vector | `Vector3.new(1,2,3)` (immutable, float32 components) | `float3(1,2,3)` value type, swizzles `.xzy` |
| 2D/4D vector | `Vector2`, no Vector4 | `float2`, `float4` |
| Transform | `CFrame` (rotation + position, 3x4) | `float4x4` / `float3x4`; `mul(M, v)` |
| Dot/cross | `a:Dot(b)`, `a:Cross(b)` | `dot(a,b)`, `cross(a,b)` |
| Length / unit | `v.Magnitude`, `v.Unit` | `length(v)`, `normalize(v)` |
| Clamp | `math.clamp(x, 0, 1)` | `clamp(x, 0, 1)` or `saturate(x)` |
| Lerp | `a:Lerp(b, t)`, `math.lerp` (2024+) | `lerp(a, b, t)` |
| Integer division | `//` | `/` on `int`/`uint` truncates |
| Indexing | 1-based tables | 0-based arrays, fixed size |
| Dynamic data | tables grow | no allocation; buffers sized by CPU |
| Recursion | allowed | not allowed (except DXR TraceRay depth) |
| Numbers | `number` = float64, plus `integer` type is not separate | `float` 32-bit, `int`/`uint` 32-bit, `half`, `double` optional |
| nil | `nil` everywhere | no null; out-of-range buffer reads return 0 |
| Concurrency | coroutines, task.spawn (single-threaded per actor) | thousands of lanes in lockstep waves |
| Errors | `error()`, pcall | none at runtime; NaN propagates silently |
| Type checking | `--!strict` | compile-time only, no reflection at runtime |

## 12. Recent changes and version notes

- **SM 6.9 retail (Feb 2026)** [1]: long vectors up to 1024 elements; `IsNormal()` and 16-bit `IsNan/IsInf/IsFinite`; native 16-bit ops, wave ops and 64-bit integer ops now required; DXR 1.2 HLSL: Opacity Micromaps and Shader Execution Reordering (`HitObject`, `MaybeReorderThread`) out of preview.
- **SM 6.8** (2024): work graphs, `[WaveSize(min,max,pref)]`, `SampleCmpLevel`, expanded comparison sampling, start vertex/instance location [11].
- **SM 6.7**: `IsHelperLane`, programmable sample offsets, raw gather, `QuadAny/QuadAll`, writeable MSAA textures.
- **SM 6.6**: dynamic resources (`ResourceDescriptorHeap`), 64-bit atomics, pack/unpack intrinsics, `WaveSize`, compute derivatives.
- **HLSL 2021** (DXC 1.7, default `-HV 2021`): templates, operator overloading, bitfields, strict vector logical ops [8]. **HLSL 202x**: conforming literals and other cleanups, default in Clang; DXC default switch unverified as of 2026-10-13 [3].
- DXC 1.9.2602 (Feb 2026) includes broad SPIR-V backend improvements [2].

## Sources

1. https://devblogs.microsoft.com/directx/shader-model-6-9-retail-and-more/ (accessed 2026-10-13)
2. https://github.com/microsoft/DirectXShaderCompiler/releases/tag/v1.9.2602 (accessed 2026-10-13)
3. https://devblogs.microsoft.com/directx/dxc-1-8-2405-available (HLSL 202x roadmap; accessed 2026-10-13)
4. https://clang.llvm.org/docs/HLSL/HLSLSupport.html (accessed 2026-10-13)
5. https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl (accessed 2026-10-13)
6. https://microsoft.github.io/DirectX-Specs/ (accessed 2026-10-13)
7. https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-per-component-math (accessed 2026-10-13)
8. https://github.com/microsoft/DirectXShaderCompiler/wiki/HLSL-2021 (accessed 2026-10-13)
9. https://microsoft.github.io/DirectX-Specs/d3d/HLSL_SM_6_6_DynamicResources.html (accessed 2026-10-13)
10. https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-packing-rules (accessed 2026-10-13)
11. https://microsoft.github.io/DirectX-Specs/d3d/HLSL_ShaderModel6_8.html (accessed 2026-10-13)
12. https://github.com/microsoft/DirectXShaderCompiler/wiki/Wave-Intrinsics (accessed 2026-10-13)
13. https://github.com/microsoft/DirectXShaderCompiler/blob/main/docs/SPIR-V.rst (accessed 2026-10-13)
14. https://shader-slang.org/ (accessed 2026-10-13)
15. https://github.com/microsoft/hlsl-specs (accessed 2026-10-13)
