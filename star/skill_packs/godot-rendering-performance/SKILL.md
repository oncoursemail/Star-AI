---
name: godot-rendering-performance
description: Godot 4 renderer choice, lighting and GI, profiling, frame-time fixes, MultiMesh and servers, headless export and GDExtension basics. Use for Godot performance, lag, stutter, rendering setup, export or build questions.
---
# Godot 4 rendering, performance and builds
Measure first: Debugger Profiler (script time), Visual Profiler (CPU and GPU per pass), Monitors (FPS, draw calls, objects, video memory), Network Profiler. Name the measurement you expect to change.
- Renderers: Forward+ for desktop 3D with every feature (SDFGI, VoxelGI, volumetric fog); Mobile for phones and XR; Compatibility (OpenGL, WebGL 2) for web and old hardware. Web exports use Compatibility.
- Global illumination: LightmapGI is baked and cheapest; VoxelGI for small semi-dynamic areas; SDFGI for large real-time worlds on Forward+ only. Limit shadow distance and cascades.
- Script hot paths: cache nodes in @onready, use static types, avoid get_node and string lookups in _process, set_process(false) on idle nodes, pool bullets and enemies (hide and disable instead of free and instantiate).
- Many identical meshes: MultiMeshInstance3D. Tens of thousands of objects: RenderingServer and PhysicsServer3D through RIDs. Use visibility ranges for LOD and OccluderInstance3D for occlusion culling.
- Physics: primitive shapes over ConcavePolygonShape3D, fewer Area3D overlaps, physics interpolation instead of a higher tick rate.
- The scene tree is not thread-safe: use WorkerThreadPool or ResourceLoader.load_threaded_request, then call_deferred to touch nodes.
- Shader stutter: ubershaders (4.4+) and the shader baker at export (4.5+); warm up materials on a loading screen.
- Export: install templates for the exact editor version; godot --headless --path . --export-release "<preset name>" <output path>. The preset name must match export_presets.cfg and the output folder must exist. godot --headless --import for CI asset import. Keep .godot/ out of version control; commit .import and .uid files.
- GDExtension: native C++ through godot-cpp built for the targeted API version; a .gdextension file sets entry_symbol, compatibility_minimum and per-platform libraries. Use it for hot loops or C libraries, not as a first fix.
- Roblox map: MicroProfiler becomes the Debugger profilers; StreamingEnabled has no automatic equivalent, so plan visibility ranges, chunk scenes and background loading yourself.
