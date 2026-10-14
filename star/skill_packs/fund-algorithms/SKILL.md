---
name: fund-algorithms
description: Engine-independent algorithms, data structures, complexity, floating point, integration and game math (vectors, matrices, quaternions). Use when choosing a data structure, analysing complexity or writing math-heavy game code.
---
# Algorithms, data structures and game math (engine-independent)
## Choose by the dominant operation
- Say n, the operation mix and the budget first, then pick: array (index, fast iteration; remove = swap with last and pop), hash map (key lookup), ordered tree (range queries), binary heap (repeated min/max: A*, Dijkstra, schedulers, timers), ring buffer (FIFO, input history), bitset (small id sets), sparse set (O(1) add/remove + dense iteration), union-find (groups, islands), generational index (stable handles).
- "Things near X": uniform grid / spatial hash with cell size about the query radius (O(n*k) instead of all-pairs O(n^2)); quadtree/octree for uneven density; BVH for rays and static geometry.
- Big-O hides constants: for n below a few hundred, a contiguous array scan often wins. Avoid allocation and O(n) work inside per-frame loops; pre-size when the maximum is known.
## Algorithms to reach for
- Library sort; stable sort or a composite key for ties; heap of size k for top-k; counting/radix sort for small integer keys.
- Binary search on half-open [lo, hi); at most floor(log2 n)+1 comparisons. Binary search also works on any monotone yes/no predicate.
- BFS (unweighted shortest path), Dijkstra (non-negative weights, heap), A* (Dijkstra plus admissible heuristic), Kahn topological sort (dependency order, cycle detection), Kruskal with union-find (spanning trees, maze generation).
- Seed every RNG you want to reproduce; Fisher-Yates shuffle; never use a game PRNG for security tokens.
## Floating point
- Never compare computed floats with ==; use a tolerance scaled to magnitude. Guard divisions and normalisation (length > 1e-8). NaN is the only value where x ~= x.
- Precision falls with distance from the origin (32-bit float: about 1 cm at 100 km); big worlds need a floating origin or doubles.
- Summation order changes results, so bit-exact determinism across machines needs the same binary, a fixed operation order, or fixed-point math.
- Long-running clocks: compute time = tick * dt instead of adding dt forever.
## Integration and smoothing
- Semi-implicit Euler (v += a*dt, then x += v*dt) at a fixed dt is the game default; explicit Euler gains energy; Verlet for particles; XPBD for stiff cloth/ropes.
- Frame-rate independent smoothing: x = lerp(x, target, 1 - exp(-k*dt)), never a constant lerp factor per frame.
## Vectors, matrices, quaternions
- dot: projection, facing tests (dot(forward, toTarget) > 0), field of view (dot > cos(fov/2)). cross: normals, left/right test, torque.
- Name variables by space (posWorld, dirLocal); transform order depends on the convention; normals use the inverse-transpose under non-uniform scale.
- Unit quaternion q = (cos(theta/2), sin(theta/2)*axis). With v' = q v q^-1, q2*q1 means q1 first, then q2: wrong order is the most common bug.
- q and -q are the same rotation: negate one when dot(q1, q2) < 0 before slerp. Use nlerp when nearly parallel; renormalise after many multiplications.
- Euler angles: readable but gimbal lock and order ambiguity; do not interpolate them.
## Answer checklist
State the complexity of the naive and the chosen approach, name edge cases (empty, ties, duplicates, unreachable, overflow, float tolerance) and give one test that would catch the most likely bug.
