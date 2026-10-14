---
name: unreal-rendering-performance
description: Unreal Engine 5 rendering and performance - Nanite, Lumen, Virtual Shadow Maps, MegaLights, World Partition, stat commands and Unreal Insights, PSO stutter, cooking and packaging with RunUAT. Use for Unreal frame rate, hitches, lighting artefacts, open-world streaming or build and packaging problems.
---
# Unreal Engine 5 rendering, performance and packaging
Measure before changing anything, in a packaged Development or Test build on the target hardware; editor numbers mislead.
- stat unit first: Game (game thread), Draw (render thread), GPU and RHIT; the biggest bounds the frame. Then stat game, stat gpu, stat scenerendering, stat streaming, stat net. Unreal Insights (-trace=cpu,gpu,frame,memory,loadtime) for timelines; ProfileGPU for one GPU frame; memreport -full and obj list for memory.
- Game thread: too many ticking actors (disable tick, tick intervals, managers), Blueprint loops, GetAllActorsOfClass or casts every frame, spawning and destroying (pool actors), GC spikes. Use the Significance Manager and animation budgeting for crowds.
- Nanite for high-poly opaque or masked static meshes; translucent materials are not Nanite; World Position Offset costs and invalidates Virtual Shadow Maps. Instanced Static Mesh or HISM for repeated non-Nanite meshes.
- Lumen gives dynamic GI and reflections; leaks come from walls thinner than about 10 cm or meshes without distance fields. Lumen Lite (5.8, beta) is the cheaper medium setting; MegaLights (production-ready in 5.8) handles many shadowed lights; Substrate materials are on by default since 5.7. SSGI is deprecated.
- Hitches the first time something appears are usually PSO or shader compilation: keep PSO precaching on, ship a bundled PSO cache, warm up on loading screens. Other hitches: synchronous loads (use soft references and async loading), GC, level streaming.
- Open worlds: World Partition grid streaming with Data Layers, HLODs and One File Per Actor; check streaming sources for clients.
- Scalability: sg.* groups and device profiles; never ship editor-only settings.
- Packaging: RunUAT BuildCookRun -project=<path to .uproject> -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory=<folder>; add -server -serverconfig=Development for a dedicated server (needs a source-built engine). Configurations: Debug, DebugGame, Development, Test, Shipping (no console, stats or logs).
- Assets referenced only by string paths are not cooked: add Primary Asset Labels or Asset Manager rules. Commit Source, Config, Content and the .uproject; never Binaries, Intermediate, Saved or DerivedDataCache. Lock binary assets.
- Automated tests: Automation Test framework or Functional Tests, run with UnrealEditor-Cmd and -ExecCmds="Automation RunTests <filter>; Quit" -unattended -nullrhi.
- Roblox map: MicroProfiler becomes stat commands plus Unreal Insights; StreamingEnabled becomes World Partition plus network relevancy.
