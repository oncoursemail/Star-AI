# Sources for godot-rendering-performance

Checked against the official Godot documentation (stable = Godot 4.7) on 2026-10-13. The Godot documentation is CC BY 3.0
(class reference MIT); the guidance is written in STAR's own words. Deeper reference: docs/research/engines/godot.md.

| Claim in the skill | Documentation page |
|---|---|
| Forward+, Mobile and Compatibility renderers and their use | https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html |
| LightmapGI, VoxelGI, SDFGI trade-offs | https://docs.godotengine.org/en/stable/tutorials/3d/global_illumination/index.html |
| Profiler, Visual Profiler, Monitors, Network Profiler | https://docs.godotengine.org/en/stable/tutorials/scripting/debug/the_profiler.html and https://docs.godotengine.org/en/stable/tutorials/scripting/debug/debugger_panel.html |
| General CPU/GPU optimisation guidance | https://docs.godotengine.org/en/stable/tutorials/performance/index.html |
| MultiMeshInstance3D for many instances | https://docs.godotengine.org/en/stable/tutorials/performance/using_multimesh.html |
| RenderingServer / PhysicsServer3D via RIDs | https://docs.godotengine.org/en/stable/tutorials/performance/using_servers.html |
| Scene tree is not thread-safe | https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html |
| Occlusion culling | https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html |
| Headless export and import from the command line | https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html and https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html |
| GDExtension and the .gdextension file | https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/what_is_gdextension.html and https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/gdextension_file.html |
| Ubershaders (4.4) and shader baker (4.5) | https://godotengine.org/releases/4.4/ and https://godotengine.org/releases/4.5/ |

API names verified against the official reference on 2026-10-13: MultiMeshInstance3D, RenderingServer, PhysicsServer3D,
WorkerThreadPool, ResourceLoader.load_threaded_request, OccluderInstance3D, LightmapGI, VoxelGI, Environment.sdfgi_enabled,
command-line options --headless, --path, --import, --export-release.
No live Godot editor run is claimed.
