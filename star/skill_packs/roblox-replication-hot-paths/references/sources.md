# Sources for roblox-replication-hot-paths

Written 2026-10-13. The field evidence comes from the owner's private Paintball port project (Roblox Studio,
September and October 2026). It was read only and rewritten as general lessons; no game assets or code were copied. The
official pages are from the Roblox Creator Documentation (CC-BY-4.0), found through the STAR Knowledge index. All
numbers are the project's own measurements.

| Label | Evidence |
|---|---|
| F1 | Project NET_BUDGET.md and CODEX_BRIEFING.md: PivotTo on models that contain nested models rewrote every nested pivot even at rest (about 32,000 replicated items/s live); skipping unchanged poses brought this to about 156 items/s; attempted setter calls were counted separately from writes that changed a value |
| F2 | Project OPTIMIZATION_RESEARCH_CLAUDE.md sections 0 and 1.4: 71.5 ms of CPU versus 2.3 ms of GPU per frame; attribute writes on every 30 Hz message; snapshot and command rates; unreliable payload size; server-side tweens |
| F3 | Project PERF_LINT.md rules PL001-PL008 and the ranked findings in PERF_AUDIT_CODEX_20261008.md: GetDescendants calls and LocalTransparencyModifier writes every frame, arrays rebuilt every frame, a destroy method that kept its records |
| S1 | https://create.roblox.com/docs/performance-optimization/improve |
| S2 | https://create.roblox.com/docs/projects/server-authority |
| S3 | https://create.roblox.com/docs/reference/engine/classes/UnreliableRemoteEvent |
| S4 | https://create.roblox.com/docs/reference/engine/classes/RunService |
| S5 | https://create.roblox.com/docs/scripting/events/remote |
| S6 | https://create.roblox.com/docs/reference/engine/classes/PVInstance |

API names verified with the knowledge service /api-lookup on 2026-10-13: Model:PivotTo (PVInstance:PivotTo),
Vector3:FuzzyEq, Instance:SetAttribute, Instance:GetAttribute, UnreliableRemoteEvent.OnClientEvent,
Instance.DescendantAdded, BasePart.LocalTransparencyModifier, RunService.Heartbeat, RunService.PreRender,
RBXScriptConnection:Disconnect, TweenService:Create.
