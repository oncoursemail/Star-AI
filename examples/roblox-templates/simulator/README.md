# Simulator template

A small, buildable Roblox clicker/simulator example for STAR's source-folder pipeline.
The client sends **action names and optional catalog IDs only**. Every currency delta,
purchase price, threshold, multiplier, and owned pet is resolved by the server.

## Gameplay

- Click **CLICK / EARN**. The server limits requests globally and grants at most one
  currency click every 0.25 seconds (four normal clicks per second).
- Buy upgrades using the server's increasing cost curve. Repeated purchases are
  limited by the wallet and the level cap.
- Unlock Canyon at 200 **run-earned** coins and Orbit at 1000. Zone bonuses apply
  only after the server verifies and accepts the requested zone.
- Buy pets with server-owned coins, then equip one owned pet for a multiplier.
  Pet ownership persists through rebirths.
- Rebirth costs 2500 current coins; it resets the wallet, run earnings, active
  zone, and upgrade level, but increases the persistent rebirth multiplier.
- Coins and rebirths appear in server-written leaderstats.

## Layout

`ReplicatedStorage/Shared/{RateLimiter,CostCurve,MultiplierMath}.luau` are pure,
deterministic math/state modules. Their executable Luau specs live under
`ServerScriptService/Tests/*.spec.luau`. The `SimulatorService` ModuleScript
owns gameplay transitions. `Simulator.server.luau` handles remotes, joins,
leaves, leaderstats and autosaves; the client only renders a basic HUD and
sends action requests.

Flooding 1,000 click requests over one second yields **no more currency** than
four correctly timed clicks. Malformed actions, client-submitted amounts, and
client-submitted prices are never honored. Global request and snapshot
cooldowns also limit the work and responses from remote spam.

## Saving and testing

`ProfileStore` uses `UpdateAsync` for both loads and saves, `pcall`, four
bounded attempts with exponential retry delays, and a server session lease.
If another server has a live lease or loading fails, the player is refused
rather than given a fresh, overwritable wallet. Autosave runs every 60
seconds; PlayerRemoving and BindToClose attempt a final save. An expired
lease can be reclaimed after a crashed server. This is an example, not a
substitute for production economy audits and simulated concurrent-server QA.

Run offline Python structure/build checks (no Roblox credentials required):

```sh
python -m pytest -q tests/test_simulator_template.py
python -m pytest -q
```

To run the **Luau behavioral specs**, use STAR's reviewed Roblox test place
pipeline after configuring your *own private* test experience and granting
the necessary approval. No test place is published by this template:

```sh
python -m star.roblox_pipeline --source examples/roblox-templates/simulator
# Owner-operated private test only, after reviewing the source:
python -m star.roblox_pipeline --source examples/roblox-templates/simulator --publish-and-test
```

Enable Studio API Services when testing DataStore behavior in Studio, and
remember that live DataStore and join/leave tests require an actual private
Roblox session. GitHub Python/React CI alone does **not** execute Luau specs
or establish that DataStore works in a published experience.
