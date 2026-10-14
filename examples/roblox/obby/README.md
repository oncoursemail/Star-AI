# Example obby — server-owned stages, respawns and one-time finish

This is a **standalone source example**, not activated in STAR or placed in a live Roblox game. Copy the scripts into your own unpublished Studio place to try it.

**Layout:** Put `ObbyServer.server.luau` (Script) and `StageCore.luau` (ModuleScript) in `ServerScriptService`. Under `Workspace`, create a Folder `Checkpoints` containing four anchored, non-overlapping BaseParts named `1`, `2`, `3`, `4` in the intended order; a Folder `KillBricks` containing red hazard parts; and one BasePart named `Finish`.

- Touched runs on the **server**; checkpoint order advances from 0 to 1, 2, 3, 4. Repeated touches and skipped stages are rejected.
- `leaderstats.Stage` is an IntValue showing the current stage. `leaderstats.Wins` increments only the first time a player finishes in that **server session**.
- After death, CharacterAdded moves the new character above the last reached checkpoint. Server kills use a short per-player debounce.
- No persistence is implemented: leave/rejoin resets the stage and wins. Add audited DataStore logic separately before claiming persistent gameplay. Test R6 and R15 respawns in Studio.
- `Tests/StageCore.spec.luau` (12 cases) and `Tests/StageSequence.spec.luau` (7 additional cases) run the **actual pure Luau StageCore** on the pinned native CLI. The added cases check interleaved checkpoint touches, independent players, rejoining/reset, exactly-once awards, monotonic hazard cooldown and a fixed-seed 144-action three-player state-machine trace. The ordered-checkpoint invariant is also run against a deliberately incorrect implementation that allows skipping stage 2; the test verifies it fails.
- Headless cases do not simulate Roblox Touched, replication, real physics, leaderstats or character spawning. The tests include an explicitly corrupted internal stage to distinguish impossible server state from invalid input; they do not claim Studio verification.

## Official Roblox references

- https://create.roblox.com/docs/reference/engine/classes/BasePart#Touched
- https://create.roblox.com/docs/reference/engine/classes/Players#GetPlayerFromCharacter
- https://create.roblox.com/docs/reference/engine/classes/Player#CharacterAdded
- https://create.roblox.com/docs/reference/engine/classes/Model#PivotTo
- https://create.roblox.com/docs/reference/engine/classes/Humanoid#Health
- https://create.roblox.com/docs/tutorials/curriculums/obby/create-checkpoints
