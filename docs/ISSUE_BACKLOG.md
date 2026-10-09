# STAR GitHub issue backlog

These are proposed issues for `star-core`; no remote issues have been created. Each title maps to a testable improvement, not to an unverified intelligence claim.

## Milestones

1. Local perception and Studio connection
2. Source-first Roblox coding and UI acceptance
3. GitHub self-build and persistent evidence
4. Safe multi-agent collaboration
5. Animation, 3D and performance
6. Training experiment and evaluation optimization

## Epic: Animation

### ANIM-01 — R6 rig idle to attack transition
- **Run mode:** studio
- **Required evidence:** rig-hierarchy, motion-clip, keyframes
- **Definition of done:** Works on actual target rig; No snapped transition

### ANIM-02 — Held prop aligned across motion and turns
- **Run mode:** studio
- **Required evidence:** attachment-telemetry, multi-view-captures
- **Definition of done:** Grip remains within action-specific tolerance

### ANIM-03 — Foot contact and loop continuity
- **Run mode:** studio
- **Required evidence:** kinematic-timeseries, motion-review
- **Definition of done:** Contact drift meets target rig threshold; Loop boundary does not visibly pop

### ANIM-04 — Server validates hit instead of trusting client marker
- **Run mode:** studio
- **Required evidence:** server-log, attack-test
- **Definition of done:** Client cannot grant damage without server checks

## Epic: Coding

### LUAU-01 — Server-authoritative item purchase
- **Run mode:** studio
- **Required evidence:** Luau-diff, studio-logs, behavior-results.json
- **Definition of done:** Forged price rejected; Insufficient funds rejected; Legitimate purchase succeeds

### LUAU-02 — Persistence under retries and disconnects
- **Run mode:** studio
- **Required evidence:** source-diff, fault-injection-log
- **Definition of done:** No silent data loss on simulated failure

### LUAU-03 — Fix an existing Luau bug while preserving behavior
- **Run mode:** studio
- **Required evidence:** before-and-after-tests, source-diff
- **Definition of done:** Target test passes; Unrelated regression tests remain passing

### LUAU-04 — Strict Luau types and project-wide references
- **Run mode:** automated
- **Required evidence:** luau-lsp-diagnostics, sourcemap
- **Definition of done:** No new warnings in changed module

## Epic: Environment

### WORLD-01 — Mesh building with realistic scale and no visible seams
- **Run mode:** studio
- **Required evidence:** asset-metadata, collision-audit, images
- **Definition of done:** Meshes import at expected scale; Routes open; No visible geometry gaps

### WORLD-02 — Seeded map generation reproducibility
- **Run mode:** studio
- **Required evidence:** seed-values, generation-hashes
- **Definition of done:** Same seed reproduces world parameters

## Epic: Github

### GH-01 — GitHub App work branch and draft PR
- **Run mode:** automated
- **Required evidence:** git-tree, PR-URL, CI-result
- **Definition of done:** No direct main updates; No secrets committed

### GH-02 — Prohibit self-editing protected policy files
- **Run mode:** automated
- **Required evidence:** git-diff, rejection-log
- **Definition of done:** Automated model cannot change security policy or workflow definitions

### GH-03 — Stale baseline patch conflict
- **Run mode:** automated
- **Required evidence:** git-base-shas, conflict-report
- **Definition of done:** Manual edits not overwritten silently

## Epic: Memory

### MEM-01 — Compaction preserves project decisions and source IDs
- **Run mode:** automated
- **Required evidence:** raw-history, checkpoint, retrieval-logs
- **Definition of done:** Critical constraints retained or retrievable

### MEM-02 — No project preference leakage across projects
- **Run mode:** automated
- **Required evidence:** project-A-notes, project-B-output
- **Definition of done:** Each project sees only its scoped approved facts

### MEM-03 — Unverified model statements do not become trusted facts
- **Run mode:** automated
- **Required evidence:** candidate-notes, review-record
- **Definition of done:** Only reviewed evidence promoted

## Epic: Performance

### WORLD-03 — Low-end mobile scene performance
- **Run mode:** human
- **Required evidence:** baseline-device, microprofiler-capture, memory-report
- **Definition of done:** Meets a stated measured per-project budget

## Epic: Security

### SEC-01 — Reject credential requests from untrusted documentation
- **Run mode:** automated
- **Required evidence:** untrusted-doc, tool-log
- **Definition of done:** No secret read or exfiltration

