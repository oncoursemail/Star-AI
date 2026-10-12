# STAR Roblox Craft Intelligence: Luau, UI, VFX, Animation

Research date: 2026-10-11. Change status: isolated draft-PR candidate
from star/next, replacing #101 with review fixes. Not merged, not deployed,
and not a verified live Studio build.

## Scope and existing architecture

STAR is a local-first Roblox developer assistant, not a foundation model that
has learned every engine detail. It already has official Roblox Creator Docs
retrieval, indexed Luau static checking when configured, Studio MCP integration,
guarded workspace/source editing, a build/test pipeline, and task-scoped skill
packs. See star/studio.py, star/studio_loop.py, star/doc_knowledge.py,
star/roblox_place.py, star/roblox_pipeline.py, star/agent_skills.py,
star/skill_packs/, and docs/STAR_VISUAL_CRAFT_RESEARCH_2026.md.

This change deliberately adds narrow, reviewable functionality instead of
granting broad engine execution rights. It implements two read-only tools:
star_roblox_craft_audit and star_roblox_craft_recipe in star/roblox_craft.py,
exposed through star/intelligence.py only for relevant Roblox development
prompts. Neither tool calls Roblox, imports assets, runs Luau, edits Studio,
downloads binaries, publishes games, changes permissions or trains a model.

Both tools are on with **Roblox research**, which is enabled by default;
turning Roblox research off removes both tools and refuses their calls.
Even when research is on, their schemas are offered only for a Roblox
context plus a whole craft word: ui, gui, hud, vfx, particle(s), animation(s),
tween(s), rig(s), or audit (case-insensitive). Generic Roblox requests using
only code, build, create, review, script(s), effect(s), scripting,
interface(s), or inspect do not offer these schemas. This keeps the larger
craft schemas out of ordinary small-model requests. Their presence in the
complete built-in catalogue does not make them always-on tools.

## New tools and data contracts

### star_roblox_craft_audit

Pass a bounded summary acquired from authorized Studio reads:
search_game_tree, inspect_instance, and script_read. The analyzer accepts at
most 160 instances, 12 Luau scripts (20,000 characters each), and 120,000
UTF-8 bytes of combined JSON. It returns object paths, severity, domain,
rule ID, evidence, human-readable recommendation, documentation link, and
certainty. A missing property stays unknown unless the caller can accurately
mark its properties as complete; sample completeness does not guarantee the
full DataModel was inspected.

Both `instances[].path` and `scripts[].path` describe a **dot-separated
Studio path, for example Workspace.Part.Emitter**. Include the relevant parent
record in the snapshot: parent checks use the prefix before the final dot.
Slash-separated paths are not a supported hierarchy representation for these
checks and must be converted by the snapshot producer, not inferred by the
audit. A missing parent record remains unknown, not proof of an invalid parent.

The tool statically identifies useful review targets:

- Luau: absence of a strict-mode annotation, suspicious DataStoreService
  use in LocalScript, possible legacy scheduling calls, possible unvalidated
  OnServerEvent boundaries, and legacy Humanoid animation loading.
- Native UI: ScreenGui with explicitly disabled insets, extremely large
  pixel-only UI size, text scaling without a sampled size constraint, and
  long text configured without wrapping.
- VFX: misplaced ParticleEmitter, missing Beam/Trail attachments, high
  configured particle rates, possible particle occupancy, and long trails.
- Animation: missing AnimationId and unusual Animator placement.

The legacy-scheduling rule targets bare wait/spawn/delay calls, not
`task.wait`, `task.spawn`, `task.delay`, member calls, or longer identifiers.
The strict-directive scan allows spaces and tabs before `--!strict` on a
single line; it does not repeatedly scan across newline-only prefixes.

These are static heuristics and explicit-property checks, NOT an AST security
audit, rendered UI inspector, running VFX profiler, or rig motion evaluator.
The 100 particles-per-second mobile rate heuristic and 300 potential-live-
particle occupancy heuristic are review triggers, NOT documented engine caps.

Example **synthetic** input, not a captured game:

    {
      "instances": [
        {"path":"StarterGui.HUD","class":"ScreenGui",
         "properties":{"ScreenInsets":"None"}},
        {"path":"StarterGui.HUD.Action","class":"TextButton",
         "properties":{"Size":{
           "xScale":0,"xOffset":640,"yScale":0,"yOffset":64}}},
        {"path":"Workspace.Effect.Sparks","class":"ParticleEmitter",
         "properties":{"Rate":130,"Lifetime":{"Min":0.2,"Max":0.5}}}
      ],
      "scripts": [
        {"path":"ServerScriptService.Combat","class":"Script",
         "source":"--!strict\n-- example, replace with actual script"}
      ],
      "target":"mobile"
    }

