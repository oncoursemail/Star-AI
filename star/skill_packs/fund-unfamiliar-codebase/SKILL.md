---
name: fund-unfamiliar-codebase
description: A transferable playbook for understanding an unfamiliar codebase, game engine or programming language quickly - orient, find entry points, trace one feature end to end, build the data model, learn engine and language checklists, make a safe first change.
---
# Playbook: understand unfamiliar code, engines and languages fast
## Rules
- Read before writing: never edit a file you have not opened; never invent an API name (find it in the code or docs, or label it unverified).
- Breadth first to build a map, then depth on the one path the task needs. Observed behaviour beats inferred behaviour. Comments and docs are claims to check against the code.
## 1. Orient
README, contributing and agent instruction files, docs index; the build, run and test commands. Top-level directories and the most changed files in git history (hot spots hold the logic; files that change together are coupled). Manifests reveal the stack (package.json, pyproject.toml, Cargo.toml, go.mod, csproj, CMakeLists.txt, project.godot, uproject, Rojo default.project.json, wally.toml). CI workflows are the truth about how it is built and tested. Recent commits show conventions.
## 2. Entry points and the main loop
Find main/bootstrap, the startup scene or server bootstrap, the per-frame or event loop and the order of systems; for services, the router and middleware. Find configuration and feature flags.
## 3. Trace one feature end to end
Input or event -> handler -> domain logic -> state change -> persistence or network -> presentation. Search for a user-visible string or log line, use find-references, and confirm at runtime with a log line or breakpoint. Mark every boundary crossed (thread, process, client/server).
## 4. Mental model
Data model first (core types, tables, components and their invariants); ownership and lifetimes (who creates, mutates, destroys; which side is authoritative); architecture style and dependency direction; conventions (naming, errors, logging, tests, formatter). Use a code graph, go-to-definition and call hierarchy where available.
## 5. New engine checklist
Object model (scene tree, actors, entities, instances); lifecycle callbacks and their order; delta time, fixed physics step, scheduling delayed work; input; physics units, up axis, handedness, collision layers; rendering pipeline; networking authority and how remote calls are validated; asset and scene serialisation; threading and garbage collection; profiler, debugger, test framework, packaging. Read one small official sample end to end, then write a one-page cheat sheet before gameplay code.
## 6. New language checklist
Execution and memory model (GC, ownership, manual), value vs reference semantics, number types, string encoding, 0- or 1-based indexing; type system, nullability, generics; error handling (exceptions, result types, multiple returns, pcall); modules, build, test, formatter, linter; concurrency model; idioms for iterate, map/filter, build strings, define types, write a test. Translate a known algorithm (binary search, BFS, heap) with tests. Keep a footgun list (e.g. JS equality and this, Python mutable default arguments, C++ undefined behaviour, Luau 1-based arrays and # on tables with holes, C# struct copies).
## 7. First change, safely
Pin current behaviour with a test or scripted run (a characterization test if none exist); make the smallest change in the existing style; keep public signatures; run the project's own checks; report what was verified and what was not. For legacy code find seams, break dependencies to get code under test, refactor in small steps.
## What to tell the user
First what you will read (entry point, feature path, tests) and then a five-to-ten line map: stack, entry points, main loop or request path, data model, conventions, how to build and test, risks. Mark anything inferred rather than read.
