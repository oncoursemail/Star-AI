---
name: roblox-editable-memory-streaming
description: Stay inside the Roblox EditableMesh and EditableImage memory budget and stream big maps safely - fixed-size copies, shared content, TintMask, Persistent and Atomic models, arrival-safe client code.
---
# roblox-editable-memory-streaming
## When to use
Use for Roblox code that creates EditableMesh or EditableImage at runtime, team-tints materials, or runs a large map with StreamingEnabled. From a port project where a second player's avatar failed because the client ran out of editable memory. [F1][F2]

## Ten concrete rules
1. Editable creation draws on a device-dependent memory budget and can return nil; always handle nil and keep the original asset as the fallback. [S1][F1]
2. Copy asset meshes with FixedSize = true; dynamic topology is budgeted at its maximum size. Create copies one at a time. [S1][F1]
3. Share one editable between many instances with Content.fromObject instead of making a copy per instance. [S2][F1]
4. Do not keep two full copies of the same character (first and third person); share a core and add only the extras. Keep finished buffers across death and respawn. [F2][F3]
5. Image memory grows with pixel count; never preallocate pools of large images "just in case" (92 fade copies took about 24 of 80 MiB in one test). [F2][S1]
6. Team colours: use SurfaceAppearance AlphaMode TintMask with Color on one colour map instead of generating an image per team. [S3][F4]
7. Write vertices with EditableMesh batch calls rather than one call per vertex. [S4][F4]
8. Make only small critical models Persistent (scoreboards, flags, objectives); make pickups Atomic; never make a whole map Persistent. [S5][F5]
9. Keep collision loaded where unanchored bodies rest, not only around players; dropped items otherwise fall through the world. [F3]
10. On the client, subscribe to arrival (CollectionService added signal, WaitForChild with a timeout) before scanning what already exists. Workspace streaming properties are set in the Properties panel, not by scripts. [S5][F5]

## Three common mistakes
1. Allocating editable copies for every player view and every effect at join, then finding the second player's avatar missing. [F2]
2. Uploading a flat one-colour texture per team instead of tinting one map. [F4]
3. Indexing workspace.Map.Building.Door on the client while the model has not streamed in yet. [S5]

## Three correct Luau examples
### Example 1: budget-aware fixed-size mesh copy
~~~luau
local AssetService = game:GetService("AssetService")
local function copyMeshFixed(meshPart)
    local ok, editable = pcall(function()
        return AssetService:CreateEditableMeshAsync(meshPart.MeshContent, { FixedSize = true })
    end)
    if not ok or editable == nil then
        warn("Editable budget reached or load failed; keeping the original mesh")
        return nil
    end
    return editable
end
return copyMeshFixed
~~~
Call it serially and only for parts that really need runtime edits. [S1][F1]

### Example 2: one generated image shared by many labels
~~~luau
local AssetService = game:GetService("AssetService")
local function makeSolidImage(size, gray)
    local image = AssetService:CreateEditableImage({ Size = Vector2.new(size, size) })
    if image == nil then
        return nil
    end
    local pixels = buffer.create(size * size * 4)
    for i = 0, size * size - 1 do
        buffer.writeu8(pixels, i * 4, gray)
        buffer.writeu8(pixels, i * 4 + 1, gray)
        buffer.writeu8(pixels, i * 4 + 2, gray)
        buffer.writeu8(pixels, i * 4 + 3, 255)
    end
    image:WritePixelsBuffer(Vector2.zero, image.Size, pixels)
    return Content.fromObject(image)
end
local shared = makeSolidImage(4, 128)
local function apply(label)
    if shared then
        label.ImageContent = shared
    end
end
return apply
~~~
One small image serves every label; nothing is uploaded. [S2][F4]

### Example 3: arrival-safe client binding and Persistent critical models
~~~luau
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
if RunService:IsServer() then
    for _, model in ipairs(CollectionService:GetTagged("CriticalModel")) do
        if model:IsA("Model") then
            model.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
        end
    end
else
    local bound = {}
    local function bindScoreboard(model)
        if bound[model] then
            return
        end
        bound[model] = true
        print("Scoreboard ready:", model:GetFullName())
    end
    CollectionService:GetInstanceAddedSignal("Scoreboard"):Connect(bindScoreboard)
    for _, model in ipairs(CollectionService:GetTagged("Scoreboard")) do
        bindScoreboard(model)
    end
end
~~~
Subscribe first, then scan, so a model that streams in between is still bound once. [S5][F5]

## Checklist
- [ ] Every editable creation handles nil and keeps a fallback
- [ ] Asset mesh copies use FixedSize and are created serially
- [ ] Shared editables used through Content.fromObject
- [ ] No duplicate full character copies; buffers kept across respawn
- [ ] Only small critical models Persistent; pickups Atomic
- [ ] Client code subscribes to arrival before scanning

## Sources
Field evidence and official pages: [references/sources.md](references/sources.md). Labels F1-F5 and S1-S5 refer to it.
