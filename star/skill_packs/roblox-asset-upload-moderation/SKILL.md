---
name: roblox-asset-upload-moderation
description: Upload Roblox images and audio without moderation trouble - review exact bytes, ban links, barcodes and handles in textures, check every returned asset, stop on the first moderation error.
---
# roblox-asset-upload-moderation
## When to use
Use before uploading or importing Roblox images, decals, textures or audio, especially in batches from an import pipeline. From a port project where two texture atlases were removed for "Directing Users Off-Platform" although neither showed a visible link. [F1][F2]

## Ten concrete rules
1. Look at every actual image before upload, at full size and zoomed, on light and dark backgrounds, rotated, including small and rotated atlas text. [F1][F3]
2. Reject any URL or domain-like text, QR or 2D code, invite link, social or contact handle, or "visit, join, download" text. [F1][S1]
3. Treat barcodes (even decorative ones) and product packaging text as off-platform risks; the removed atlases had barcodes and part numbers. [F1][F2]
4. Record approval against the exact file hash (SHA-256 of the bytes). A changed byte means a new, unreviewed file. A blocked hash overrides any approval. [F1][F3]
5. Check each returned asset on its own; one tool reply can report success while single items failed. [F1][F2]
6. Confirm each new asset is usable: load it back in Studio and compare size, pixels or duration with the source. A decal that loads does not prove its image loads. [F2][S2]
7. Stop the whole batch on the first moderation or account error (for example HTTP 403 "User is moderated"); keep the results already obtained and tell the owner. [F1][F2]
8. Never rename, re-encode, crop or re-upload removed content to get past moderation; identical bytes come back as the same blocked asset. [F2]
9. Build flat or constant maps (one colour, constant roughness) at runtime with EditableImage instead of uploading them; even a one-pixel map was blocked once. [F2][S3]
10. For audio, check spoken content for off-platform instructions; the owner, not the agent, confirms import rights. [F1]

## Three common mistakes
1. Approving by file name or by "the API said success" instead of by looking at the pixels and hash. [F1]
2. Retrying a blocked image under a new name, which looks like moderation evasion. [F2]
3. Continuing a batch after a moderation error, risking further account restrictions. [F1]

## Three correct Luau examples
These run in Studio after an upload to verify, not to upload.

### Example 1: load an uploaded image back and check its size
~~~luau
local AssetService = game:GetService("AssetService")
local function verifyImage(assetId, expectedSize)
    local ok, image = pcall(function()
        return AssetService:CreateEditableImageAsync(Content.fromUri("rbxassetid://" .. assetId))
    end)
    if not ok or image == nil then
        return false, "not loadable (blocked, pending or wrong id)"
    end
    local size = image.Size
    image:Destroy()
    if size ~= expectedSize then
        return false, "size " .. tostring(size)
    end
    return true, "loaded"
end
print(verifyImage(0, Vector2.new(512, 512)))
~~~
Replace 0 with each returned id; any false stops the batch for review. [F2][S2]

### Example 2: preload uploaded audio and check its length
~~~luau
local ContentProvider = game:GetService("ContentProvider")
local function verifySound(sound, expectedSeconds)
    local status = nil
    local ok = pcall(function()
        ContentProvider:PreloadAsync({ sound }, function(_, fetchStatus)
            status = fetchStatus
        end)
    end)
    if not ok or status ~= Enum.AssetFetchStatus.Success then
        return false, "fetch " .. tostring(status)
    end
    return math.abs(sound.TimeLength - expectedSeconds) < 0.05, sound.TimeLength
end
return verifySound
~~~
Compare against the source file's duration. [F2][S4]

### Example 3: constant roughness map built at runtime
~~~luau
local AssetService = game:GetService("AssetService")
local function constantMap(value)
    local image = AssetService:CreateEditableImage({ Size = Vector2.new(2, 2) })
    if image == nil then
        return nil
    end
    local pixels = buffer.create(2 * 2 * 4)
    for i = 0, 3 do
        buffer.writeu8(pixels, i * 4, value)
        buffer.writeu8(pixels, i * 4 + 1, value)
        buffer.writeu8(pixels, i * 4 + 2, value)
        buffer.writeu8(pixels, i * 4 + 3, 255)
    end
    image:WritePixelsBuffer(Vector2.zero, image.Size, pixels)
    return Content.fromObject(image)
end
return constantMap
~~~
A value of 128 stands for a roughness of about 0.5; nothing is uploaded. [F2][S3]

## Checklist
- [ ] Every image viewed in full, zoomed, rotated, on light and dark
- [ ] No links, codes, barcodes, handles or off-platform text
- [ ] Approval stored against the exact SHA-256; blocked list checked
- [ ] Each returned asset loaded back and compared with the source
- [ ] Batch stops on the first moderation or account error
- [ ] Constant maps generated at runtime, not uploaded

## Sources
Field evidence and official pages: [references/sources.md](references/sources.md). Labels F1-F3 and S1-S4 refer to it.
