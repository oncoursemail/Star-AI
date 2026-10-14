# Roblox player character and respawn lifecycle — candidate lessons

**Status: unreviewed candidate reference, not imported into STAR's active lessons or default skill packs.**

Engine-dependent Luau snippets below are illustrative: they have NOT been run or typechecked inside Roblox Studio. Roblox class members are cited individually; official docs are not evidence of a game playtest. Do not automatically promote these lessons without independent evaluation.

### CL-01: GetPlayers lifecycle correction
**Failure:** PlayerAdded misses already-present players.
**Correction:** Connect PlayerAdded and enumerate existing players; initialization must be idempotent.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Players#GetPlayers
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
Players.PlayerAdded:Connect(onPlayer)
```
**Corrected (Luau):**
```luau
Players.PlayerAdded:Connect(onPlayer)
for _, player in Players:GetPlayers() do onPlayer(player) end
```

### CL-02: CharacterAdded lifecycle correction
**Failure:** CharacterAdded listeners cannot replay a character spawned before subscription.
**Correction:** Connect before reading player.Character and initialize its current value when available.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Player#CharacterAdded
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
player.CharacterAdded:Connect(setupCharacter)
```
**Corrected (Luau):**
```luau
player.CharacterAdded:Connect(setupCharacter)
if player.Character then setupCharacter(player.Character) end
```

### CL-03: WaitForChild lifecycle correction
**Failure:** A Humanoid may not yet be a child when CharacterAdded fires.
**Correction:** Use a bounded WaitForChild and check both existence and class before using properties.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Instance#WaitForChild
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
local humanoid = character.Humanoid
humanoid.WalkSpeed = 16
```
**Corrected (Luau):**
```luau
local humanoid = character:WaitForChild("Humanoid", 5)
if not humanoid or not humanoid:IsA("Humanoid") then return end
humanoid.WalkSpeed = 16
```

### CL-04: Character lifecycle correction
**Failure:** An old character can be replaced during a yielding initialization.
**Correction:** Compare the captured character against player.Character after a bounded wait.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Player#Character
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
local humanoid = character:WaitForChild('Humanoid', 5)
if humanoid then setupHumanoid(humanoid) end
```
**Corrected (Luau):**
```luau
local humanoid = character:WaitForChild('Humanoid', 5)
if player.Character ~= character then return end
if humanoid then setupHumanoid(humanoid) end
```

### CL-05: Died lifecycle correction
**Failure:** A listener on only the first spawn does not handle later Humanoids.
**Correction:** Attach Died on each new character and disconnect the previous listener during removal.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Humanoid#Died
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
local humanoid = player.Character:FindFirstChildOfClass('Humanoid')
humanoid.Died:Connect(onDeath)
```
**Corrected (Luau):**
```luau
local function setup(character)
    local humanoid = character:WaitForChild('Humanoid', 5)
    if humanoid then humanoid.Died:Connect(onDeath) end
end
player.CharacterAdded:Connect(setup)
```

### CL-06: CharacterRemoving lifecycle correction
**Failure:** Dead character event connections can retain obsolete state across respawns.
**Correction:** Use CharacterRemoving to clean per-character connections when the old character leaves.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Player#CharacterRemoving
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
humanoid.Died:Connect(onDeath) -- no cleanup
```
**Corrected (Luau):**
```luau
local diedConnection = humanoid.Died:Connect(onDeath)
player.CharacterRemoving:Connect(function(oldCharacter)
    if oldCharacter == character then diedConnection:Disconnect() end
end)
```

### CL-07: PlayerRemoving lifecycle correction
**Failure:** Player-indexed server state is leaked when a player disconnects.
**Correction:** Disconnect player-owned handlers and clear tables in PlayerRemoving.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Players#PlayerRemoving
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
state[player] = {stage = 1} -- remains after player leaves
```
**Corrected (Luau):**
```luau
Players.PlayerRemoving:Connect(function(leavingPlayer)
    cleanupPlayer(leavingPlayer)
    state[leavingPlayer] = nil
end)
```

### CL-08: TakeDamage lifecycle correction
**Failure:** Locally changing a Humanoid's health is not a server-authoritative damage system.
**Correction:** The server validates the hit and calls TakeDamage; clients only display effects.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Humanoid#TakeDamage
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
-- LocalScript
humanoid.Health -= 10
```
**Corrected (Luau):**
```luau
-- Server Script after validating a hit
if humanoid.Health > 0 then humanoid:TakeDamage(10) end
```

### CL-09: RigType lifecycle correction
**Failure:** R15 RightHand assumptions break R6 characters with Right Arm.
**Correction:** Inspect Humanoid.RigType and select the correct rig part, handling an absent part.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Humanoid#RigType
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
local hand = character.RightHand -- not available on R6
```
**Corrected (Luau):**
```luau
local partName = humanoid.RigType == Enum.HumanoidRigType.R15
    and 'RightHand' or 'Right Arm'
local hand = character:FindFirstChild(partName)
if not hand then return end
```

### CL-10: LoadAnimation lifecycle correction
**Failure:** Humanoid:LoadAnimation hides animator ownership and deprecated API behavior.
**Correction:** Load tracks through a server-created Animator under the Humanoid.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Animator#LoadAnimation
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
local track = humanoid:LoadAnimation(animation)
```
**Corrected (Luau):**
```luau
local animator = humanoid:FindFirstChildOfClass('Animator')
if not animator then return end -- server creates it
local track = animator:LoadAnimation(animation)
track:Play()
```

### CL-11: CharacterAutoLoads lifecycle correction
**Failure:** Disabling automatic character loading without spawning leaves players without characters.
**Correction:** For controlled server respawns, use LoadCharacterAsync on an explicit server lifecycle path.
**Source:** https://create.roblox.com/docs/reference/engine/classes/Players#CharacterAutoLoads
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
Players.CharacterAutoLoads = false -- nobody spawns
```
**Corrected (Luau):**
```luau
Players.CharacterAutoLoads = false
-- Server decides when this player spawns or respawns
player:LoadCharacterAsync()
```

### CL-12: GetMarkerReachedSignal lifecycle correction
**Failure:** Marker callbacks left connected on tool unequip can run repeatedly.
**Correction:** Keep the connection and disconnect it on Unequipped alongside stopping the track.
**Source:** https://create.roblox.com/docs/reference/engine/classes/AnimationTrack#GetMarkerReachedSignal
**Verification:** illustrative-engine-only
**Incorrect (Luau):**
```luau
track:GetMarkerReachedSignal('Hit'):Connect(onHit) -- no disconnect
```
**Corrected (Luau):**
```luau
local markerConnection = track:GetMarkerReachedSignal('Hit'):Connect(onHit)
tool.Unequipped:Connect(function()
    markerConnection:Disconnect()
    track:Stop()
end
```

## Scope

These are local documentation candidates only. No service, model, file, or default skill-pack selection reads them automatically. Server/client examples require a real Roblox Studio playtest, including R6/R15 respawn, network ownership and disconnect behavior. Offline tests validate citations, distinct snippets and candidate status, not engine behavior.
