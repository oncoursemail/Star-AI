# Multiplayer netcode fundamentals

Researched 2026-10-13. Engine-independent. Sources at the end.

## 1. The constraints
- Latency (RTT 20-200 ms, more on mobile), jitter, packet loss and reordering, limited bandwidth, and players who
  control their own client (assume every client is hostile).
- You cannot remove latency, only **hide** it (prediction, interpolation) or **move** who suffers from it (lag
  compensation favours the shooter; rollback re-simulates).
- Pick the model per game: player count, how fast the game is, determinism of the simulation, competitive stakes.

## 2. Authority and topology
| Model | How | Use when | Risks |
|---|---|---|---|
| Server-authoritative client/server | Clients send inputs; server simulates and sends state | Default for competitive and persistent games (shooters, MMOs, Roblox) | Server cost; needs prediction to feel responsive |
| Client-authoritative (owner sends state) | Each client simulates its own avatar and sends results | Co-op, casual, prototypes | Trivial cheating (teleport, speed) unless server validates plausibility |
| Deterministic lockstep | All peers exchange inputs and simulate the same frame; only inputs are sent | RTS with thousands of units (Age of Empires), small bandwidth | Needs bit-exact determinism; game speed = slowest peer; input delay; full-state visibility (map hacks) |
| Rollback (GGPO-style) | Lockstep without waiting: predict remote inputs, simulate, roll back and re-simulate when real inputs arrive | 1v1 / small-player fighting and action games | Determinism; CPU cost of re-simulation; visual corrections |
| Relay / listen server / P2P mesh | Topology choices, orthogonal to authority | Cost and NAT trade-offs | Host advantage, host migration |

Distributed authority (ownership per object, e.g. physics objects owned by the nearest player) is a middle ground used
by some engines; it still needs server validation for anything that matters.

## 3. The core techniques (client/server)

### Tick, snapshots and serialization
- The server simulates at a fixed **tick rate** (20-128 Hz; VALORANT 128 Hz, a 7.8125 ms CPU budget per frame) and
  sends snapshots or state deltas at a send rate.
- Delta-compress against the last acknowledged snapshot; quantize (positions to mm/cm, angles to 16 bits,
  smallest-three quaternions); bit-pack; send unreliable-sequenced for state, reliable for events that must arrive
  (chat, purchases, ability unlocks).

### Client-side prediction
The client applies its own input immediately with the same movement code the server runs, tagging each input with a
**sequence number** and keeping it in a pending buffer.

### Server reconciliation
Each server state says "last input processed = N". The client:
1. sets its predicted state to the server's authoritative state,
2. drops all pending inputs with sequence <= N,
3. re-applies the remaining pending inputs in order.
If the result differs from what was shown, smooth the visual error over a few frames (error offset that decays) rather
than snapping, unless the error is large (teleport).

### Entity interpolation (other players)
Render remote entities **in the past**, interpolating between two received snapshots (buffer of ~2 snapshots +
jitter: at 10 snapshots/s a minimum of 100 ms, practically ~150 ms; at 60 Hz ~35-50 ms). Extrapolation (dead
reckoning) hides gaps but overshoots; cap it. Use a jitter buffer and a smoothly adjusted playback clock.

### Lag compensation (server-side rewind)
For hitscan, the server rewinds other players' hitboxes to where the shooter saw them:
`command time = server time - one-way latency - client interpolation delay`, tests the shot against the historical
hitboxes, then restores. Valve's Source engine keeps ~1 s of history. Consequences: "shot behind cover" for the
victim; cap the rewind window (e.g. 200-250 ms) so high-ping players cannot abuse it. Projectiles: either simulate on
server with spawn-time rewind or use client-predicted projectiles with server verification.

### Peeker's advantage
The moving (peeking) player sees the holder first by roughly RTT + interpolation delay + tick quantization.
Reduce it with high tick rate, low interpolation delay, good network routing (Riot Direct), and server-side buffering
policies; you cannot eliminate it.

