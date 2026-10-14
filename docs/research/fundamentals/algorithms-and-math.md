# Algorithms, data structures, numerical methods and game math

Researched 2026-10-13. Engine- and language-independent. Sources at the end.

## 1. Complexity: how to reason, not just recite

- **Big-O is an upper bound on growth, not a speed.** An O(n) scan over a contiguous array of 1,000 items often beats
  an O(log n) lookup in a pointer-heavy tree because of cache behaviour. For n below a few hundred, measure.
- **Amortized cost**: a dynamic array's append is O(1) amortized (capacity doubling), but a single append can be O(n).
  In a frame-budgeted game loop a rare O(n) spike is a hitch; pre-size (`reserve`, `table.create`) when the
  maximum is known.
- **Expected vs worst case**: hash tables are O(1) expected, O(n) worst case (collisions, adversarial keys). Quicksort is
  O(n log n) expected, O(n^2) worst; production sorts use introsort/pdqsort (quicksort that falls back to heapsort) or
  Timsort/powersort (stable, adaptive to runs).
- **Space matters**: memory traffic is usually the real cost. Struct-of-arrays (SoA) layouts beat array-of-structs
  (AoS) when a loop touches few fields of many items; this is the core argument for data-oriented design and ECS.
- **Lower bounds worth knowing**: comparison sorting is Omega(n log n); searching an unsorted list is Omega(n);
  binary search on a sorted array of n items needs at most floor(log2 n) + 1 comparisons (20 for 1,000,000).

## 2. Choosing a data structure

| Need | Use | Avoid / note |
|---|---|---|
| Index by position, iterate fast | Dynamic array | Linked list (pointer chasing, poor cache) unless O(1) splice with stable iterators is essential |
| Remove from middle, order irrelevant | Array + swap-with-last-and-pop, O(1) | Shifting removal, O(n) |
| Key -> value | Hash map | Ordered map unless you need ordered iteration or range queries |
| Ordered keys, range queries | Balanced BST / B-tree / skip list, O(log n) | Re-sorting an array after each insert |
| Repeatedly take min/max (schedulers, A*, Dijkstra, event queues) | Binary heap (O(log n) push/pop, O(1) peek) | Sorting the whole list each time |
| FIFO / BFS / input buffers | Ring buffer or deque | Removing index 1 from an array (O(n)) |
| Membership of small integer ids | Bitset | Hash set of ints |
| Sparse id -> dense packed storage | Sparse set (sparse[] + dense[]) | Used by EnTT-style ECS for O(1) add/remove and dense iteration |
| Union of groups, connectivity (islands, Kruskal) | Disjoint set with path compression + union by rank (near O(1)) | |
| Prefix search, autocomplete | Trie / radix tree | |
| Stable handles to objects that move | Generational index (slot + generation counter) | Raw pointers/indices that dangle after reuse |
| "Nearby" queries in space | Uniform grid / spatial hash (uniform sizes), quadtree/octree (varying density), BVH (static or refit geometry, ray casts), k-d tree (static points, k-NN) | Checking all pairs: O(n^2) |
| Approximate membership | Bloom filter (false positives, no false negatives) | |

Rule of thumb STAR should say aloud: *name the dominant operation, its frequency, n, and the access pattern, then
pick the structure*. Example: "1,000 projectiles, each needs neighbours within 5 units every frame" -> spatial hash
with cell size about the query radius: O(n * k) instead of O(n^2).

## 3. Core algorithms

- **Sorting**: use the library sort. Need stability (sort by score, then keep name order)? Use a stable sort or a
  composite key. Partial order only (top-k)? Use a heap of size k: O(n log k). Integers in a small range: counting /
  radix sort O(n + k). Render sorting by a packed 64-bit key (layer, material, depth) then radix sort is a classic
  engine technique.
- **Searching**: binary search needs a sorted, random-access container; write it with half-open intervals
  `[lo, hi)` and `mid = lo + (hi - lo) // 2` to avoid overflow and off-by-one errors. Binary search on the answer
  ("smallest speed that finishes in time") works on any monotone predicate.
