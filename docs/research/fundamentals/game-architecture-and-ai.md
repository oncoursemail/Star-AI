# Game architecture and game AI

Researched 2026-10-13. Engine- and language-independent; engine names appear only as examples. Sources at the end.

## 1. The game loop

Every game is a loop: **process input -> update simulation -> render**, repeated. The design questions are how time
advances and what runs at which rate.

- **Variable timestep** (`update(dt_frame)`): simple, but the simulation depends on frame rate: physics explodes on
  spikes, jump heights differ between 30 and 144 fps, replays and netcode cannot reproduce results.
- **Fixed timestep with accumulator** (Fiedler, "Fix Your Timestep!"):
  ```
  accumulator += min(frameTime, maxFrameTime)   -- clamp avoids the "spiral of death"
  while accumulator >= dt do
      previous = current
      simulate(current, dt)
      accumulator -= dt
  end
  alpha = accumulator / dt
  render(lerp(previous, current, alpha))         -- interpolation removes stutter
  ```
  The simulation always advances by exactly `dt`; rendering interpolates between the last two states (one step of
  latency) or extrapolates (no latency, can overshoot). This is what Unity's `FixedUpdate`, Unreal's sub-stepping
  and Godot's `_physics_process` approximate.
- **Spiral of death**: if one simulation step costs more than `dt`, the accumulator grows forever. Clamp the frame time
  and/or cap steps per frame, and accept slow motion under load.
- **Separate rates**: input sampling and camera at render rate; physics/gameplay at fixed rate (30-120 Hz);
  AI decision-making at lower rates (2-10 Hz, staggered across agents); network send at tick rate.
- **Frame budget**: 16.6 ms at 60 fps, 8.3 ms at 120 fps, 11.1 ms at 90 fps (VR). Budget per system and measure.
- **Determinism checklist**: fixed dt, fixed iteration order (no iteration over hash maps with random order),
  seeded RNG owned by the simulation, no wall-clock reads inside the simulation, consistent floating point.

## 2. Structuring game objects

### Inheritance (classic OOP)
Deep hierarchies (`Entity -> Actor -> Pawn -> Character -> Enemy -> FlyingEnemy`) break down when a feature cuts
across branches ("a flying, swimming, pickup-able enemy"): the diamond / "blob class" problem. Prefer composition.

### Component composition (Unity GameObject/MonoBehaviour, Unreal ActorComponent, Godot nodes, Roblox Instances)
Objects own components that hold both data and behaviour. Flexible, easy to author in editors. Costs: per-object
virtual update calls, scattered memory, hidden inter-component dependencies.

### Entity Component System (ECS)
- **Entity**: an id. **Component**: plain data. **System**: a function that runs over all entities matching a query.
- Storage strategies:
  - **Archetype / table** (Unity DOTS Entities, Flecs, Bevy tables): entities with the same component set are stored
    together in SoA chunks. Very fast iteration; adding/removing a component moves the entity (structural change cost).
  - **Sparse set** (EnTT, Bevy sparse-set storage): one packed array per component plus an index. O(1) add/remove,
    iteration of multi-component queries is slower. 2025 Eurographics CGVC comparison (Cox et al.) confirms: sparse
    sets win on churn, archetypes on large iteration.
- Benefits: cache-friendly iteration, trivially parallel systems with declared read/write sets, easy serialization and
  snapshotting (useful for netcode and rollback: Overwatch built its netcode on ECS).
- Costs: indirection for one-off logic, harder debugging of "who changed this", relationships (parent/child,
  targets) need explicit support (Flecs relationships), steep learning curve.
- **When to choose**: thousands of similar simulated things (bullets, units, particles with logic, crowds), heavy
  netcode/rollback needs. Stay with components for a few hundred heterogeneous, designer-authored objects. Hybrid is
  common: ECS for the hot simulation, objects for UI and one-off scripts.
- **System ordering**: make it explicit (phases: input, gameplay, physics, animation, render prep) and derive the
  order with a dependency graph (topological sort).

