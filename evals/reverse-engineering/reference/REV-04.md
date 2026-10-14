They make the simulation deterministic, so the same inputs always give the same game, and then they record and replay inputs.

How the lockstep projects do it: OpenTTD and OpenRA advance the game in fixed ticks. Every random number comes from a seeded generator that is part of the game state, the simulation never reads the wall clock, and only player commands (not results) go over the network. Each client computes a checksum of the game state regularly; if two checksums differ, that is a desync, and the logs pin down the first tick where they diverged. A replay is essentially the starting state plus the list of commands with their tick numbers, so a bug report becomes a test that replays the same game.

In Luau:

- Run the wave simulation on the server in a fixed step: accumulate Heartbeat time and advance the simulation in steps of exactly 1/20 s, passing a constant dt, never the frame's delta time or os.clock.
- Give the wave its own `Random.new(seed)` and use only that for spawns, crits and targeting; log the seed. Don't share math.random with other systems.
- Avoid order-dependent iteration: `pairs` over a dictionary has no guaranteed order, so iterate sorted arrays (for example towers sorted by id) when the order affects results.
- Keep physics out of the outcome: move enemies along the path by distance per tick instead of relying on physics.
- Record player actions (place tower, upgrade, sell) with the tick number. A test can then replay the seed and the action log in a test place and compare a hash of the state, for example the sorted list of enemy health values, after every tick or at the end.

When a wave ends differently, you now have the seed and log to replay it, and the hash tells you the first tick that diverged.
