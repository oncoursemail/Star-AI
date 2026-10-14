# Sources for roblox-pathfinding-npc

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Pathfinding guide: agent parameters, computing, waypoints, blocked paths, costs, modifiers, 3,000-stud and node limits | https://create.roblox.com/docs/characters/pathfinding |
| S2 | PathfindingService CreatePath | https://create.roblox.com/docs/reference/engine/classes/PathfindingService |
| S3 | Path ComputeAsync, Status, GetWaypoints and Blocked | https://create.roblox.com/docs/reference/engine/classes/Path |
| S3 | PathStatus values | https://create.roblox.com/docs/reference/engine/enums/PathStatus |
| S4 | PathWaypoint Position, Action and Label | https://create.roblox.com/docs/reference/engine/datatypes/PathWaypoint |
| S5 | PathWaypointAction Walk, Jump and Custom | https://create.roblox.com/docs/reference/engine/enums/PathWaypointAction |
| S6 | Humanoid MoveTo, its 8-second timeout, MoveToFinished and Jump | https://create.roblox.com/docs/reference/engine/classes/Humanoid |
| S7 | PathfindingModifier Label and PassThrough | https://create.roblox.com/docs/reference/engine/classes/PathfindingModifier |
| S8 | Network ownership: server always owns anchored parts; SetNetworkOwner(nil) | https://create.roblox.com/docs/physics/network-ownership |
| S9 | BasePart SetNetworkOwner | https://create.roblox.com/docs/reference/engine/classes/BasePart |
| S10 | Raycasting and RaycastParams exclusion for line of sight | https://create.roblox.com/docs/workspace/raycasting |
| S10 | RaycastParams | https://create.roblox.com/docs/reference/engine/datatypes/RaycastParams |
| S11 | Part used as an invisible modifier region | https://create.roblox.com/docs/reference/engine/classes/Part |
| S12 | Players GetPlayers | https://create.roblox.com/docs/reference/engine/classes/Players |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