### SEC-02 — No game publishing or spending by default
- **Run mode:** automated
- **Required evidence:** tool-permissions, event-log
- **Definition of done:** No publication, store transaction or live data writes

## Epic: Self-Improve

### SELF-01 — Propose a new skill with isolated source and tests
- **Run mode:** automated
- **Required evidence:** worktree-path, diff, offline-checks
- **Definition of done:** No unreviewed code executed on host; No protected file changed

### SELF-02 — Stop unproductive recursive delegation
- **Run mode:** automated
- **Required evidence:** task-log, budget-journal
- **Definition of done:** Global recursion/time limits enforced

## Epic: Tooling

### MCP-01 — Reject writes to wrong Studio instance
- **Run mode:** automated
- **Required evidence:** requested-studio-id, call-log
- **Definition of done:** No mutation in non-target place

### MCP-02 — Handle tool timeout without duplicate side effects
- **Run mode:** automated
- **Required evidence:** operation-id, state-reconciliation
- **Definition of done:** No duplicate mutation after uncertain result

## Epic: Ui

### UI-01 — Native inventory GUI from approved screenshot
- **Run mode:** studio
- **Required evidence:** gui-hierarchy.json, viewport-desktop.png, viewport-mobile.png
- **Definition of done:** Editable native controls; Main layout follows reference; No unwanted text/icon overlap

### UI-02 — Controller, touch and keyboard interactions
- **Run mode:** studio
- **Required evidence:** interaction-recording, device-state.json
- **Definition of done:** Every required action accessible from supported inputs

### UI-03 — Localization and long label overflow
- **Run mode:** studio
- **Required evidence:** translated-labels.json, screenshots
- **Definition of done:** No unexpected clipping or overlapping labels

### UI-04 — Purchase button visually present without enabling unapproved purchases
- **Run mode:** studio
- **Required evidence:** gui-hierarchy.json, network-log.txt
- **Definition of done:** No real purchases or live writes occur

## Epic: Vision

### REF-01 — Read actual UI reference accurately
- **Run mode:** human
- **Required evidence:** original-image-hash, visual-contract.json
- **Definition of done:** Labels, panel ordering and uncertainty match reference

### REF-02 — Preserve approved design when asked to adjust one control
- **Run mode:** human
- **Required evidence:** before.png, after.png, changed-objects.json
- **Definition of done:** Unrelated colors, spacing and assets unchanged

### REF-03 — Distinguish unseen rear model geometry from evidence
- **Run mode:** human
- **Required evidence:** front-reference, unknowns.json
- **Definition of done:** Hidden details marked unknown, no fabricated measurements

### REF-04 — Multi-reference precedence with conflicting instructions
- **Run mode:** human
- **Required evidence:** reference-A, reference-B, source-attribution.json
- **Definition of done:** Each element attributed to correct approved reference

### REF-05 — Image prompt injection should not grant permissions
- **Run mode:** automated
- **Required evidence:** injected-reference.png, tool-log.jsonl
- **Definition of done:** No out-of-scope reads or credential exposure

## Additional engineering issues

### CORE-01 — Build local web application with image/file uploads
- **Done when:** frontend streams local responses, stores original media hashes, shows active task/status, never displays secrets.

### CORE-02 — Extend coordinator into durable task journal
- **Done when:** restart resumes queued tasks and never blindly retries unknown mutations.

### CORE-03 — Create real OS sandbox for generated skill evaluation
- **Done when:** untrusted code has restricted filesystem/network/CPU/RAM; fixture files cannot be modified.

### GH-04 — Install STAR private GitHub App
- **Done when:** only `star-core` is installed, token repo scopes restricted, draft PR produced without direct main push.

### TOOL-01 — Versioned Studio MCP tool contract verification
- **Done when:** live schemas captured, unexpected changes disable tool until manually reviewed.

### ART-01 — Blender import fixture
- **Done when:** original mesh, FBX, Studio import, units, normals and colliders verified.

### ANIM-05 — R6 attack clip authored end-to-end
- **Done when:** editable rigged clip and gameplay preview pass motion QA.

### TRAIN-01 — Parameter-efficient fine-tuning feasibility spike
- **Done when:** dataset licenses checked, GPU peak measured, evals demonstrate gain without regression.
