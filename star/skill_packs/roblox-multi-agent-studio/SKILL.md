---
name: roblox-multi-agent-studio
description: Run several AI agents on one Roblox Studio place - file claims, a single integrator, a short Studio lock, honest playtest verdicts and two-client acceptance that counts only real player input.
---
# roblox-multi-agent-studio
## When to use
Use when two or more agents (for example Claude and Codex) share one Roblox project and Studio place, or when planning playtest acceptance for such a team. From a port project run by many parallel agents for weeks. [F1][F2]

## Ten concrete rules
1. Claim files before editing and never edit another agent's claimed files; stale claims are reported, never released automatically. [F1]
2. Exactly one integrator installs into the place and saves it; everyone else hands over a ready list of modules. Hand the role over in writing. [F2]
3. Hold a Studio lock for at most ten minutes per session; Studio and other apps share keyboard focus, so input needs the lock, and only when the user is idle. [F1][F3]
4. Commit only your own listed paths; a plain commit after staging can carry files another agent staged in the shared index. [F4]
5. Keep one handoff file where the newest active block wins, with the exact next action and evidence paths. [F1]
6. Verify files before trusting old notes; "ready to install" sometimes meant the module was never finished. [F1]
7. When a usage limit stops agents, their edits stay on disk uncommitted and claims stay held; restart from the brief and review before installing. [F3]
8. Report PASS, FAIL, INCOMPLETE or PENDING per check; INCOMPLETE is never a pass, and many passing checks do not make a feature complete. [F5]
9. Normal-play acceptance needs real player input in Server and Clients mode; scripted teleports, forced scores and direct start calls are setup, not acceptance. [F5][S1]
10. A reviewer agent reads each diff, runs lint and affected tests and spot-checks evidence, but never installs or saves. [F4]

## Three common mistakes
1. Two agents installing into the same place in parallel, each overwriting the other's modules. [F2]
2. Starting a match from an extra test client, which froze that client; use a Studio-only server hook instead. [F3]
3. Calling a feature done because fixtures passed while nobody played it with two real clients. [F5]

## Three correct Luau examples
### Example 1: Studio-only server QA hook
~~~luau
local RunService = game:GetService("RunService")
local ServerStorage = game:GetService("ServerStorage")
if RunService:IsStudio() then
    local hook = Instance.new("BindableFunction")
    hook.Name = "QAMatchCommand"
    hook.Archivable = false
    hook.OnInvoke = function(command)
        if command == "Start" then
            return "started"
        end
        return "unknown command"
    end
    hook.Parent = ServerStorage
end
~~~
Wire "Start" to your round module; Archivable = false keeps the hook out of saves, and it never exists in live servers. [F3][S2]

### Example 2: time-boxed QA step with an honest verdict
~~~luau
local HttpService = game:GetService("HttpService")
local function runStep(deadlineSeconds, check)
    local started = os.clock()
    local done, passed, detail = false, false, nil
    task.spawn(function()
        local ok, result = pcall(check)
        done, passed, detail = true, ok and result == true, if ok then nil else tostring(result)
    end)
    while not done and os.clock() - started < deadlineSeconds do
        task.wait(0.1)
    end
    local verdict = if not done then "INCOMPLETE" elseif passed then "PASS" else "FAIL"
    return HttpService:JSONEncode({ verdict = verdict, error = detail, normalPlayAccepted = false })
end
print(runStep(50, function()
    return workspace:FindFirstChild("Map") ~= nil
end))
~~~
Keep each step under the tool timeout; a timeout is INCOMPLETE, not PASS. [F5]

### Example 3: observer that disconnects itself
~~~luau
local Players = game:GetService("Players")
local function observeJoins(seconds)
    local joined = {}
    local connection
    connection = Players.PlayerAdded:Connect(function(player)
        table.insert(joined, player.UserId)
    end)
    task.delay(seconds, function()
        connection:Disconnect()
    end)
    return joined
end
return observeJoins
~~~
QA observers read state only and clean up after themselves, so they cannot leak into the next session. [F5]

## Checklist
- [ ] Files claimed before editing; no edits to others' claims
- [ ] One named integrator installs and saves
- [ ] Studio lock held for ten minutes or less, released after
- [ ] Commits contain only your own listed paths
- [ ] Every QA check has PASS, FAIL, INCOMPLETE or PENDING
- [ ] Acceptance uses real input with two clients, not scripted shortcuts

## Sources
Field evidence and official pages: [references/sources.md](references/sources.md). Labels F1-F5 and S1-S2 refer to it.