### Scene graph
A tree of transforms: a child's world transform = parent world * child local. Useful for attachment (weapon on hand,
UI hierarchies) and culling hierarchies. Pitfalls: deep trees make transform updates expensive (cache dirty flags;
update top-down once per frame), reparenting changes world position unless compensated, and a scene graph is not a
good spatial index (use a BVH/grid for queries).

## 3. Communication between systems

- **Direct calls**: simplest, tightest coupling.
- **Observer / events / signals**: subject notifies listeners; decouples sender from receivers. Pitfalls: listener
  leaks (always disconnect, tie connection lifetime to the owner), re-entrancy (a handler that fires the same event),
  unclear ordering, and events fired during iteration of the listener list (copy or defer).
- **Event queue / message bus**: decouple in time too (process at a known point of the frame); good for
  cross-thread and network boundaries; bounded queues and back-pressure.
- **Command pattern**: actions as objects: input remapping, undo/redo, replays, network input messages.
- **Service locator vs dependency injection**: prefer passing dependencies explicitly; global singletons hinder
  testing and hide order-of-initialization bugs.
- **Data-driven design**: tunables, item tables, AI parameters in data files with schema validation; hot reload.

## 4. Decision-making AI

| Technique | Best for | Weakness |
|---|---|---|
| Finite state machine (FSM) | Few, clear modes (door, enemy patrol/chase/attack) | State explosion; transitions everywhere |
| Hierarchical FSM / statecharts | Shared transitions via parent states (any "dead" transition), history states | Still author-heavy |
| Behavior tree (BT) | Reactive, modular, designer-readable behaviours (Halo 2 onwards, Unreal) | Can become huge; implicit priorities; "running" state handling |
| Utility AI | Many competing options scored by context (needs, tactics: The Sims, Infinite Axis Utility System) | Tuning curves; can dither without hysteresis |
| GOAP (goal-oriented action planning) | Emergent multi-step plans from actions with preconditions/effects (F.E.A.R.) | Planning cost; harder to author predictable behaviour |
| HTN (hierarchical task network) | Designer-structured plans (Horizon Zero Dawn, Transformers) | Domain authoring |
| Machine-learned policies | Testing bots, animation, NPC driving | Hard to control, explain and ship |

### State machines
- Each state: `enter`, `update`, `exit`; transitions are explicit and guarded. Never change state in the middle of
  another state's update without finishing the transition (queue it).
- Make illegal states unrepresentable (one current-state variable instead of many booleans).
- Pushdown automata (a state stack) for "pause menu over gameplay" or "stunned, then resume what you were doing".

### Behavior trees
- Node results: **Success, Failure, Running**. Composites: **Sequence** (AND: runs children left to right, fails on
  first failure, returns Running and resumes from that child), **Selector / Fallback** (OR: first child that does not
  fail), **Parallel** (policy-based). **Decorators**: inverter, repeater, cooldown, timeout, condition guards.
- **Reactive vs memory**: a reactive sequence re-evaluates earlier conditions every tick (so a guard can abort a
  running action); a memory sequence resumes from the running child. Know which one you are writing.
- Blackboard: shared per-agent key-value memory read by conditions and written by actions/sensors.
- Event-driven BTs (Unreal) avoid ticking the whole tree each frame: observers abort lower-priority branches when a
  blackboard key changes.
- A running action that gets aborted must be told (`onAbort`/halt) so it can stop animations and release resources.

### GOAP
World state as a set of facts; each action has preconditions, effects and cost; the planner runs A* backward (or
forward) from the goal over world states to find the cheapest action sequence. F.E.A.R. used a three-state FSM
(Goto, Animate, UseSmartObject) driven by a planner. Keep the state small (bitfields), re-plan on invalidation, and
cap planner time per frame.

### Utility AI
Score each option = product (or weighted combination) of considerations, each a response curve (linear, quadratic,
logistic) over a normalized input (distance, health, ammo). Use **compensation** for many multiplied factors, a
**momentum/inertia bonus** for the current action to avoid dithering, and weighted random among the top scores for
variety. Debug with per-agent score tables.

### Perception and coordination
Sight cones (dot product + raycast), hearing via events with radius, memory with decay (last known position).
Squad tactics: shared blackboard or a coordinator assigning roles/tokens (limit how many enemies attack at once:
"attack tokens"). Tactical position scoring = utility over sampled points (cover, distance, line of sight).

