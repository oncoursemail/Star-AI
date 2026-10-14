# Round-based minigame template

A source-only Roblox place template: lobby, server-owned intermission countdown,
`Intermission -> Loading -> Playing -> Ended -> Intermission`, an example arena,
last-player-standing winners, session coins, a read-only HUD, and bounded
per-round connections and map lifetime. No network calls or credentials.

## Run it

Build from the repository root with STAR's script-only place builder:

```sh
python -m star.roblox_pipeline --source examples/roblox-templates/rounds --out rounds.rbxlx
```

The `--out` option writes a place even if a Roblox API key is not configured;
the pipeline may subsequently report that it cannot validate the test experience.
To open the generated place, import the .rbxlx in Roblox Studio. The source paths
map directly to Roblox services; the server script starts automatically.
The example `ArenaFactory` generates a lobby platform and a disposable arena
at runtime, so no preexisting map asset is required.

For **owner-approved** Roblox-server specs, configure a private test experience
as described in `docs/ROBLOX_ACCESS.md`, then explicitly run:

```sh
python -m star.roblox_pipeline --source examples/roblox-templates/rounds --publish-and-test
```

This is **not** a CI test. It needs a real owner's credentials and approval;
do not run it against a public game. `pytest -q` tests the source build
and safety/layout invariants offline; `ServerScriptService/Tests/*.spec.luau`
hold the behavioral tests executed by STAR's approved Luau harness.

## State transition contract

The pure `ReplicatedStorage/Shared/RoundState.luau` function
`next(current, event, playerCount, minimumPlayers)` has no engine dependencies:

| Current state | Event | Condition | Next state |
| --- | --- | --- | --- |
| Intermission | countdown_elapsed | enough players | Loading |
| Intermission | countdown_elapsed | fewer than minimum, including zero | Intermission |
| Loading | map_ready | enough eligible characters | Playing |
| Loading | map_ready | fewer than minimum, including zero | Intermission |
| Loading | load_failed | any count | Intermission |
| Playing | winner | one survivor | Ended |
| Playing | timeout | round time elapsed | Ended |
| Playing | empty | zero survivors / all left | Ended |
| Ended | results_elapsed | any count, including zero | Intermission |

All other transitions return `nil, "illegal_transition"`; invalid states
and invalid counts return `nil, "invalid_input"`. The server decides which
event occurred. Only `ReplicatedStorage`'s `RoundState` attribute replicates
the state machine; `RoundDeadline` is separate read-only UI timing metadata.
Clients never have authority over transitions or coins.

## Players, winners and cleanup

- Countdown starts only with at least two players; dropping below two cancels
  and restarts it. A fixed server-side snapshot of **ready** characters at
  Loading (up to 12) is eligible for the round. Late joins and respawns wait
  in the lobby until the next round. Ineligible loading snapshots cancel cleanly.
- Each active character is teleported to a map spawn. Humanoid death, character
  removal and leaving mark an entrant eliminated. One surviving entrant wins;
  zero means a draw. On timeout, a sole survivor wins, or a unique living
  **positive** score leader wins; ties and all-zero scores draw.
- The demo deliberately has no scoring pickups, so multiple survivors at
  timeout draw. To add scores, update `entry.score` only from independently
  validated server-side game events. Never trust a client-provided score,
  win claim, price or reward amount.
- A winner receives 25 session-only `leaderstats.Coins` once on the server.
  This is not persisted. Add server-validated DataStore saving separately if
  your game needs currency across sessions.
- `RoundResources` closes every round's `Humanoid.Died` and
  `CharacterRemoving` connections and destroys the arena instance. Its
  disposers run once, in reverse order. Player `CharacterAdded` listeners are
  one per connected player and are disconnected on leave. The lobby persists
  for the server lifetime; there are no per-round heartbeat loops or remotes.

Configuration is in `ServerScriptService/RoundConfig.luau` (players, timings,
and reward). Swap `ArenaFactory.createArena()` for a cloned ServerStorage
map returning `(model, spawnParts)`; keep the map owned by the round resource
bag so it is destroyed after the round. This is an instructional template,
not a published Roblox experience or a production anti-cheat.
