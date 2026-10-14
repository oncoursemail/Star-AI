# Sources for unity-rendering-performance

Checked against official Unity documentation (Unity 6.6 / 6000.6 manual, URP 17.7, Entities 6.7, Burst 1.8, Test Framework 1.9) on 2026-10-13. The guidance is written in STAR's own words; Unity documentation is licensed CC BY-NC-ND, so no text is copied.

| Claim in the skill | Documentation page |
|---|---|
| URP, HDRP and Built-in; Built-in is deprecated and supported through the 6.7 LTS lifecycle | https://docs.unity3d.com/Manual/render-pipelines-overview.html |
| GPU Resident Drawer requirements: Forward+/Deferred+, SRP Batcher, BatchRendererGroup variants Keep All; incompatible objects fall back | https://docs.unity3d.com/Manual/urp/gpu-resident-drawer.html |
| Custom URP passes through the render graph API | https://docs.unity3d.com/Manual/urp/render-graph.html |
| SRP Batcher compatibility | https://docs.unity3d.com/Manual/SRPBatcher.html |
| EntityCommandBuffer records structural changes from jobs for main-thread playback; one ECB per job | https://docs.unity3d.com/Packages/com.unity.entities@6.7/manual/systems-entity-command-buffers.html |
| ECB system singletons (EndSimulationEntityCommandBufferSystem.Singleton), CreateCommandBuffer(state.WorldUnmanaged), AsParallelWriter; do not play back or dispose them yourself | https://docs.unity3d.com/Packages/com.unity.entities@6.7/manual/systems-entity-command-buffer-automatic-playback.html |
| Burst compiles a high-performance subset of C# | https://docs.unity3d.com/Packages/com.unity.burst@1.8/ |
| Profiler and GC guidance | https://docs.unity3d.com/Manual/Profiler.html and https://docs.unity3d.com/Manual/performance-garbage-collector.html |
| Managed code stripping, link.xml and Preserve | https://docs.unity3d.com/Manual/managed-code-stripping.html |
| Build Profiles window, platform vs custom profiles | https://docs.unity3d.com/Manual/build-profiles.html |
| -batchmode, -nographics, -projectPath, -executeMethod, -activeBuildProfile, -build, -logFile; exit code 1 on exception; -quit with -runTests quits before tests finish | https://docs.unity3d.com/Manual/EditorCommandLineArguments.html |
| Unity Test Framework EditMode and PlayMode tests | https://docs.unity3d.com/Packages/com.unity.test-framework@1.9/ |

API names verified against the official reference on 2026-10-13: EntityCommandBuffer, EntityCommandBuffer.AsParallelWriter, EndSimulationEntityCommandBufferSystem, EntityCommandBufferSystem.Singleton.CreateCommandBuffer, SystemAPI.GetSingleton, BatchRendererGroup, command-line flags -batchmode -nographics -quit -projectPath -executeMethod -buildTarget -activeBuildProfile -build -logFile. Not re-fetched (long-standing names): ChunkIndexInQuery, IEnableableComponent, SystemAPI.Query, IJobEntity, ProfilerMarker, UnityEngine.Pool.ObjectPool, -runTests, -testPlatform, -testResults, RecordRenderGraph.
