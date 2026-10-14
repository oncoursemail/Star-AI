# Sources for roblox-pathfinding-npc

Reviewed against Roblox Creator Hub on 2026-10-13. Original, illustrative server-side code; not executed in Roblox Studio. No knowledge-service /api-lookup is claimed.

| ID | Rule and verified API claim | Official source |
|---|---|---|
| S1 | 1, 2: PathfindingService:CreatePath and agent parameters | https://create.roblox.com/docs/reference/engine/classes/PathfindingService |
| S2 | 1, 3, 4, 7: Path.ComputeAsync, Status, GetWaypoints and Blocked | https://create.roblox.com/docs/reference/engine/classes/Path |
| S3 | 2, 7, 8: agent sizes, Costs, Blocked index and navigation | https://create.roblox.com/docs/characters/pathfinding |
| S4 | 3: PathStatus.Success and PathStatus.NoPath | https://create.roblox.com/docs/reference/engine/enums/PathStatus |
| S5 | 4, 5: PathWaypoint.Position and PathWaypoint.Action | https://create.roblox.com/docs/reference/engine/datatypes/PathWaypoint |
| S6 | 5, 6, 9: Humanoid.MoveTo and MoveToFinished(reached) | https://create.roblox.com/docs/reference/engine/classes/Humanoid |
| S7 | 10: BasePart.CanSetNetworkOwnership and SetNetworkOwner | https://create.roblox.com/docs/reference/engine/classes/BasePart |
| S8 | 10: optional server network owner, anchored constraints and jitter tradeoff | https://create.roblox.com/docs/physics/network-ownership |