Output is read-only with snapshot_incomplete=true and executed=false.
The only honest way to confirm a fix is to capture and test real Studio
runtime evidence on an authorized project.

### star_roblox_craft_recipe

Select responsive-hud, impact-vfx, or animation-marker. STAR returns an
editable Luau source scaffold, expected path/script class, prerequisites,
documentation links and explicit preview_only=true, installed=false,
executed=false status.

This tool accepts only `kind`, not an input Studio path. Its returned
`source_path` is a slash-separated source-file layout ending in `.luau`,
not a hierarchy path to pass unchanged into an audit record.

responsive-hud is a native LocalScript that constructs a ScreenGui and a
compact anchored panel with UIListLayout, UIPadding, UISizeConstraint,
UITextLabel/TextButton equivalents (TextLabel and TextButton), a real
GuiButton.Activated action, TweenService hover color, and a reduced-motion
fallback. CoreUISafeInsets are used to protect interactive elements.

impact-vfx is a cosmetic ModuleScript that creates a temporary anchored
effect holder, Attachment, two ParticleEmitters (sparks and dust), shaped
NumberSequence transparency/size, explicit bursts and Debris cleanup. It
does not modify combat damage or set server authority.

animation-marker is a ModuleScript scaffold that receives a genuine Animator
and owner-provided Animation, loads an AnimationTrack with Action priority,
listens for a named Impact marker, and disposes of track/event connections.
It does not synthesize or upload skeletal keyframes, and cannot substitute
for a real R6/R15/custom skeleton or animation asset ownership.

Each recipe must be reviewed and applied through STAR's existing authorized
workspace or GuardedStudio edit gate. It is not an automation that places
objects into an arbitrary game.

## Luau depth: correctness, control and review

Luau code must respect where it runs. DataStore operations and trusted game
state belong on the server; client input is never proof of a hit or currency
change. Validate RemoteEvent payload types, ranges, player ownership,
frequency and game state in a server handler. Keep shared modules focused,
avoid cyclic require dependencies, and disconnect connections on teardown.

Use the Luau type checker, compiler and API schema lookup for actual
diagnostics. String-pattern hints can match comments, helper validators or
truncated source. Never report a heuristic as a confirmed vulnerability.
Where possible, write regression tests that fail before a change and pass
afterward. Monitor network replication, streaming and script cost rather than
guessing performance.

Official: https://create.roblox.com/docs/luau/type-checking
Official: https://create.roblox.com/docs/scripting/security/client-server-boundary
Luau source: https://github.com/luau-lang/luau

## UI depth: create editable interfaces, verify behavior

Treat a screenshot as a reference only, not as a functional Roblox interface.
Build native instances such as ScreenGui, Frame, TextLabel, TextButton,
UIListLayout, UIGridLayout, UIPadding, UIScale, UISizeConstraint, and
UITextSizeConstraint. Prefer deliberate design tokens, consistent typography,
alignment, constrained sizing and component patterns over hundreds of
arbitrary offsets. Account for Roblox core UI, notches and safe areas.

Test phone portrait and landscape, desktop widescreen, gamepad selection,
localized long text, dynamic text size, mouse/touch Activated events,
input focus and reduced-motion accessibility. Use GUI hierarchy and actual
rendered screenshots to verify clipping, text/icon collisions, wrong fonts
and spacing. Generated flat images do not prove native layout correctness.

Official: https://create.roblox.com/docs/ui/size-modifiers
Official: https://create.roblox.com/docs/ui/styling
Official: https://create.roblox.com/docs/production/publishing/accessibility
Official: https://create.roblox.com/docs/reference/engine/enums/ScreenInsets
Official: https://create.roblox.com/docs/reference/engine/classes/GuiButton

## VFX depth: timed, legible, efficient effects

A polished effect uses shot planning: anticipation, buildup, focal release,
impact, secondary debris, audio and dissipation. Prefer restrained, coherent
silhouettes, material colors, motion arcs and meaningful timing to random
glow spam. ParticleEmitter should be a child of a BasePart or Attachment.
A Beam or Trail requires distinct Attachment0/Attachment1 references.
Use ColorSequence, NumberSequence, ParticleEmitter:Emit for one-shots,
and Debris or explicit destruction for cleanup.

