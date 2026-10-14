# Sources for fund-algorithms

Distilled from the long-form research note `docs/research/fundamentals/algorithms-and-math.md` (researched 2026-10-13; a copy ships as `references/notes.md` so Agent mode can read it with star_skill_reference). Primary sources (papers, official documentation, talks by the engineers who shipped the technique, standards bodies) come first; secondary write-ups are marked as such. This pack is engine- and language-independent: it names no engine API, so there is nothing to verify with the knowledge service /api-lookup.

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
