# Playbook: understanding an unfamiliar codebase, engine or language quickly

Researched 2026-10-13. This is the transferable method STAR follows whenever it meets code it has not seen before
(a user's project, a new engine, a new language). It is written as steps STAR can execute with read-only tools.
Sources at the end.

## 0. Principles
- **Read before writing.** Never propose an edit to a file you have not opened. Never invent an API name: find it in
  the code, the docs, or say it is unverified.
- **Top-down, then follow one thread end to end.** Breadth first to build a map, then depth on the path that matters
  for the task.
- **Run it if you can.** Behaviour observed beats behaviour inferred. A failing test you ran beats a theory.
- **Write the map down** (short notes: entry points, data flow, conventions). It is what makes the next question fast.
- Treat comments, READMEs and docs as claims to verify against the code; they drift.

## 1. Orient (first 10 minutes)
1. **What is it?** Read README, CONTRIBUTING, AGENTS/CLAUDE files, docs index, license. Note the product purpose
   and the build/run/test commands.
2. **Shape of the tree**: list top-level directories and the biggest/most-changed files
   (`git ls-files | head`, file counts per directory, `git log --format= --name-only | sort | uniq -c | sort -rn | head`).
   Hot files are where the logic lives; frequently co-changed files are coupled.
3. **Manifests tell the stack**: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.csproj`, `CMakeLists.txt`,
   `project.godot`, `*.uproject`, `ProjectSettings/`, `default.project.json` (Rojo), `wally.toml`. Read dependencies:
   they reveal frameworks and patterns (ECS library, networking library, test framework).
4. **CI config** (`.github/workflows`, etc.) is the most reliable statement of how the project is really built and
   tested.
5. **History**: `git log --oneline -30`, recent PR titles; who works on what; conventions in commit messages.

## 2. Find the entry points and the main loop
- Executables: `main`, `Program.cs`, `__main__`, server bootstraps, `index.ts`; engine-specific: startup scenes,
  `GameMode`/`GameInstance` (Unreal), autoloads (Godot), `ServerScriptService` and `StarterPlayerScripts` (Roblox),
  bootstrap MonoBehaviours / `[RuntimeInitializeOnLoadMethod]` (Unity).
- Find the update loop or event loop and the order of systems. In a web/server codebase find the router and request
  pipeline (middleware).
- Find configuration loading and feature flags: behaviour often hides there.

## 3. Follow one feature end to end
Pick the feature the task is about (or the most central one: "player takes damage", "user logs in") and trace:
input/event -> handler -> domain logic -> state change -> persistence/network -> presentation. Use
"find references", grep for the user-visible string (a UI label, an error message, a log line), and a debugger
breakpoint or a log statement to confirm the path at runtime. Note every boundary crossed (thread, process, network,
client/server).

## 4. Build the mental model
- **Data model first**: the core types/tables/components and their invariants. Code is easier to read once you know
  the nouns.
- **Ownership and lifetimes**: who creates, mutates and destroys each thing; which side (client/server) is
  authoritative.
- **Architecture style**: layered, ECS, MVC/MVVM, actor, event-driven, plugin-based. Note the dependency direction.
- **Conventions**: naming, error handling style, logging, test layout, formatting tools. Match them in any change.
- Use structure tools when available: code graph (graphify in STAR's setup), language server "go to definition" and
  call hierarchy, ctags, dependency graphs (madge, pydeps, cargo-modules), docs generators.

## 5. Learn a new engine quickly (transferable checklist)
For any engine, answer these questions; each maps to a concept in the other fundamentals documents:
1. Object model: scene tree / actors / entities / instances? How are components attached? (game-architecture)
2. Lifecycle callbacks and their order: init, start, per-frame update, fixed update, late update, destroy.
3. Time: where is delta time; is there a fixed physics step; how to schedule delayed work and coroutines.
4. Input, physics (units, up axis, handedness, collision layers), rendering pipeline choice.
5. Networking model: who is authoritative, how replication works, how RPCs/remotes are validated.
6. Assets and serialization: how scenes/prefabs are stored, how references survive renames, import pipeline.
7. Scripting and threading model: main thread only? job system? garbage collection behaviour?
8. Tooling: profiler, debugger, logging, test framework, build/packaging, version control conventions for binaries.
9. Official samples: read one small official sample end to end; it shows the idiomatic way.
Write the answers as a one-page "engine cheat sheet" before writing gameplay code.

## 6. Learn a new language quickly
1. Execution model: compiled/interpreted/JIT, GC vs ownership vs manual memory, value vs reference semantics,
   integer and float types, string encoding, 0- vs 1-based indexing.
2. Types: static/dynamic/gradual, nullability, generics, error handling (exceptions, result types, multiple returns,
   pcall).
3. Modules and packages, the standard build and test commands, the formatter and linter the community uses.
4. Concurrency model: threads, async/await, coroutines, actors; what is safe to share.
5. Idioms: iterate a collection, build a string, map/filter, define a type, write a test. Write ten small programs or
   translate a known algorithm (binary search, BFS, a heap) and test them.
6. Footguns list (every language has one: JS `==` and `this`, Python mutable default args, C++ UB, Lua/Luau 1-based
   arrays and `#` on tables with holes, Go loop variable capture before 1.22, C# struct copies).
Use the official tour/reference, then the community style guide, then an idiomatic open-source project.

## 7. Make the first change safely
1. Reproduce the current behaviour with a test or a scripted run (characterization test if no tests exist).
2. Make the smallest change in the existing style; keep public signatures unless asked.
3. Run the project's own checks (the CI commands from step 1).
4. Explain what you verified and what you could not.
For larger refactors in legacy code: find seams (places where behaviour can be changed without editing in place),
break dependencies to get code under test, then refactor in small steps (Feathers). The Mikado method helps plan a
change that has many prerequisites.

## 8. What STAR should say when it meets an unfamiliar codebase
"First I will read X, Y, Z (entry point, the feature path, the tests) and tell you the map; then propose the change."
Then give the map in five to ten lines: stack, entry points, main loop/request path, data model, conventions, how to
build/test, risks. Mark anything inferred rather than read.

## Sources
- Michael Feathers, *Working Effectively with Legacy Code* (seams, characterization tests): https://www.oreilly.com/library/view/working-effectively-with/0131177052/
- Michael Feathers, "Characterization Testing": https://michaelfeathers.silvrback.com/characterization-testing
- Adam Tornhill, *Your Code as a Crime Scene*, 2nd ed. (hotspots, change coupling from git history): https://pragprog.com/titles/atcrime2/your-code-as-a-crime-scene-second-edition/
- Marianne Bellotti, *Kill It with Fire* (legacy modernization): https://nostarch.com/kill-it-fire
- Ellnestam and Brolund, *The Mikado Method*: https://www.manning.com/books/the-mikado-method
- Peter Naur, "Programming as Theory Building" (1985), reprinted: https://pages.cs.wisc.edu/~remzi/Naur.pdf
- Felienne Hermans, *The Programmer's Brain* (reading unfamiliar code): https://www.manning.com/books/the-programmers-brain
- Google, *Software Engineering at Google* (code search, readability): https://abseil.io/resources/swe-book
- Git documentation (log, blame, bisect): https://git-scm.com/docs
- Language Server Protocol (go to definition, references, call hierarchy): https://microsoft.github.io/language-server-protocol/
- Learn X in Y minutes (quick language tours, secondary): https://learnxinyminutes.com/
- Unity manual, order of execution for event functions: https://docs.unity3d.com/Manual/execution-order.html
- Godot docs, idle and physics processing: https://docs.godotengine.org/en/stable/tutorials/scripting/idle_and_physics_processing.html
- Unreal Engine, actor lifecycle: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle
- Roblox, task scheduler and frame order: https://create.roblox.com/docs/studio/microprofiler/task-scheduler