### Clock synchronization
Estimate server time with an NTP-like exchange (send local time, server echoes with its time; offset = server time
+ RTT/2 - local time; filter over samples, discard outliers). Clients run their simulation slightly **ahead** of the
server (by RTT/2 + buffer) so inputs arrive in time for the tick they target (Overwatch and many shooters adjust the
client's simulation rate to keep a small input buffer on the server).

## 4. Rollback netcode in detail
- Each frame: gather local input, predict missing remote inputs (repeat the last known input), save state, simulate.
- When a real remote input for frame F arrives and differs from the prediction: load the state saved at F,
  re-simulate F..now with corrected inputs (within one render frame), continue.
- Requirements: deterministic simulation, cheap save/load of the full game state (snapshot arrays; ECS helps),
  rendering and audio/VFX that tolerate corrections (do not spawn one-shot effects twice; key effects by frame and
  entity).
- Add a small **input delay** (1-3 frames) to reduce rollback distance; adapt it to RTT. Detect desyncs with
  per-frame checksums.
- GGPO (Tony Cannon, open source, MIT since 2019) and GGRS (Rust) are reference implementations.

## 5. Interest management and scaling
- Send each client only what is relevant: distance/area of interest (grid cells), visibility (PVS, line of sight:
  also mitigates wallhacks), team/ownership, priority accumulators (more important or closer entities get more of
  the bandwidth budget; starved entities accumulate priority).
- Dormancy: do not replicate unchanged actors; change detection via dirty flags.
- Engines: Unreal Replication Graph and Iris, Unity Netcode for GameObjects / Entities ghost relevancy, Roblox
  StreamingEnabled, Photon Fusion interest keys.
- Sharding / zoning / server meshing for MMO scale; authority handoff at boundaries.

## 6. Security and anti-cheat
- **Never trust the client**: validate every input on the server: type, range, rate, cooldowns, resource ownership,
  physical plausibility (max speed, line of sight, reach distance), and state (alive, has item, in range).
- Make the server the source of truth for economy, inventory, damage, scores, progression and purchases; make
  purchase handling idempotent (receipt ids) so retries never double-grant.
- Rate-limit every remote endpoint per player (token bucket); bound payload sizes and table depths.
- Hide information the client does not need (interest management limits ESP/wallhacks).
- Server-side detection: statistical outliers (accuracy, reaction time, impossible movement), replay review,
  honeypot values.
- Client-side anti-cheat (kernel drivers, integrity checks, obfuscation) raises cost but is always bypassable;
  treat it as a deterrent layered on top of server authority, never a replacement.
- Encrypt and authenticate the transport (DTLS/QUIC or engine equivalent); sign session tokens; never put secrets in
  the client.

## 7. Bandwidth and reliability budget (rules of thumb)
- MTU-safe packets ~1200 bytes; avoid IP fragmentation.
- Use UDP-based transports with your own reliability layer for real-time (or QUIC/WebTransport), TCP/WebSocket only
  where latency spikes from head-of-line blocking are acceptable.
- Measure per-entity and per-message bytes; most savings come from sending less often and less (relevance), not
  from clever compression.

## 8. What STAR should do with a netcode question
1. Identify the genre and pick the authority model from the table; say why.
2. Draw the timeline: client input -> server tick -> snapshot -> client; mark where prediction, interpolation and
   rewind happen.
3. Write the server-side validation first, then the client presentation.
4. Test with simulated latency, jitter and loss (e.g. 150 ms, 20 ms jitter, 2% loss) and two or more clients.

## Sources
- Gabriel Gambetta, Fast-Paced Multiplayer series: Part I https://www.gabrielgambetta.com/client-server-game-architecture.html ; Part II prediction and reconciliation https://www.gabrielgambetta.com/client-side-prediction-server-reconciliation.html ; Part III entity interpolation https://www.gabrielgambetta.com/entity-interpolation.html ; Part IV lag compensation https://www.gabrielgambetta.com/lag-compensation.html
- Valve, "Source Multiplayer Networking": https://developer.valvesoftware.com/wiki/Source_Multiplayer_Networking
- Valve, "Lag Compensation": https://developer.valvesoftware.com/wiki/Lag_Compensation
- Yahn Bernier, "Latency Compensating Methods in Client/Server In-game Protocol Design and Optimization" (2001): https://developer.valvesoftware.com/wiki/Latency_Compensating_Methods_in_Client/Server_In-game_Protocol_Design_and_Optimization
- Glenn Fiedler, Networked Physics series (deterministic lockstep, snapshot interpolation, state synchronization): https://gafferongames.com/categories/networked-physics/ ; "Snapshot Interpolation": https://gafferongames.com/post/snapshot_interpolation/
- Glenn Fiedler, Building a Game Network Protocol series: https://gafferongames.com/categories/building-a-game-network-protocol/
- Timothy Ford, "Overwatch Gameplay Architecture and Netcode" (GDC 2017): https://gdcvault.com/play/1024001/-Overwatch-Gameplay-Architecture-and
- Riot Games tech blog, "VALORANT's 128-Tick Servers": https://technology.riotgames.com/news/valorants-128-tick-servers
- Riot Games tech blog, "Peeking into VALORANT's Netcode": https://technology.riotgames.com/news/peeking-valorants-netcode
- Infil, "Netcode: explaining how fighting games use delay-based and rollback netcode": https://words.infil.net/w02-netcode.html
- GGPO (rollback networking SDK): https://github.com/pond3r/ggpo
- GGRS (Rust rollback): https://github.com/gschup/ggrs
- Mark Terrano and Paul Bettner, "1500 Archers on a 28.8: Network Programming in Age of Empires and Beyond": https://www.gamedeveloper.com/programming/1500-archers-on-a-28-8-network-programming-in-age-of-empires-and-beyond
- Unreal Engine, Networking overview and Replication Graph / Iris: https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine
- Unity Netcode for Entities (prediction, ghost relevancy): https://docs.unity3d.com/Packages/com.unity.netcode@1.3/manual/index.html
- Photon Fusion interest management (secondary engine example): https://doc.photonengine.com/fusion-unreal/v3/manual/replication/interest-management
- Roblox, client-server security model (example of server authority): https://create.roblox.com/docs/scripting/security/security-tactics