## 5. Pathfinding and movement

- **Graph representation**: grid (simple, memory heavy for big worlds), waypoint graph (hand-placed, sparse),
  **navigation mesh** (convex polygons covering walkable space: the industry default; Recast builds it by voxelizing
  the level, Detour queries it; also used in Unity, Unreal, Godot, Roblox PathfindingService).
- **A\***: `f = g + h`. With an **admissible** heuristic (never overestimates) the path is optimal; **consistent**
  (monotone) heuristics mean each node is expanded at most once. Grid heuristics: Manhattan (4-way), octile
  (8-way: `D*(dx+dy) + (D2-2D)*min(dx,dy)`), Euclidean (any angle). Weighted A* (`g + w*h`, w>1) trades optimality for
  speed. Tie-breaking toward larger g (or by a small h nudge) reduces expanded nodes on grids.
- **Implementation details**: open set as a binary heap with lazy deletion (push duplicates, skip stale pops);
  closed set as a hash/bitset; reconstruct the path from `cameFrom`; cap iterations/time and return "no path" vs
  "budget exceeded" separately.
- **Variants**: Dijkstra (no heuristic: many targets, or distance maps), BFS (unweighted), Jump Point Search (uniform
  grids, prunes symmetric paths), hierarchical pathfinding (HPA*: clusters + abstract graph for big maps), D* Lite /
  LPA* (incremental replanning when costs change), Theta* / any-angle, string pulling / funnel algorithm to smooth
  navmesh corridors.
- **Flow fields**: one Dijkstra/BFS from the goal outward produces an integration field, then a per-cell direction;
  every unit just reads its cell. Ideal for many units sharing one goal (RTS, tower defense, Supreme Commander 2,
  Planetary Annihilation). Cost: memory per goal; combine with local steering.
- **Local avoidance / steering**: seek, arrive, flee, separation, cohesion, alignment (Reynolds boids); RVO/ORCA for
  reciprocal collision avoidance in crowds (DetourCrowd).
- **Path following**: look-ahead point, re-path on blocked, smoothing, handling off-mesh links (jumps, ladders).
- Pathfinding cost spikes: time-slice queries across frames, cache paths, share paths for groups.

## 6. Procedural generation

- **Seeded determinism**: same seed -> same world; derive sub-seeds by hashing (seed, chunk x, chunk y) so chunks
  generate independently and in any order.
- **Noise**: value noise, gradient (Perlin) noise, simplex/OpenSimplex; fractal Brownian motion (octaves, lacunarity,
  gain); domain warping for organic shapes; Worley/cellular noise for cells and cracks.
- **Grammar and rule systems**: L-systems (plants), shape grammars (buildings), graph grammars (dungeon mission
  structure).
- **Space partitioning dungeons**: BSP split + rooms + corridors; cellular automata for caves (smooth walls with the
  4-5 rule); drunkard's walk; Poisson-disk sampling for even object placement.
- **Wave Function Collapse** (Maxim Gumin, 2016): constraint propagation over tile adjacency learned from an example;
  pick the lowest-entropy cell, collapse, propagate; restart or backtrack on contradiction.
- **Constraint solving / answer set programming** for guaranteed properties (key before lock, reachable exits).
- **Validation**: always verify generated content (connectivity via flood fill / BFS, difficulty bounds), and keep a
  fallback. Generate offline when possible; procedural does not mean runtime.

