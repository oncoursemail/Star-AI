---
name: fund-game-architecture
description: Engine-independent game architecture and game AI - game loop, fixed timestep, ECS vs components, scene graphs, events, state machines, behavior trees, GOAP, utility AI, pathfinding (A*, navmesh, flow fields) and procedural generation.
---
# Game architecture and game AI (engine-independent)
## Game loop and time
- Fixed timestep with an accumulator: accumulator += min(frameTime, maxFrame); while accumulator >= dt do simulate(dt); accumulator -= dt end; render with alpha = accumulator / dt (interpolate previous and current state).
- Clamp the frame time (or cap steps per frame) to avoid the spiral of death. Variable dt makes physics, jump heights and replays frame-rate dependent.
- Run systems at their own rates: input and camera per frame, gameplay/physics at the fixed tick, AI decisions at 2-10 Hz staggered across agents.
- Determinism: fixed dt, fixed iteration order, simulation-owned seeded RNG, no wall-clock reads inside the simulation.
## Structuring objects
- Prefer composition over deep inheritance.
- ECS = entity ids + plain-data components + systems over queries. Archetype storage iterates fastest but moves entities on add/remove; sparse sets make add/remove cheap. Choose ECS for thousands of similar simulated things or rollback/snapshots; keep components for a few hundred designer-authored objects. Make system order explicit (input, gameplay, physics, animation, render prep).
- Scene graph: world = parent world * local, cached with dirty flags; it is not a spatial index.
- Events/observers decouple, but always disconnect (lifetime tied to the owner), guard re-entrancy and never mutate a listener list while iterating it. Queue events to process them at a known point in the frame.
- Command objects for input, undo, replay and network messages; data-driven tunables with validation.
## Decision-making
- FSM: few clear modes; each state has enter/update/exit; one current-state variable instead of many booleans; queue transitions. Hierarchical FSM for shared transitions; a state stack for "stunned, then resume".
- Behavior tree: Success/Failure/Running. Sequence = AND (resume at the running child), Selector = OR (first child that does not fail), decorators (inverter, cooldown, timeout). Decide reactive vs memory sequences; tell aborted actions to clean up; per-agent blackboard.
- Utility AI: score = product of response curves over normalised inputs; momentum bonus for the current action; debug with score tables.
- GOAP: actions with preconditions, effects and cost; A* over world states to the goal; re-plan when invalidated; cap planner time per frame.
## Pathfinding and movement
- Navmesh is the default representation; grids for tile games; waypoint graphs for sparse levels.
- A*: f = g + h; admissible h (never overestimates) keeps paths optimal: Manhattan for 4-way, octile for 8-way, Euclidean for any-angle. Open set as a binary heap with lazy deletion; closed set; cameFrom for reconstruction; iteration budget, and report "no path" separately from "budget exceeded".
- Many units, one goal: flow field (one Dijkstra/BFS from the goal, each cell stores a direction). Big maps: hierarchical A*. Changing costs: D* Lite. Smooth navmesh corridors with the funnel algorithm.
- Local avoidance: steering (seek, arrive, separation) or RVO/ORCA; time-slice path requests across frames.
## Procedural generation
- Seeded and chunk-local: hash(seed, chunkX, chunkY) gives independent, order-free chunks.
- Noise with octaves (fBm) and domain warping; BSP or cellular automata dungeons; Poisson-disk placement; Wave Function Collapse for adjacency rules.
- Validate output (flood fill for connectivity, difficulty bounds) and keep a fallback.
## Answer checklist
Ask for scale (entity count, players, frame rate, determinism), recommend the simplest structure that meets it, say what would trigger a switch, show the update order and tick rates, and name the debug view to build.
