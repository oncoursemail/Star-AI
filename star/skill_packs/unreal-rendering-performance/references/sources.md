# Sources for unreal-rendering-performance

Checked against the official Unreal Engine documentation (labelled 5.8) on 2026-10-13. Epic's documentation is not openly
licensed: the guidance is written in STAR's own words and only links to the pages. Deeper reference: docs/research/engines/unreal.md.

| Claim in the skill | Documentation page |
|---|---|
| stat unit and other stat commands | https://dev.epicgames.com/documentation/en-us/unreal-engine/stat-commands-in-unreal-engine |
| Unreal Insights tracing, memory insights | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-insights-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/memory-insights-in-unreal-engine |
| Profiling workflow and configuration | https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-performance-profiling-and-configuration-in-unreal-engine |
| Significance Manager | https://dev.epicgames.com/documentation/en-us/unreal-engine/significance-manager-in-unreal-engine |
| Nanite supported content | https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine |
| Lumen GI and reflections | https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine |
| Virtual Shadow Maps | https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine |
| MegaLights; Lumen Lite and SSGI deprecation in 5.8; Substrate default in 5.7 | https://dev.epicgames.com/documentation/en-us/unreal-engine/megalights-in-unreal-engine , https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes , https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-7-release-notes |
| PSO precaching | https://dev.epicgames.com/documentation/en-us/unreal-engine/pso-precaching-for-unreal-engine |
| World Partition, One File Per Actor | https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/one-file-per-actor-in-unreal-engine |
| BuildCookRun and packaging | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-automation-tool-overview-for-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine |
| Build configurations | https://dev.epicgames.com/documentation/en-us/unreal-engine/build-configurations-reference-for-unreal-engine |
| Automation tests | https://dev.epicgames.com/documentation/en-us/unreal-engine/automation-test-framework-in-unreal-engine |

API names verified against the official reference on 2026-10-13: stat unit, stat gpu, ProfileGPU, memreport, Unreal Insights trace channels,
UInstancedStaticMeshComponent, UHierarchicalInstancedStaticMeshComponent, USignificanceManager, RunUAT BuildCookRun,
-clientconfig, -serverconfig, Primary Asset Labels.
No compile, profile or packaging run is claimed.
