---
name: unity-rendering-performance
description: Unity 6 rendering pipeline choice, batching, DOTS (Entities, Burst, Jobs) basics, profiling and GC, and builds (IL2CPP, Build Profiles, batchmode tests). Use for Unity frame-rate problems, URP setup, ECS code, or CI builds.
---
# Unity rendering, performance and builds
Measure first: profile a development build on the target device, not the editor.
- Pipelines: URP for nearly every new project; HDRP only for high-end PC and console realism; Built-in is deprecated, so migrate (Render Pipeline Converter fixes pink materials).
- Keep the SRP Batcher on with compatible shaders (Shader Graph, URP Lit); MaterialPropertyBlock breaks it. Many repeated meshes: GPU Resident Drawer (Forward+ path, BatchRendererGroup variants Keep All, no Animator or OnBecameVisible on those objects).
- Custom URP passes use Render Graph (RecordRenderGraph); old Execute-style passes are legacy.
- Lighting: bake static lighting, use light probes or Adaptive Probe Volumes for moving objects, few realtime shadows. Add LODGroup and occlusion culling.
- Tools: CPU Profiler (GC Alloc column), Memory Profiler snapshots, Frame Debugger for broken batches. Mark code with ProfilerMarker.
- GC: zero allocations per frame. No LINQ, string building, boxing, capturing lambdas or new WaitForSeconds in Update. Use NonAlloc physics queries and UnityEngine.Pool.ObjectPool<T> for bullets and effects.
- Jobs and Burst: [BurstCompile] code uses only unmanaged structs and Native containers; no classes, string or managed arrays. Complete handles before reading and dispose native containers.
- Entities: IComponentData structs, Baker classes in SubScenes, ISystem with SystemAPI.Query, IJobEntity. Structural changes (create, destroy, add or remove components) are illegal in jobs and during iteration: record them in an EntityCommandBuffer from EndSimulationEntityCommandBufferSystem.Singleton (CreateCommandBuffer(state.WorldUnmanaged), AsParallelWriter with ChunkIndexInQuery as sort key). Toggle often-changing state with IEnableableComponent.
- IL2CPP for release, iOS, consoles and Web; stripping removes reflection-only types, so keep them with link.xml or [Preserve].
- Build Profiles (File > Build Profiles) hold per-target scenes and defines. CI: -batchmode -nographics -projectPath -executeMethod or -activeBuildProfile with -build, -logFile; throw to exit 1. Tests: -runTests -testPlatform EditMode or PlayMode -testResults, and never add -quit to a test run.
- Roblox map: MicroProfiler -> Unity Profiler, StreamingEnabled -> Addressables or additive scenes, instance budget -> draw calls and batches.
