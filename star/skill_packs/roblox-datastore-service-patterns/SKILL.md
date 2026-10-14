---
name: roblox-datastore-service-patterns
description: DataStoreService patterns for atomic UpdateAsync writes, budgets, pcall protection and session locks in Roblox.
---
# roblox-datastore-service-patterns
## When to use
Use for Roblox server-owned persistent records, concurrent saves, budgets and preventing stale session writes. These are focused patterns, not a complete player-data system.

## Ten concrete rules
1. Access DataStoreService from a server Script, never a LocalScript. Keep active player state in server memory. [S1]
2. Prefer UpdateAsync when a write depends on old data or multiple servers might write. It uses read and write budgets. [S2]
3. An UpdateAsync transform returns a new value or nil to cancel. It cannot yield and might run again; avoid side effects. [S2]
4. Wrap yielding data-store operations in pcall. Failed responses do not prove writes never committed; use ordered, bounded, idempotent retries. [S3]
5. Check StandardRead and StandardWrite budgets for standard UpdateAsync calls. The enum still lists UpdateAsync, but current server budget documentation uses the StandardRead and StandardWrite types. [S4]
6. Budgets are snapshots, not reservations. Stagger saves and handle throttling; do not issue a request on every change. [S3][S4]
7. For live player profiles, atomically claim a session lock with UpdateAsync, ideally in key metadata, before using the record. [S5]
8. Reject non-owner saves, refresh the lease periodically and release it on PlayerRemoving and BindToClose; recover from crashes. [S5][S6]
9. Preserve other fields, user IDs and metadata when updating data. Reject malformed existing schemas rather than overwriting them. [S2]
10. Serialize writes for each key; record unique IDs for retryable rewards and verify cross-server handoff in a test game. [S3][S5]

## Three correct Luau examples
These independent server Script examples show one operation each, not a complete profile manager.

### Example 1: atomic server-computed award
~~~luau
local store = game:GetService("DataStoreService"):GetDataStore("ExampleCoinsV1")
local function awardServerReward(player)
    local ok, result = pcall(function()
        return store:UpdateAsync("Player_" .. player.UserId, function(old)
            if old ~= nil and typeof(old) ~= "number" then return nil end
            return (old or 0) + 10
        end)
    end)
    if not ok then
        warn("Reward not confirmed")
        return false
    end
    return result ~= nil
end
~~~
Call once per verified server reward. A retryable purchase grant also needs an atomic award-ID ledger. [S2][S3]

### Example 2: budget-aware, monotonic stage save
~~~luau
local service = game:GetService("DataStoreService")
local stages = service:GetDataStore("ExampleStagesV1")
local function saveServerStage(player, stage)
    if typeof(stage) ~= "number" or stage < 0 or stage % 1 ~= 0 then return false end
    if service:GetRequestBudgetForRequestType(Enum.DataStoreRequestType.StandardRead) < 1
        or service:GetRequestBudgetForRequestType(Enum.DataStoreRequestType.StandardWrite) < 1 then
        return false -- Defer; the stage has not been saved.
    end
    local ok, saved = pcall(function()
        return stages:UpdateAsync("Player_" .. player.UserId, function(old)
            if old ~= nil and typeof(old) ~= "number" then return nil end
            return math.max(old or 0, stage)
        end)
    end)
    return ok and saved ~= nil
end
~~~
Stage must come from trusted server progress. Budget may change after this preflight check. [S3][S4]

### Example 3: atomic session-lock claim (acquisition only)
~~~luau
local service = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")
local profiles = service:GetDataStore("ExampleProfilesV1")
local function tryClaim(player)
    local token = HttpService:GenerateGUID(false)
    local now = os.time()
    local ok, value = pcall(function()
        return profiles:UpdateAsync("Player_" .. player.UserId, function(old, keyInfo)
            local meta = if keyInfo then keyInfo:GetMetadata() else nil
            if meta == nil then meta = {} end
            if typeof(meta) ~= "table" then return nil end
            if meta.LockId ~= nil and meta.LockId ~= token then
                if typeof(meta.LeaseUntil) ~= "number" or meta.LeaseUntil > now then
                    return nil
                end
            end
            local nextMeta = table.clone(meta)
            nextMeta.LockId = token
            nextMeta.LeaseUntil = now + 240
            local ids = if keyInfo then keyInfo:GetUserIds() else { player.UserId }
            if old ~= nil and typeof(old) ~= "table" then return nil end
            return old or { Coins = 0 }, ids, nextMeta
        end)
    end)
    return if ok and value ~= nil then token else nil
end
~~~
For production, add serialized loading/saving, owner-checked updates, lease refresh, release at departure/shutdown, expiry policy and schema validation. This example alone is not sufficient. [S5][S6]

## Three common mistakes
1. GetAsync followed by SetAsync to increment a balance races with writes from other servers. [S2]
2. Assuming a budget preflight guarantees a write, or that a pcall failure means nothing was committed. [S3][S4]
3. Holding a lock without refreshing and releasing, or letting a stale server overwrite a newer session. [S5]

## Checklist
- [ ] Access is server-only and data-store calls are protected.
- [ ] UpdateAsync transforms never yield or cause external side effects.
- [ ] Saves handle read/write budgets, bounded retries and idempotency.
- [ ] Lock lifecycle includes claim, refresh, owner check, expiry and release.
- [ ] Cross-server and failure cases are tested before production.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S6]. Names and time thresholds are illustrative, not official defaults.
