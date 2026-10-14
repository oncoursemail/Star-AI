---
name: roblox-pathfinding-npc
description: Roblox PathfindingService NPC movement, waypoints, blocked paths, MoveTo and network ownership.
---
# roblox-pathfinding-npc
## When to use
For Roblox NPCs that chase targets or move along navigation routes. Complements `game-npc-quests` (quest/reward logic), `roblox-performance-streaming` (performance) and existing NPC strict-type practice; do not repeat their guidance. OFF unless opted in.

## Ten concrete rules
1. Compute obstacle-aware navigation with server `PathfindingService:CreatePath(agentParameters)`; `Path` is computed, not a list of direct straight-line targets. [S1][S2]
2. Set `AgentRadius`, `AgentHeight`, `AgentCanJump` and optional `Costs` for agent dimensions and navigation preferences. Use actual NPC geometry; these numbers are design settings. [S1][S3]
3. Call yielding `Path:ComputeAsync(start, goal)` inside `pcall`; treat errors and `Path.Status == Enum.PathStatus.NoPath` as non-traversable for now. [S2][S4]
4. Only use ordered `Path:GetWaypoints()` after `Enum.PathStatus.Success`; inspect `PathWaypoint.Position` and `Action`. [S2][S5]
5. For `Enum.PathWaypointAction.Jump`, set `Humanoid.Jump = true`; call `Humanoid:MoveTo(position)`, observing `MoveToFinished(reached)` instead of assuming arrival. [S5][S6]
6. `MoveToFinished` can report failure rather than arrival, and a movement wait must not hang forever. Refresh/replan after failure; this skeleton enforces its **own** 7-second wait bound (not a documented engine guarantee). [S6]
7. Listen to `Path.Blocked(blockedWaypointIndex)`; recompute when the blocked waypoint is **ahead** of the current one. Disconnect listeners when a path is abandoned. [S2][S3]
8. Throttle path recomputation and agent updates: `MIN_RECOMPUTE_INTERVAL` is a local configuration, never an official request allowance. Avoid recalculating on every Heartbeat. [S3]
9. End move and retry loops if the NPC/root/target disappears or `Humanoid.Health <= 0`. Clean up `MoveToFinished` and `Path.Blocked` connections on cancellation. [S6]
10. Evaluate network ownership on server-driven unanchored NPC physics. `BasePart:CanSetNetworkOwnership()` can precede optional `SetNetworkOwner(nil)` to make the server owner; do not assume all parts are eligible or that manual ownership is always best (it can add jitter). [S7][S8]

## Strict Luau skeleton
```luau
--!strict
-- ServerScriptService/Chase.server.luau; Chaser is a rig, Goal a BasePart.
local PathfindingService = game:GetService("PathfindingService")
local npc = workspace:WaitForChild("Chaser") :: Model
local humanoid = npc:WaitForChild("Humanoid") :: Humanoid
local root = npc:WaitForChild("HumanoidRootPart") :: BasePart
local target = workspace:WaitForChild("Goal") :: BasePart
local MIN_RECOMPUTE_INTERVAL = 1.2 -- Design throttle, not an engine rate.
local path = PathfindingService:CreatePath({
    AgentRadius = 2, AgentHeight = 5, AgentCanJump = true,
    Costs = {Water = 10},
})
-- For an eligible unanchored NPC assembly, server ownership can limit exploits.
local canSet = root:CanSetNetworkOwnership()
if canSet then
    pcall(function() root:SetNetworkOwner(nil) end)
end

local function alive(): boolean
    return npc.Parent ~= nil and root.Parent ~= nil and target.Parent ~= nil
        and humanoid.Parent ~= nil and humanoid.Health > 0
end

local function chase()
    while alive() do
        local ok = pcall(function()
            path:ComputeAsync(root.Position, target.Position)
        end)
        if ok and path.Status == Enum.PathStatus.Success then
            local waypoints = path:GetWaypoints()
            local nextWaypoint = 2
            local blocked = false
            local blockedConnection = path.Blocked:Connect(function(blockedWaypointIndex)
                if blockedWaypointIndex >= nextWaypoint then blocked = true end
            end)
            for index = 2, #waypoints do
                if not alive() or blocked then break end
                nextWaypoint = index
                local waypoint = waypoints[index]
                if waypoint.Action == Enum.PathWaypointAction.Jump then
                    humanoid.Jump = true
                end
                local finished, reached = false, false
                local moveConnection = humanoid.MoveToFinished:Connect(function(didReach)
                    finished, reached = true, didReach
                end)
                humanoid:MoveTo(waypoint.Position)
                local deadline = os.clock() + 7 -- Local bound; not engine timeout.
                while not finished and not blocked and alive()
                    and os.clock() < deadline do
                    task.wait(0.1)
                end
                moveConnection:Disconnect()
                if not finished or not reached or blocked then break end
            end
            blockedConnection:Disconnect()
        elseif ok and path.Status == Enum.PathStatus.NoPath then
            -- No route currently; try again after the throttle.
        else
            -- ComputeAsync error or unexpected status: retry later.
        end
        task.wait(MIN_RECOMPUTE_INTERVAL)
    end
end

task.spawn(chase)
```
The sample assumes an unanchored NPC rig with Humanoid, HumanoidRootPart and a server-controlled Goal part. It is a single-target example: multi-target chasing, target retargeting, streaming and dynamic navmesh changes require additional cancellation logic. This is a source-backed illustration, **not** Studio-validated.

## Three common mistakes
1. Calling `Humanoid:MoveTo(target.Position)` repeatedly through walls, ignoring `Path.Status`.
2. Recomputing paths on Heartbeat, or reacting to blocked waypoints already behind the NPC.
3. Waiting on stale `MoveToFinished:Wait()` while the target is destroyed or NPC dies.

## Checklist
- [ ] Set realistic agent radius/height and supported traversal costs.
- [ ] Handle ComputeAsync error, NoPath, empty waypoints and blocked paths.
- [ ] Interpret MoveToFinished(false), cancel or time out stalled movement.
- [ ] Throttle recomputation, disconnect listeners and stop on NPC/target removal.
- [ ] Validate network ownership and multiplayer NPC motion in Studio.

## Sources
See [references/sources.md](references/sources.md) for [S1]–[S8]. API names checked against current Creator Hub references; no Studio execution or held-out gain claimed.