- **Graphs**: BFS gives shortest paths in unweighted graphs; Dijkstra for non-negative weights (heap, O((V+E) log V));
  A* = Dijkstra + admissible heuristic; Bellman-Ford for negative edges; topological sort (Kahn's algorithm) for
  dependency ordering (build systems, system scheduling in ECS, task graphs) and cycle detection; Tarjan/Kosaraju for
  strongly connected components; minimum spanning tree (Kruskal with union-find, Prim with heap) for maze/level
  generation.
- **Dynamic programming**: when the problem has optimal substructure and overlapping subproblems (edit distance,
  knapsack-style loadouts, sequence alignment). Write the recurrence first, then memoize or tabulate.
- **Greedy**: correct only with a proof (exchange argument); otherwise it is a heuristic.
- **Randomness**: seed explicitly for reproducibility (procedural generation, tests, replays). Use a fast PRNG
  (PCG, xoshiro, SplitMix64); never a cryptographic one in the hot path, never a non-cryptographic one for security
  tokens. Fisher-Yates for unbiased shuffles. Reservoir sampling to pick k items from a stream.
- **Hashing**: combine hashes properly (e.g. `h ^= v + 0x9e3779b9 + (h << 6) + (h >> 2)`), and never use a hash of
  floating-point positions as a grid key without quantizing first (`floor(x / cell)`).

## 4. Numerical methods every game programmer needs

### Floating point
- IEEE-754 doubles have ~15-16 significant decimal digits, floats ~7. Precision falls with magnitude: at 100 km a
  32-bit float resolves only ~8 mm; at 10,000 km ~1 m. Large worlds need origin rebasing / floating origin or doubles
  (Unreal 5 uses 64-bit Large World Coordinates).
- Never compare floats with `==` after arithmetic; compare with a tolerance scaled to the magnitude
  (`abs(a-b) <= eps * max(1, abs(a), abs(b))`). `0.1 + 0.2 ~= 0.3`.
- Floating-point addition is not associative, so summation order changes results: parallel reductions and different
  compilers/instruction sets (x87 vs SSE, FMA contraction) break bit-exact determinism. Cross-platform lockstep needs
  fixed-point math or strict IEEE mode with a controlled operation set (Fiedler, "Floating Point Determinism").
- Catastrophic cancellation: subtracting nearly equal numbers loses digits; rearrange formulas
  (e.g. the numerically stable quadratic formula, `log1p`, `hypot`).
- Accumulating small increments into a large total drifts; use Kahan summation or recompute from a base value
  (e.g. `elapsed = tick * dt`, not `elapsed += dt` for a long-running clock).
- Guard every division and normalize: `if len > 1e-8 then v / len`. NaN propagates silently and compares false to
  everything, including itself (`x ~= x` detects it).

### Integration (simulation)
- **Explicit Euler** (`x += v*dt; v += a*dt`) gains energy and explodes for springs and orbits.
- **Semi-implicit (symplectic) Euler** (`v += a*dt; x += v*dt`) is the default in game physics engines: same cost,
  stable for oscillators at reasonable dt, conserves energy on average.
- **Velocity Verlet** is second order and symplectic; good for particles and cloth.
- **RK4** is accurate but four force evaluations per step and not symplectic (slowly drains energy); rarely worth it
  for gameplay rigid bodies.
- **Implicit / position-based (PBD/XPBD)** methods stay stable for stiff constraints (cloth, soft bodies, ropes).
- Stability depends on `dt * stiffness`; a **fixed dt** is what makes a simulation reproducible.
- **Frame-rate independent smoothing**: `x = lerp(x, target, 1 - exp(-k * dt))`, not `lerp(x, target, 0.1)` per frame.
  Critically damped springs (e.g. Game Programming Gems "SmoothCD") give overshoot-free following cameras.

### Root finding, interpolation and curves
- Bisection (robust), Newton-Raphson (fast, needs derivative and a good start), secant method. Use them for
  time-of-impact searches, inverse easing, ballistic aim solving.
- Linear interpolation `a + (b-a)*t`; inverse lerp; remap. Smoothstep `t*t*(3-2t)`.
- Bezier curves (de Casteljau), Catmull-Rom splines (pass through control points; centripetal variant avoids
  cusps), Hermite splines (position + tangent). Arc-length reparameterize for constant-speed motion.

## 5. Linear algebra for games

- **Vectors**: dot product `a.b = |a||b|cos(theta)`: projection, "is it in front" (`dot(forward, toTarget) > 0`),
  field of view tests (`dot > cos(fov/2)`), lighting (N.L). Cross product: surface normals, winding/handedness,
  torque, "is target to the left or right" (sign of the up component).
- **Matrices**: 4x4 homogeneous transforms combine rotation, scale and translation; composition order matters and
  depends on the convention (column vectors: `M = T * R * S`, applied right to left). Know your engine's convention
  (row vs column major storage is a separate question from row vs column vectors).
- Inverse of a rigid transform is cheap: `R^T` and `-R^T t`. Transform normals with the inverse-transpose when scale
  is non-uniform.
- **Spaces**: object/local -> world -> view/camera -> clip -> NDC -> screen. Bugs often come from mixing spaces;
  name variables with their space (`posWorld`, `dirLocal`).
- **Handedness and up-axis** differ between tools and engines (Y-up vs Z-up, left vs right handed): convert once at
  the import boundary.

### Rotations and quaternions
- Euler angles are readable but suffer gimbal lock and order ambiguity (XYZ vs ZYX); interpolating them looks wrong.
- A unit quaternion `q = (cos(theta/2), sin(theta/2) * axis)` represents a rotation of theta around a unit axis.
  Rotate a vector with `v' = q v q^-1` (q^-1 is the conjugate for unit quaternions).
- **Composition**: `q2 * q1` means "apply q1 first, then q2" (with the `q v q*` convention). Getting this order wrong is
  the most common quaternion bug.
- `q` and `-q` represent the same rotation. Before interpolating, if `dot(q1, q2) < 0` negate one to take the short
  path.
- **Slerp** gives constant angular velocity; **nlerp** (lerp then normalize) is cheaper, commutative and good enough
  for animation blending with small angles. Fall back to nlerp when the quaternions are nearly parallel to avoid
  division by ~0.
- Re-normalize after many multiplications (drift).
- Integrating angular velocity: `q += 0.5 * (0, omega) * q * dt; normalize(q)`.
- Swing-twist decomposition splits a rotation into a twist about an axis and the remaining swing: used for joint
  limits and IK constraints.
- Look-rotation from a forward and up vector: orthonormalize with cross products (Gram-Schmidt), handle the
  degenerate case when forward is parallel to up.

### Geometry primitives worth having by heart
Ray-plane, ray-sphere, ray-AABB (slab method), ray-triangle (Moller-Trumbore), AABB-AABB overlap, sphere-sphere,
closest point on segment/triangle, point-in-polygon (winding number), segment intersection with orientation tests,
barycentric coordinates. Robustness: use epsilons consistently; exact predicates (Shewchuk) when topology must
never be wrong (mesh booleans, navmesh generation).

## 6. What STAR should do when asked an algorithm question
1. Restate n, the operation mix and the constraints (real-time budget, memory, determinism).
2. Give the complexity of the naive solution and the chosen one, and name the data structure.
3. Mention the edge cases (empty, duplicates, ties, overflow, float tolerance, unreachable goal).
4. Provide a test that would fail on the most likely bug (off-by-one, wrong comparator, missing normalize).

## Sources
- Cormen, Leiserson, Rivest, Stein, *Introduction to Algorithms* (4th ed., MIT Press 2022): https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/
- Sedgewick and Wayne, *Algorithms*, 4th ed. (book site): https://algs4.cs.princeton.edu/home/
- Big-O cheat sheet (secondary, quick reference): https://www.bigocheatsheet.com/
- Orson Peters, pdqsort (pattern-defeating quicksort): https://github.com/orlp/pdqsort
- Python `list.sort` / Timsort and powersort notes (CPython listsort.txt): https://github.com/python/cpython/blob/main/Objects/listsort.txt
- PCG random number generators: https://www.pcg-random.org/
- David Goldberg, "What Every Computer Scientist Should Know About Floating-Point Arithmetic": https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html
- Glenn Fiedler, "Floating Point Determinism": https://gafferongames.com/post/floating_point_determinism/
- Glenn Fiedler, "Integration Basics": https://gafferongames.com/post/integration_basics/
- Bruce Dawson, "Comparing Floating Point Numbers, 2012 Edition": https://randomascii.wordpress.com/2012/02/25/comparing-floating-point-numbers-2012-edition/
- Unreal Engine, Large World Coordinates: https://dev.epicgames.com/documentation/en-us/unreal-engine/large-world-coordinates-in-unreal-engine-5
- Freya Holmer, "Lerp smoothing is broken" (frame-rate independent damping, talk): https://www.youtube.com/watch?v=LSNQuFEDOyQ
- Real-Time Rendering resources, object/object intersection table: https://www.realtimerendering.com/intersections.html
- Christer Ericson, *Real-Time Collision Detection* (book site): https://realtimecollisiondetection.net/
- Ken Shoemake, "Animating Rotation with Quaternion Curves" (SIGGRAPH 1985), via ACM: https://dl.acm.org/doi/10.1145/325165.325242
- 3D Math Primer for Graphics and Game Development (free online edition): https://gamemath.com/book/
- Jonathan Blow, "Understanding Slerp, Then Not Using It": http://number-none.com/product/Understanding%20Slerp,%20Then%20Not%20Using%20It/
- Matthias Mueller et al., XPBD: "Position-Based Simulation of Compliant Constrained Dynamics": https://matthias-research.github.io/pages/publications/XPBD.pdf
- Jonathan Shewchuk, robust geometric predicates: https://www.cs.cmu.edu/~quake/robust.html
- EnTT (sparse-set ECS) documentation: https://github.com/skypjack/entt/wiki
