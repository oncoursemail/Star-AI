# STAR Frontier GitHub Issue Backlog — proposed, not remotely created

This is a repo-ready backlog for STAR's future GitHub issues. Priority tags P0 critical / P1 major / P2 research. Issues are concise and each has measurable exit evidence. **None are claimed to exist on GitHub yet.**

## P0 — make one trustworthy complete loop

1. **STAR-001 · Local health check**: verify the selected model, actual image bytes, Studio MCP tool schemas and the selected studio instance; save a health report without model secrets.
2. **STAR-002 · Model benchmark profiler**: log VRAM/context/tokens-sec/task outcome across candidate local models and quantizations.
3. **STAR-003 · Immutable reference registry**: preserve original images with hash, dimensions, role, annotation and approval state.
4. **STAR-004 · Roblox scene probe**: capture script and object paths, classes and selected properties, current play mode and console evidence.
5. **STAR-005 · UI native rect probe**: instrument Roblox GUI descendants and capture their actual bounding rectangles under selected device profiles.
6. **STAR-006 · First native UI builder**: generate an interactive panel from an owned screenshot, without flattening controls into a raster image.
7. **STAR-007 · Standalone trusted fixture runner**: execute and record small reproducible Luau and Studio tests outside the worker's editable scope.
8. **STAR-008 · Evidence journal**: atomically bind candidate commit, baseline place, action log and screenshots.
9. **STAR-009 · Independent acceptance gate**: reject blocked, unknown and hard-failure cases; allow only reviewed candidate promotion.
10. **STAR-010 · One complete visual repair**: introduce a deliberate UI overlap, have STAR detect it via evidence and fix it without changing protected design.
11. **STAR-011 · Initialize private GitHub repo**: make `star-core`, push audited baseline, verify remote SHA; do not claim success before GitHub reports it.
12. **STAR-012 · Register STAR GitHub App**: selected repository only, scoped installation token and a small working draft PR; never expose private key to model.

## P1 — deepen reliable Roblox capabilities

13. **STAR-013 · Rojo + sourcemap integration**: enforce one source of truth for Luau and map Studio paths to repository files.
14. **STAR-014 · Remote authority inspector**: map client/server events to validation, cooldown, state mutation and permission checks.
15. **STAR-015 · Adversarial purchase fixture**: catch duplicate rewards, invalid values and disconnect race conditions in owned test game.
16. **STAR-016 · Task dependency coordinator**: prevent concurrent edits to same Studio instance or shared source resource.
17. **STAR-017 · Process-crash recovery**: resume from journal, check actual side effects, never repeat completed uploads/commits.
18. **STAR-018 · Compaction with exact retrieval**: persist compact active summary, retain original code/media and reproduce approved facts.
19. **STAR-019 · Project decision versioning**: approved/rejected/superseded, with revocation and source hashes.
20. **STAR-020 · Responsive layout compiler**: translate aligned/centered/equal-spacing constraints to native Roblox GUI plus StyleSheets.
21. **STAR-021 · Multi-device visual regression**: capture desktop/tablet/phone scenarios and verify text/icon bounding rectangles.
22. **STAR-022 · R6/R15 rig inspector**: inspect joints and attachment transforms; never silently change required rig type.
23. **STAR-023 · Editable animation authoring adapter**: output actual clips and verify playback in Studio.
24. **STAR-024 · Motion telemetry and visual checker**: detect prop grip drift, loop snapping, foot sliding and mistimed markers.
25. **STAR-025 · Blender+Importer pipeline**: validate axis/scale, rig and PBR import, collision and provenance.
26. **STAR-026 · Procedural building library**: safe generator modules for staircase, door, bridge, rails and reusable kits.
27. **STAR-027 · Performance budget profiler**: low-end device baseline, draw calls, triangle/instance/memory and stream behavior.
28. **STAR-028 · GitHub CI and local Studio attestation**: keep PR runner read-only; attach trusted Studio results separately.
29. **STAR-029 · Self-builder behavior checks**: reject syntactically valid broken skills before draft PR or promotion.
30. **STAR-030 · Branch conflict detection**: compare base SHAs before applying model edits; reconcile manual changes.

## P2 — frontier research

31. **STAR-031 · Grounded structural-visual comparison experiment**: test screenshot-only vs screenshot + native metadata.
32. **STAR-032 · Adversarial verifier experiment**: collect new confirmed bugs on frozen code candidates.
33. **STAR-033 · Experience-summarization search**: compare raw traces vs structured hypotheses/progress/failure summaries.
34. **STAR-034 · GEPA-style policy evolution**: optimize one prompt on dev fixtures, publish negative and positive holdout results.
35. **STAR-035 · Test-time candidate selector**: matched samples, quality/cost frontier and independent acceptance.
36. **STAR-036 · Concurrency scaling experiment**: compare 1/2/3 workers against GPU-budget-controlled baseline.
37. **STAR-037 · Cross-project memory isolation experiment**: synthetic conflicting design decisions, no leakage.
38. **STAR-038 · Small-model tool schema adapter**: compare native MCP vs typed concise wrappers for tool hallucinations.
39. **STAR-039 · LoRA feasibility pilot**: measure 8 GB GPU capability, provenance, loss curves, and blind eval; no premature deployment.
40. **STAR-040 · STAR vs general-assistant controlled Roblox benchmark**: same fixtures/tools, transparent costs and replicated trials.

## Prioritization policy

Complete P0 first. Do not skip from “basic tool works” to “self-training AGI” without verified fixtures, trusted execution and safe rollback. P1/2 can be researched in parallel, but release depends on independently observed evidence.
