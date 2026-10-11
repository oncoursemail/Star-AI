# Sources for roblox-performance-streaming

Official Roblox Creator Documentation (CC-BY-4.0), checked against the STAR Knowledge index (creator-docs af5f853).

| Claim in the skill | Documentation page |
|---|---|
| Improve performance; script computation; MicroProfiler | https://create.roblox.com/docs/performance-optimization/improve |
| Heartbeat handlers: reduce their workload, spread computation across frames | https://create.roblox.com/docs/performance-optimization/microprofiler/tag-table |
| RunService.Heartbeat / RenderStepped | https://create.roblox.com/docs/reference/engine/classes/RunService |
| Instance streaming, model streaming controls | https://create.roblox.com/docs/workspace/streaming |
| Model.ModelStreamingMode (set in Studio or in Scripts, never LocalScripts), Enum.ModelStreamingMode (Atomic, Persistent) | https://create.roblox.com/docs/reference/engine/classes/Model and https://create.roblox.com/docs/reference/engine/enums/ModelStreamingMode |
| Debris:AddItem | https://create.roblox.com/docs/reference/engine/classes/Debris |
| ProximityPrompt, Workspace:GetPartBoundsInRadius, OverlapParams | https://create.roblox.com/docs/reference/engine/classes/ProximityPrompt and https://create.roblox.com/docs/reference/engine/classes/WorldRoot |

API names verified with the knowledge service /api-lookup on 2026-10-10: RunService.Heartbeat, RunService.RenderStepped, Workspace:GetPartBoundsInRadius,
OverlapParams, CollectionService:GetInstanceAddedSignal, Model.ModelStreamingMode, Enum.ModelStreamingMode, Player.ReplicationFocus,
Workspace.StreamingEnabled, Debris:AddItem, ProximityPrompt.Triggered. (Model.PersistentLoaded is not in the index and is not used.)
