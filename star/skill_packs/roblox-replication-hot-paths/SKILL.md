---
name: roblox-replication-hot-paths
description: Keep Roblox replication and per-frame Luau cheap - skip unchanged PivotTo and attribute writes, sequence unreliable remotes, avoid allocation and hierarchy queries on frame paths.
---
# roblox-replication-hot-paths
## When to use
Use when a Roblox game sends too much network traffic, lags as players join, or runs heavy work every frame. Lessons measured in a large Studio port project where one change cut replication from about 32,000 to about 156 items per second. [F1][F2]

## Ten concrete rules
1. Never PivotTo or move a model that has not moved. On models with nested models, each call rewrote every nested pivot even at rest. [F1]
2. Guard every repeated property or attribute write with an equality check; an unchanged write still costs work. Count attempts, not just changes. [F1][F3]
3. Attributes replicate to every client. Do not write many attributes per movement update; under the server authority model only a limited number (64) per instance replicate. [F2][S2]
4. UnreliableRemoteEvent drops large payloads (about 900 bytes and up) and may reorder; keep messages small and add a sequence number. [F2][S3]
5. Server-authoritative state: send snapshots at a fixed rate (for example 10 Hz) and rate-limit client commands with a token bucket. [F2]
6. On frame paths (Heartbeat, PreRender, render steps) create no tables, closures or strings; reuse buffers. [F3][S4]
7. Never call GetDescendants, GetChildren or FindFirstChild inside per-frame loops; cache the list and maintain it with DescendantAdded. [F3]
8. Run tweens on the client; a server tween replicates every frame. [F2][S1]
9. Measure before optimising: in the project the CPU frame was 71 ms of Luau against about 2 ms of GPU, so rendering tweaks could not help. [F2]
10. A destroy method must clear its records, not only disconnect; a closure that keeps a destroyed object keeps everything it indexed. Bound every cache. [F3]

## Three common mistakes
1. Writing LocalTransparencyModifier on every part of a held model every frame, even while nothing changes. [F3]
2. Setting ten attributes on each character root for every 30 Hz input message. [F2]
3. Rebuilding active and expired arrays in each audio or effect owner every frame. [F3]

## Three correct Luau examples
### Example 1: resting skip for PivotTo
~~~luau
local lastPivot = setmetatable({}, { __mode = "k" })
local EPSILON = 1e-4
local function placeModel(model, target)
    local previous = lastPivot[model]
    if previous ~= nil
        and previous.Position:FuzzyEq(target.Position, EPSILON)
        and previous.LookVector:FuzzyEq(target.LookVector, EPSILON)
        and previous.UpVector:FuzzyEq(target.UpVector, EPSILON) then
        return false
    end
    model:PivotTo(target)
    lastPivot[model] = target
    return true
end
local function setIfChanged(instance, name, value)
    if instance:GetAttribute(name) == value then
        return false
    end
    instance:SetAttribute(name, value)
    return true
end
return { placeModel = placeModel, setIfChanged = setIfChanged }
~~~
Weak keys let destroyed models drop out of the cache; both helpers skip unchanged writes. [F1][F3]

### Example 2: sequenced unreliable remote on the client
~~~luau
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local poseEvent = ReplicatedStorage:WaitForChild("PoseUpdate", 10)
local lastSequence = {}
local latestSpeed = {}
if poseEvent then
    poseEvent.OnClientEvent:Connect(function(userId, sequence, speed)
        if typeof(userId) ~= "number" or typeof(sequence) ~= "number" or typeof(speed) ~= "number" then
            return
        end
        if sequence <= (lastSequence[userId] or -1) then
            return -- stale or duplicate packet
        end
        lastSequence[userId] = sequence
        latestSpeed[userId] = speed
    end)
end
return latestSpeed
~~~
The server sends a small typed message with a rising sequence number; the client keeps only the newest per sender. [F2][S3]

### Example 3: cached part list on a frame path
~~~luau
local function makeHider(model)
    local parts = {}
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("BasePart") then
            table.insert(parts, item)
        end
    end
    local added = model.DescendantAdded:Connect(function(item)
        if item:IsA("BasePart") then
            table.insert(parts, item)
        end
    end)
    local hidden = nil
    local function setHidden(shouldHide)
        if shouldHide == hidden then
            return
        end
        hidden = shouldHide
        local value = if shouldHide then 1 else 0
        for _, part in ipairs(parts) do
            part.LocalTransparencyModifier = value
        end
    end
    local function destroy()
        added:Disconnect()
        table.clear(parts)
    end
    return setHidden, destroy
end
return makeHider
~~~
Call setHidden from the render step; it writes only when the state flips. [F3]

## Checklist
- [ ] Moves and pivots skipped when the pose is unchanged
- [ ] Attribute and property writes guarded by equality checks
- [ ] Unreliable messages small, typed and sequence-filtered
- [ ] No allocation or hierarchy query inside frame callbacks
- [ ] CPU versus GPU measured before any optimisation
- [ ] Caches bounded and cleared on destroy

## Sources
Field evidence and official pages: [references/sources.md](references/sources.md). Labels F1-F3 and S1-S4 refer to it.