## 7. What STAR should do with an architecture question
1. Ask (or infer) scale: how many entities, how many players, target frame rate, deterministic or not.
2. Recommend the simplest structure that meets it, and say what would make you switch (e.g. "move to ECS beyond ~5k
   simulated entities or if you need rollback").
3. Show the loop/ordering explicitly; name the tick rates.
4. For AI: pick the decision technique from the table, show the data (states, nodes, considerations), and name the
   debug view you would build.

## Sources
- Glenn Fiedler, "Fix Your Timestep!": https://gafferongames.com/post/fix_your_timestep/
- Robert Nystrom, *Game Programming Patterns*: Game Loop https://gameprogrammingpatterns.com/game-loop.html ; Update Method https://gameprogrammingpatterns.com/update-method.html ; Component https://gameprogrammingpatterns.com/component.html ; Observer https://gameprogrammingpatterns.com/observer.html ; Event Queue https://gameprogrammingpatterns.com/event-queue.html ; State https://gameprogrammingpatterns.com/state.html ; Command https://gameprogrammingpatterns.com/command.html ; Data Locality https://gameprogrammingpatterns.com/data-locality.html
- Jason Gregory, *Game Engine Architecture*, 3rd ed. (book site): https://www.gameenginebook.com/
- Timothy Ford, "Overwatch Gameplay Architecture and Netcode" (GDC 2017): https://gdcvault.com/play/1024001/-Overwatch-Gameplay-Architecture-and
- Sander Mertens, Flecs documentation and ECS FAQ: https://www.flecs.dev/flecs/md_docs_2FAQ.html
- Unity Entities (DOTS) manual: https://docs.unity3d.com/Packages/com.unity.entities@1.3/manual/index.html
- Bevy ECS (component storage): https://docs.rs/bevy_ecs/latest/bevy_ecs/
- EnTT wiki (sparse sets): https://github.com/skypjack/entt/wiki
- "Archetypal ECS Considered Harmful?" (secondary, trade-offs): https://moonside.games/posts/archetypal-ecs-considered-harmful/
- Damian Isla, "Handling Complexity in the Halo 2 AI" (GDC 2005, Game Developer article): https://www.gamedeveloper.com/programming/gdc-2005-proceeding-handling-complexity-in-the-i-halo-2-i-ai
- Colledanchise and Oegren, *Behavior Trees in Robotics and AI* (arXiv): https://arxiv.org/abs/1709.00084
- Unreal Engine Behavior Tree overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/behavior-tree-in-unreal-engine---overview
- Jeff Orkin, "Three States and a Plan: The A.I. of F.E.A.R." (GDC 2006): https://gdcvault.com/play/1013282/Three-States-and-a-Plan
- Jeff Orkin, "Three States and a Plan" paper (PDF mirror): https://www.gamedevs.org/uploads/three-states-plan-ai-of-fear.pdf
- Dave Mark and Mike Lewis, "Building a Better Centaur: AI at Massive Scale" (GDC 2015, IAUS): https://gdcvault.com/play/1021848/Building-a-Better-Centaur-AI
- Kevin Dill, Dave Mark, "Improving AI Decision Modeling Through Utility Theory" (GDC 2010): https://gdcvault.com/play/1012410/Improving-AI-Decision-Modeling-Through
- Game AI Pro (free online chapters): https://www.gameaipro.com/
- Amit Patel, Red Blob Games, Introduction to A*: https://www.redblobgames.com/pathfinding/a-star/introduction.html ; Amit's A* pages (heuristics): https://theory.stanford.edu/~amitp/GameProgramming/Heuristics.html
- Red Blob Games, flow field pathfinding for tower defense: https://www.redblobgames.com/pathfinding/tower-defense/
- Elijah Emerson, "Crowd Pathfinding and Steering Using Flow Field Tiles" (Game AI Pro, ch. 23): https://www.gameaipro.com/GameAIPro/GameAIPro_Chapter23_Crowd_Pathfinding_and_Steering_Using_Flow_Field_Tiles.pdf
- Harabor and Grastien, Jump Point Search: https://users.cecs.anu.edu.au/~dharabor/data/papers/harabor-grastien-aaai11.pdf
- Recast & Detour navigation mesh toolset: https://recastnav.com/ and https://github.com/recastnavigation/recastnavigation
- Craig Reynolds, steering behaviors: https://www.red3d.com/cwr/steer/
- van den Berg et al., RVO2 / ORCA: https://gamma.cs.unc.edu/RVO2/
- Maxim Gumin, WaveFunctionCollapse: https://github.com/mxgmn/WaveFunctionCollapse
- Red Blob Games, noise-based terrain: https://www.redblobgames.com/maps/terrain-from-noise/
- PCG book, Shaker, Togelius, Nelson, *Procedural Content Generation in Games* (free): https://www.pcgbook.com/
