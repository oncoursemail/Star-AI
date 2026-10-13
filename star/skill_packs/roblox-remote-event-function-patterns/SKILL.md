---
name: roblox-remote-event-function-patterns
description: Roblox RemoteEvent and RemoteFunction patterns for server-side validation, rate limits and asynchronous replies.
---
# roblox-remote-event-function-patterns
## When to use
Use for concrete Roblox RemoteEvent or RemoteFunction contracts, validating client requests, server rate limits and choosing async messages over synchronous client calls. Complements the general secure-remotes pack.

## Ten concrete rules
1. Treat client arguments as untrusted; check permission, state, type, value, and context on the server before state changes. [S1]
2. OnServerEvent and OnServerInvoke receive the actual sender Player first; never trust a client-supplied identity. [S2][S3]
3. Allowlist actions and bound payloads; never accept an arbitrary instance, script, path, damage or purchase price. [S1]
4. For distance-based actions, verify an existing character and a server-controlled target before measuring range. [S1]
5. Limit calls per player using server-owned timestamps or token buckets; a client-only debounce is bypassable. [S1]
6. Clear per-player cooldown state when the player leaves; design idempotency for actions that may repeat. [S1][S4]
7. Use RemoteEvent:FireServer for one-way actions and FireClient for async server notifications. [S2]
8. Use RemoteFunction:InvokeServer only when a synchronous answer is necessary; OnServerInvoke should return promptly. [S3]
9. Do not make server authority depend on RemoteFunction:InvokeClient: the client can error, disconnect or never reply. [S3]
10. Send a small approved message key for UI feedback instead of arbitrary executable data or server secrets. [S1][S2]

## Three correct Luau examples
Each is an independent server Script. Create the named remote objects in ReplicatedStorage and the anchored part in Workspace.

### Example 1: validated action, cooldown and server range
~~~luau
local Players = game:GetService("Players")
local remote = game:GetService("ReplicatedStorage"):WaitForChild("PressButton")
local button = workspace:WaitForChild("LaunchButton")
local lastUsed = {}

remote.OnServerEvent:Connect(function(player, action)
    if typeof(action) ~= "string" or action ~= "press" then return end
    if not button:IsA("BasePart") or not button.Anchored then return end
    local character = player.Character
    local root = character and character:FindFirstChild("HumanoidRootPart")
    if not root or not root:IsA("BasePart") then return end
    if (root.Position - button.Position).Magnitude > 12 then return end
    local now = os.clock()
    if now - (lastUsed[player] or -math.huge) < 1 then return end
    lastUsed[player] = now
    button.Color = Color3.fromRGB(0, 200, 0)
end)

Players.PlayerRemoving:Connect(function(player)
    lastUsed[player] = nil
end)
~~~
The part must be anchored and authoritative. Check game-specific permissions before any consequential action. [S1][S2][S4]

### Example 2: validated, read-only RemoteFunction
~~~luau
local Players = game:GetService("Players")
local request = game:GetService("ReplicatedStorage"):WaitForChild("RequestStage")
local lastAsked = {}

request.OnServerInvoke = function(player, field)
    if typeof(field) ~= "string" or field ~= "stage" then return nil end
    local now = os.clock()
    if now - (lastAsked[player] or -math.huge) < 0.5 then return nil end
    lastAsked[player] = now
    local value = player:FindFirstChild("Stage")
    if not value or not value:IsA("IntValue") then return 0 end
    return value.Value
end

Players.PlayerRemoving:Connect(function(player)
    lastAsked[player] = nil
end)
~~~
Trusted server code must maintain the Stage IntValue; do not copy unvalidated client progress into it. [S1][S3]

### Example 3: asynchronous server-to-client feedback
~~~luau
local status = game:GetService("ReplicatedStorage"):WaitForChild("StatusToast")
local function sendStatus(player, messageKey)
    if messageKey ~= "checkpoint" and messageKey ~= "victory" then return end
    status:FireClient(player, messageKey)
end
~~~
Call after server verification; a LocalScript maps the key to display text. The server never waits for InvokeClient. [S2][S3]

## Three common mistakes
1. Trusting client prices, cooldowns or target references, or checking only typeof without ownership and range. [S1]
2. Using InvokeClient as a required permission or reward decision, or allowing OnServerInvoke to yield indefinitely. [S3]
3. Rate-limiting only in LocalScripts and leaving client-triggered expensive operations unthrottled on the server. [S1]

## Checklist
- [ ] Caller, payload schema, allowlist and reply type are documented.
- [ ] Server applies permission, context and per-player throttling.
- [ ] Player-keyed state is cleaned on departure.
- [ ] RemoteFunction replies quickly; server authority does not wait on a client.
- [ ] Test malformed input, spam and invalid player states separately.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S4]. Thresholds are illustrative, not guaranteed engine rates.
