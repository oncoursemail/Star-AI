---
name: fund-netcode
description: Engine-independent multiplayer netcode - authority models, client-side prediction, server reconciliation, entity interpolation, lag compensation, rollback, interest management, bandwidth and server-side anti-cheat validation.
---
# Multiplayer netcode (engine-independent)
## Pick the model
- Server-authoritative client/server (clients send inputs, the server simulates and sends state): default for competitive, persistent and economy games.
- Client-authoritative owner simulation: co-op and prototypes only, and the server must still check plausibility.
- Deterministic lockstep: send only inputs; RTS with many units; needs bit-exact determinism; input delay; game speed = slowest peer.
- Rollback: lockstep that does not wait: predict remote inputs, roll back and re-simulate on correction; fighting and small action games; needs determinism and cheap save/load of the whole state.
## Client/server techniques
- Fixed server tick (20-128 Hz). State snapshots unreliable-sequenced, delta-compressed against the last acknowledged snapshot and quantised; must-arrive events reliable.
- Client prediction: apply local input at once with the same movement code the server runs; tag each input with a sequence number; keep it in a pending list.
- Reconciliation: when the server state says "last processed input = N", set the authoritative state, drop pending inputs <= N, re-apply the rest in order; hide small errors by decaying a visual offset, snap large ones.
- Entity interpolation: render remote entities in the past between two snapshots (about 2 snapshot intervals plus jitter, e.g. 100-150 ms at 10 Hz); cap extrapolation.
- Lag compensation: the server rewinds other players' hitboxes to command time = server time - one-way latency - client interpolation delay, tests the shot, restores. Cap the rewind window (about 200-250 ms). Victims may be hit behind cover: that is the trade.
- Peeker's advantage comes from RTT + interpolation delay + tick quantisation; reduce with tick rate and low buffers; it cannot be removed.
- Clock sync: NTP-style samples, offset = server time + RTT/2 - local time, filtered. Clients run slightly ahead so inputs reach the server before their tick.
## Rollback details
Save state every frame; predict missing remote input as the last known input; on a mismatch load the saved frame and re-simulate to now within one render frame; 1-3 frames of input delay shrink rollbacks; key one-shot effects by frame and entity so re-simulation does not duplicate them; per-frame checksums catch desyncs.
## Scaling and bandwidth
- Interest management: send only relevant entities (distance grid, visibility, team), with priority accumulators sharing the bandwidth budget; skip unchanged entities; this also limits wallhack information.
- Packets under about 1200 bytes; UDP-style transports with your own reliability for real-time; measure bytes per entity and message. Sending less often and less data beats clever compression.
## Security (never trust the client)
- Validate every client message on the server: type, range, size, rate (token bucket per player), cooldown, ownership, alive state, distance/line of sight, and physical plausibility (max speed, reach).
- The server owns economy, inventory, damage, scores, progression and purchases; purchase handling is idempotent (receipt ids) so retries never double-grant.
- Client anti-cheat is a deterrent on top of server authority, never a replacement; never ship secrets in the client.
## Answer checklist
Name the genre and chosen model and why; draw the timeline (input -> server tick -> snapshot -> client) marking prediction, interpolation and rewind; write the server validation before the client presentation; test with simulated 150 ms latency, jitter and 2% loss on two or more clients.