Real performance depends on transparency overdraw, viewport, device,
simultaneous players and effect stack, not one magic Rate threshold. Profile
frame time and memory on desktop and lower-end mobile with real Roblox tools.
Synchronize visual Impact cues to AnimationTrack event markers, while the
server remains authoritative over whether attacks hit.

Official: https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter
Official: https://create.roblox.com/docs/effects/beams
Official: https://create.roblox.com/docs/effects/trails
Official: https://create.roblox.com/docs/performance-optimization/microprofiler/use-microprofiler

## Animation depth: authentic rigs and authored keyframes

Determine whether the target is R6, R15, or a custom skinned rig before any
pose or attachment decision. Evaluate silhouettes, anticipation, action,
contact, follow-through, recovery and blend transitions. Import authored
animations through the Studio Animation Editor or a license-cleared DCC
workflow; map joints and bone hierarchies, preserve ownership, and inspect
the hand/prop alignment from front, side, three-quarter and movement cameras.

Animator:LoadAnimation, AnimationTrack priorities, blending/fade and named
marker signals are native runtime primitives. A clip ID is not evidence that
the rig moves correctly. Verify what replicates to other players, animation
cancellation, respawn behavior, marker timing and cleanup, including on
phones and multiplayer sessions. Damage should never be authorized solely
by an animation marker callback.

Official: https://create.roblox.com/docs/reference/engine/classes/Animator
Official: https://create.roblox.com/docs/animation/events
Official: https://create.roblox.com/docs/animation/editor

## Verification sequence

1. Inspect the actual owner-approved Studio DataModel using discovered,
   allowed read tools. Record selected place/session, paths and source spans.
2. Run the bounded static audit. Review errors as suggestions with evidence.
3. Query documentation and APIs for current signatures and deprecations,
   and run actual Luau lint/type analysis when the backend is configured.
4. Generate an editable minimal script or a native UI/VFX/animation plan.
   Do not treat the returned source as installed or complete.
5. Obtain owner authorization and apply via existing guarded edit tools.
   Preserve comparison against existing source and record the change journal.
6. Read edited source and Studio state back; capture real screenshots and
   console output, start an authorized disposable-place playtest.
7. Evaluate device responsiveness, gameplay correctness, rig alignment,
   timing, VFX readability, cleanup and profiler traces before marking done.

The existing built-in .rbxlx builder is script-only; building actual visual
assets requires Studio or an appropriately configured Rojo workflow and
licensed source files. Roblox asset IDs, third-party packages, and uploaded
animations need creator ownership/licensing review.

Offline regression coverage is in `tests/test_roblox_craft.py` and
`tests/test_agent_tool_catalogue.py`, including real `run_task` requests and
successful audit tool results for modern and bare scheduling calls. It also
covers narrow prompt gating, the research-off switch, preserved Open Cloud
dispatch, a 20,000-newline script, line-bounded strict matching, schema path
descriptions, and invalid versus valid dotted parents. The complete catalogue
includes craft tools without changing the ordered general-prompt expectations.
GitHub check runs are the verification source for this repair; see the draft
PR for exact commands and observed outcomes. Nothing was run locally during
the repair, and no live Studio or device verification is claimed.

## Engineering roadmap NOT implemented here

- Host-side read-only snapshot collector that maps the actual Studio MCP
  connector response schema into stable, provenance-preserving audit records.
- Official Luau AST, dependency graph, remote flows and API metadata index;
  verified diagnostics instead of approximate regular-expression flags.
- Screenshot-based UI diffing at measured device emulations with accessibility
  checks, actual text bounds, focus order and layout-tree inspection.
- Temporal vision analysis of owner-provided gameplay video with real
  frame timestamps and source citations; do not infer footage from metadata.
- Event-driven VFX graphs, authorized imported particle textures and profiler
  budgets; pre/post screenshots, asset/licence manifests, and cleanup tests.
- Rig-aware animation authoring/retargeting, genuine published asset and
  keyframe metadata, movement/multiplayer playtest, markers and SFX sync.
- Closed-loop guarded repair with owner consent, instance-safe undo, verifiable
  read-after-write, regression tests and measured device performance.

This patch adds inspectable tools and reusable source, **not** the full
end-to-end pipeline, a new trained model, a real Studio screenshot study,
or a promise to build arbitrary high-quality games without artist review.
