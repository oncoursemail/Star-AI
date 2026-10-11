# STAR obstacle course (Rojo)

A compact playable, four-checkpoint Roblox obstacle course for STAR or a developer to copy. It mirrors the
`examples/roblox-test-place/` split between shared Luau, server logic and small named specs, and adds a Rojo
project plus a client-only stage display. Running the server script generates the platforms, gaps, kill strips,
checkpoints, lava floor and finish gate in `Workspace/STARObbyCourse`.

## Open and play

1. Install [Rojo](https://rojo.space/docs/) and its Roblox Studio plugin. From this folder run
   `rojo serve default.project.json` and connect Studio, or `rojo build default.project.json -o Obby.rbxlx`
   to build a place file.
2. Publish a **separate testing experience**. For persisted saves in Studio, enable Studio API access
   only for that test experience (not an existing live game), then use **Test > Start** with one or two players.
   Without DataStore access the server refuses to load progress rather than risk replacing it.
3. Jump between four platform sections; touch each blue checkpoint in order, avoid red kill parts, and
   touch the gold finish gate. The `Finishes` leaderboard and top-center `Stage x/4` label update.

## Source map

- `default.project.json`: Rojo maps shared modules into ReplicatedStorage, server modules/scripts into
  ServerScriptService and the HUD LocalScript into StarterPlayerScripts.
- `ServerScriptService/CourseBuilder.luau`: produces the small authored-in-code obstacle layout, spawn,
  checkpoints, hazards and finish. Edit its dimensions/positions to change the course.
- `ServerScriptService/ObbyServer.server.luau`: boots services, connects player respawns and closes
  sessions. `CheckpointService`, `KillService`, `FinishService` and `TouchValidation` each handle one
  server-controlled responsibility.
- `ServerScriptService/PlayerData.luau`: holds player progression only on the server; loads, refreshes,
  saves and releases a DataStore session lock.
- `ReplicatedStorage/Shared/StageProgression.luau` and `SaveData.luau`: pure logic (no `game`,
  `script`, `Instance`, or other Roblox API). `tests/*.spec.luau` exercise these in a standalone Luau VM;
  run `luau tests/run.luau` with a Luau CLI that supports relative `require` paths.

## Server/client trust boundary

The client **reads** only the replicated `Stage` player attribute for the HUD. It never chooses checkpoints,
awards finishes, sends progression remotes or writes a DataStore. Server `Touched` handlers check a live
character belonging to a real player, its root part's proximity, strict checkpoint order, and an active
loaded session. The finish gate requires the last stage and grants at most one finish per server session;
the kill service debounces by Humanoid. Physics contacts/proximity alone are **not** a tamper-proof anti-cheat
system against a malicious client controlling its own character; production competitive rewards need
additional movement validation.

Saves use `UpdateAsync` inside `pcall`, bounded exponential retry/backoff, per-player write serialization,
and a unique session token stored with a 120-second expiring lock. Active sessions refresh every 30 seconds
and on stage/finish changes; quitting or server shutdown attempts a final merge-and-unlock. A live foreign
lock cancels the transform (returning `nil`) and the player cannot load. Expired locks can be reclaimed after
server crashes. Migrations accept old numeric stages or `{ stage, wins }` records and normalize a v2
`{ version, furthestStage, finishes, lock }` record. Saved stage/finishes never decrease. Shutdown and
backend failures can still lose the last unsaved touch; never treat DataStore writes as guaranteed. A lost
lock causes a safe disconnect rather than overwriting another server's data. Keep the DataStore name
`STAR_ObbyProgress_v2` stable across published updates.

Roblox API references: [Data stores](https://create.roblox.com/docs/cloud-services/data-stores),
[session locking and retries](https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing),
[Player](https://create.roblox.com/docs/reference/engine/classes/Player),
[PVInstance:PivotTo](https://create.roblox.com/docs/reference/engine/classes/PVInstance),
[BasePart](https://create.roblox.com/docs/reference/engine/classes/BasePart),
[DataModel:BindToClose](https://create.roblox.com/docs/reference/engine/classes/DataModel).

## Playtest checklist

- [ ] Rojo connects and the server builds five platforms, four ordered stages, hazards and a finish gate.
- [ ] Fresh player sees Stage 1; blue checkpoints require stages 2, 3, 4 in that order.
- [ ] Red kill strips/lava kill once per touch burst; death respawns at the latest checkpoint.
- [ ] Touching finish early awards nothing; touching it after Stage 4 awards one `Finishes` point,
      without duplicate awards from other character parts.
- [ ] Rejoining restores furthest stage and saved finishes. Concurrent second-server join while locked
      refuses to load; after a clean leave or an expired crash lock, joining works again.
- [ ] Shut down during or after a checkpoint and verify last **confirmed** saved stage is never decreased.
- [ ] Set DataStore requests to fail in a private test: bounded retries occur; no default progress
      overwrites saved data; release failure is handled via lock expiry.
- [ ] Run `luau tests/run.luau` with a compatible standalone VM and repository `pytest -q`.
