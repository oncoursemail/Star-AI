# Fundamentals research (engine- and language-independent)

Researched 2026-10-13 for STAR. Scope: the knowledge that transfers between engines (Roblox, Unity, Unreal, Godot,
custom) and languages (Luau, C#, C++, Rust, TypeScript, Python). Engine- and language-specific research lives in
sibling folders written by other agents; this folder deliberately avoids engine API names except as examples.

| File | Covers |
|---|---|
| [algorithms-and-math.md](algorithms-and-math.md) | Complexity, data-structure choice, sorting/searching, graphs, hashing, spatial structures, numerical methods (floats, integration, root finding), vectors/matrices/quaternions for games |
| [game-architecture-and-ai.md](game-architecture-and-ai.md) | Game loop, fixed timestep, ECS vs OOP, scene graphs, events, state machines, behavior trees, GOAP, utility AI, pathfinding (A*, navmesh, flow fields), procedural generation |
| [rendering-physics-animation.md](rendering-physics-animation.md) | Forward/deferred/clustered rendering, PBR, shadows, GI, collision detection, integrators, constraint solvers, determinism, IK, blend trees, motion matching |
| [multiplayer-netcode.md](multiplayer-netcode.md) | Authority models, client prediction, reconciliation, interpolation, lag compensation, rollback, interest management, bandwidth, anti-cheat |
| [software-engineering.md](software-engineering.md) | Design patterns, testing strategy, debugging method, profiling, concurrency, security (OWASP Top 10:2025, ASVS 5.0), API design, version control, CI/CD |
| [unfamiliar-codebase-playbook.md](unfamiliar-codebase-playbook.md) | A step-by-step method STAR follows to understand an unknown codebase, engine or language quickly |

## How STAR uses this

1. **Skill packs** (`star/skill_packs/fund-*`): a short distilled checklist per area, chosen in code for matching
   prompts (see `star/skill_packs/__init__.py`, `GENERAL_PACKS`). Fundamentals packs may fire for non-Roblox prompts
   too, because the knowledge is engine-independent. Like every pack they are **off by default** until the evaluation
   gate shows they do not lower the golden-task score (docs/evals.md). Enable with
   `STAR_SKILL_PACKS=fund-algorithms,fund-netcode,...` or `all`. In Agent mode every pack is also loadable on demand
   through `star_skill_load` / `star_skill_reference` regardless of triggers.
2. **Golden tasks**: `evals/roblox/golden-tasks-fundamentals-v1.json` (pure-Luau tasks with harness-owned unit tests:
   heap, A*, fixed timestep, quaternions, prediction/reconciliation, behavior tree, spatial hash) and
   `evals/general_knowledge/fundamentals-v1.*.json` (ten closed-world JSON-answer tasks with reviewed oracles).
3. **These documents** are the long form. They are the source the packs were distilled from and the place to update
   first when something changes.

## Source policy

Primary sources first (papers, official engine/library docs, talks by the engineers who shipped the technique,
standards bodies). Secondary write-ups are named as such. Where sources disagree or a number is a vendor claim, the
text says so. Every file ends with a source list. All 143 URLs were requested on 2026-10-13: dead links were replaced
or removed; the rest answered 200, except about a dozen publisher sites (ACM, MIT Press, O'Reilly, realtimerendering.com,
unrealengine.com and similar) that answer 403/406 to automated clients but load in a browser.

## How the evals were checked

- `evals/roblox/golden-tasks-fundamentals-v1.json`: the shipped reference answers (`reference/FND-*.md`) pass and the
  deliberately wrong ones (`reference/FND-*.bad.md`) fail, verified with the harness's own scorer
  (`star.eval_checks.score_answer`) but with the official Luau CLI on a PC (luau and luau-analyze from the
  luau-lang/luau release) standing in for the server sandbox and the knowledge service `/luau/check`. Only these
  harness-owned answers were run locally; model answers are still only run in the server sandbox. Re-run
  `python -m star.evals selftest --suite evals/roblox/golden-tasks-fundamentals-v1.json` on the server before the
  suite is used for a gate decision.
- `evals/general_knowledge/fundamentals-v1.*.json`: loaded by `star.general_knowledge_benchmark` and every oracle is
  recomputed independently in `tests/test_fundamentals.py`.
- No model has been run on either suite yet; there is no baseline.

## Known gaps

- No measured effect yet: the packs have not been through the evaluation gate on the STAR server.
- Rendering coverage is conceptual (pipeline choice, PBR terms, shadow/GI families); shader-level detail and
  GPU-API specifics (Vulkan/D3D12 barriers, bindless) are out of scope here.
- Audio, UI/UX design, economy/live-ops design and console certification are not covered.
