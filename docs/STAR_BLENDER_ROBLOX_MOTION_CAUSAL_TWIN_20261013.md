# STAR Motion Forge: Blender -> Roblox Animation and Causal Visual Intelligence

Research checkpoint: October 13, 2026. Branch: star/chatgpt-blender-roblox-motion-20261013. Status: engineering draft, not released. Actual Blender FBX export and Roblox Studio import are **not** validated by GitHub's offline fake tests.

## Why this matters

Blender is a **real animation production tool**, not just a mesh exporter. STAR should author and inspect rigs, pose actions, IK/FK transitions, motion curves and baked clips in Blender; Roblox Studio remains the final arbiter for animation import, gameplay, character replication, mobile performance and visual art direction.

R6 rigid Motor6D and standard R15 skinned/segmented rigs require different pipelines. Never substitute a renamed R15 skeleton for Roblox R6 joint offsets. An exported FBX by itself does not prove correct rig binding, avatar compatibility, beautiful motion, or a working Roblox AnimationClip.

## What's actually added in this draft

- **blender_animation.py**: pure, bounded R15/R6 action recipe schema, verified joint-name families, exact frame coverage, finite rotations, in-place roots, closing loop poses, angular-rate warnings and Studio import checklist. R6 is validation only.
- **blender_animation_worker.py**: fixed and trusted bpy worker. It creates a standard-name R15-shaped **bone-only proxy**, keys one limited Blender action, and writes editable scene.blend plus experimental animation.fbx. It does NOT create real R15 body meshes, skin weights, mouth poses or actual Roblox avatar animation.
- **blender_bridge.py**: immutable project-private jobs, file checks, 180-second child-process time limit, stripped secrets, operator CLI checks, distinct R15 animation inspection path. No arbitrary file, addon, script, shell or URL.
- **blender_mcp.py**: star_blender_animation_preflight read-only tool; the optional star_blender_animation_export_r15_draft only appears with BOTH the existing Blender scene-edit switch and STAR_BLENDER_R15_ANIMATION_EXPERIMENT=on. Off by default.
- **Windows packaging** includes the fixed worker file; GitHub offline tests and one reproducible wave recipe in examples/blender/.
- The existing STAR Blender scene constructor, VFX compiler, first-party MCP guard and other permissions remain unchanged.

## Exact official Blender-to-Studio production workflow

1. **Choose actual target**. Use a Roblox Studio R15 Rig Builder or user-authorized, compatible R15 skinned avatar. Record R15 bone names and hierarchy, bind/rest pose and ownership. R6 should use a real Studio R6 rig with its correct Motor6D joints and C0/C1 mapping. Those are not generic interchangeable armatures.
2. **Match bone architecture**. Standard humanoid Blender rig names from Roblox official avatar specifications: Root -> HumanoidRootNode -> LowerTorso -> UpperTorso -> Head, upper arms/lower arms/hands, upper legs/lower legs/feet. Body rig requirements include frozen bone transforms, identity bind scale, Root 0,0,0 and at most 4 skin influences per vertex, with no root influence. Extra Rigify controls must be baked onto proper export/deform bones.
3. **Animate thoughtfully**. Use Blender Pose Mode, Dope Sheet, Action Editor, Graph Editor and NLA for blockout, anticipation, arcs, IK foot locking, grip/pole vector and pose transitions. Bake constraint/IK evaluation to the bones Roblox will actually recognize. Separate authored clips and inspect constant speed, foot contact, hands/weapon attachment, loop first and last position/velocity, interpolation overshoot and root motion. Don't claim a still frame proves a good animation.
4. **Prepare FBX**. Save .blend master, select correct rig and required skinned meshes, set FBX Unit Scale and axes for Roblox import, disable Add Leaf Bones, enable Bake Animation, disable NLA Strips and All Actions when exporting a single clip, disable Force Start/End Keyframes if the official character tutorial indicates it, set Simplify to 0 and ensure frame range includes all motion. Scaling differs between Blender and Roblox; inspect Studio import orientation and size.
5. **Import in Studio**. Avatar tab -> Clip Editor/Animation Editor -> Import from File or From FBX Animation -> select the correct file, review Imported Rig root pose option for standard avatar clips, check importer warnings and all tracks. CurveAnimation conversion is required for some avatar/emote pipelines and may be irreversible. Do not publish or create asset IDs without the owner.
6. **Run actual character**. Use a correct Animator under Humanoid or AnimationController, load using Animator:LoadAnimation, test priority/blend weights, timing/loop, marker events, equip socket and server/client replication. Owner-owned NPCs generally require server animation activation for replication; character-owned playback rules differ. Validate in actual test place, with motion and graphics-quality footage.
7. **R6 warning**. R6's rigid Motor6D part/joint representation is NOT the R15 skin/bone representation. A proper Blender R6 rig exporter/importer with Motor6D remapping must be tested separately. STAR's first draft does not export or retarget R6.
8. **Plugin warning**. Roblox's official open-source Roblox Blender plugin demonstrates Open Cloud asset upload but is not established as a universal animation publisher; its v1.0.3 notes explicitly describe animation upload endpoint limitations at the time. Prefer Studio-imported FBX and verified rights over inventing a plugin capability.

Official sources:
- https://create.roblox.com/docs/art/blender
- https://create.roblox.com/docs/art/modeling/specifications
- https://create.roblox.com/docs/avatar/character-bodies/specifications
- https://create.roblox.com/docs/art/modeling/rig-a-humanoid-model
- https://create.roblox.com/docs/art/modeling/skin-a-humanoid-model
- https://create.roblox.com/docs/art/modeling/export-requirements
- https://create.roblox.com/docs/avatar/emotes/export
- https://create.roblox.com/docs/avatar/animation-packs
- https://create.roblox.com/docs/studio/importer
- https://create.roblox.com/docs/reference/engine/classes/Animator
- https://create.roblox.com/docs/reference/engine/classes/Animation
- https://github.com/Roblox/roblox-blender-plugin/releases
- https://docs.blender.org/api/dev/bpy.ops.export_scene.html

## Professional art-direction / visual-design system to build next

**Reference intake**: Owner image/video and high-level "do not use" constraints become a versioned Visual Brief: allowed style, silhouette, color/material, roughness, light mood, rig family, camera, animation intention, timing, priority, VFX layer hierarchy, platform budgets and source rights. Preserve rejections and exact corrections. Never promote a model's screenshot guess over a user's explicit feedback.

**Characters**: Require authentic R6/R15 or original, legally sourced skinned models; aligned attachment sockets, anatomy/proportions, topology and UVs, weights normalized, materials consistently shaded. Flat primitive cubes do not replace actual character meshes.

**Motion**: Analyze joint-angle/velocity curves, pose silhouettes at 8+ timepoints, root transforms, contact/foot sliding, looping phase transitions, hand grips, priority crossfade and animation markers. Differentiate Blender preview from actual Roblox Humanoid, client/server replication and game input state.

**VFX**: Blender can design an effect or render transparent spritesheet/flipbook textures, but Blender Geometry Nodes, particles and shaders are NOT automatically native Roblox effects. Build final ParticleEmitter, Trail, Beam, Attachment, SurfaceAppearance and scripted emission behavior in Studio. Validate mobile alpha overdraw, screenshot/UI occlusion, dynamic readability, lifetime/density limits and actual frame budget on target devices. Contrast against the user's visual reference at *matching camera, exposure, time and quality*.

**UI**: Implement editable native ScreenGui/GuiObject hierarchy with consistent typography, spacing, padding, clipping prevention, hit targets, contrast, reduced motion and phone/tablet/desktop screenshots, rather than displaying a design-reference PNG as a fake usable interface.

**Evidence**: Record source and candidate hashes, true rig identity, exported exact Blender/FBX versions, scene properties, native Studio import warnings, multi-camera motion screenshots/short clips and owner acceptance. A model can explain differences but not certify aesthetics without independent review.

Existing STAR references: docs/STAR_VISUAL_CRAFT_RESEARCH_2026.md; star/environment_craft.py; star/roblox_vfx_compiler.py; Studio Lab PRs #268/#277; owner Discord image-feedback draft PR #287.

## NEW IDEA: STAR Causal Motion Twin (SCMT)

**This is an original engineering hypothesis, not a verified groundbreaking scientific discovery.**

Today, typical image-to-edit agents guess many variables simultaneously and may claim that changing overall lighting makes an animation "correct". SCMT proposes an **editable causal graph** of all visual/game variables: source rig and named bone hierarchy, animation tracks and joint constraints, hand/foot contact intervals, VFX parameters, material/lighting state, camera, UI geometry, asset budgets and time-synchronized rendered screenshots.

When the owner says "it looks floaty" or "the lightning VFX blocks the screen", STAR does not blindly regenerate everything. It:

1. Checks which real editable variables could produce that specific mismatch, using the fixed Visual Brief and native scene inspector.
2. Runs **paired causal interventions** (one scoped edit at a time). Examples: earlier foot contact IK vs shoulder easing; lower ParticleEmitter emission vs lower bloom; move a UI panel vs reduce icon size.
3. Screens cheap invalid variations by rigid rig constraints, static keyframe schema, joint range, exact source license and native UI dimensions.
4. Renders top candidates at the SAME cameras/time and, if authorized, runs the same native Studio playback/test case. Records which variable changed.
5. Evaluates multiple objective signals: silhouette alignment, contact slide, phase/event synchronization, frame time, mobile occlusion, build/import validation; owner pairwise "better/worse" preference remains a separate input.
6. Learns which **types of evidence-backed repairs** satisfy this owner at a bounded CPU/GPU budget. It may update a reviewed preference/repair recipe, NOT foundation weights, permissions, published games or protected test oracles automatically.
7. Returns the most promising editable result with exact before/after images/video and a repair explanation. If results still do not meet owner standards, explicitly keep status rejected/unknown.

### Scientific test, rather than a slogan

Collect 20 owner-rights-cleared reference/build tasks. Compare STAR baseline vs ordinary vision critique vs SCMT at equal compute and model budgets. Split by task family and use blind, independent owner preference judgments. Metrics: time to accepted playable animation, native-import rate, bone-name mapping coverage, mean foot-slip/contact error, joint jerk, VFX mobile overdraw, screenshot grounding error, hardware cost and human approval. Randomize order and pin rigs/cameras/screenshots; report confidence and failures. No claims of new science unless better than strong baselines and independently repeated.

A specific experiment could distinguish a stiff idle animation caused by inappropriate elbow anticipation from a mismatched rig bind pose. The first needs better timing, while the second requires repairing the source rig; a generic image generator often conflates them. Similarly, a light burst hiding the HUD might be fixed by shortening lifetime, not by darkening the entire game.

### Research that motivates, but does not provide, SCMT

- UniRig (SIGGRAPH 2025) predicts skeleton hierarchy and skin weights for diverse meshes. Source states at least 8GB CUDA VRAM, not guaranteed fit alongside STAR's loaded model or compatibility with Roblox R6/R15: https://github.com/VAST-AI-Research/UniRig
- RigAnything (2025) proposes template-free autoregressive rigging and skinning, not native Roblox engine adoption: https://arxiv.org/abs/2502.09615
- RigMo (2026) jointly models rig/motion from deforming mesh sequences, promising representation research, not a deployed STAR integration: https://arxiv.org/abs/2601.06378
- Puppeteer (2025) combines automatic skeleton/skin and differentiable animation optimization; distinct native rig/foot-contact validation still required: https://arxiv.org/abs/2508.10898
- Roblox native animation architecture + Studio MCP: https://create.roblox.com/docs/animation and https://create.roblox.com/docs/studio/mcp

## Manual activation and acceptance

For read-only preflight with a STAR source checkout and approved settings file:

    python -m star.blender_bridge --settings PATH_TO_STAR_SETTINGS_JSON --preflight-animation examples/blender/roblox_r15_wave_animation.json

For experimental Blender file export, operator must separately enable Blender and Blender scene creation in STAR Settings and supply this EXACT local environment flag:

    STAR_BLENDER_R15_ANIMATION_EXPERIMENT=on

Then:

    python -m star.blender_bridge --settings PATH_TO_STAR_SETTINGS_JSON --animation examples/blender/roblox_r15_wave_animation.json

The job writes an immutable project-private scene.blend and animation.fbx. It does **not** upload or automatically apply to Studio. Test .blend reopening, FBX reimport/bone/action count, real Studio clip import on the correct trusted R15 rig, pose/scale/hand/foot alignment, animation playback, network replication, mobile visual and owner approval. Record version/hash/screenshot and reject unverified behaviors.

Acceptance stages:
- Stage 0: Github Python & Windows offline regressions, pure rig validation, exact owner gating, fixed worker and deterministic fake process. Does NOT prove Blender output.
- Stage 1: real installed Blender 4.x/5.x native load/export and animation frame checks. Verify source vs FBX bone hierarchy; no external file import.
- Stage 2: actual authorized Studio R15 target import via Clip Editor, motion/playback, multi-frame screenshots and replication. Only then claim support for any specific animation target.
- Stage 3: real meshes, Rigify bake, sampled animation control, facial poses, VFX/flipbook sync, cross-device production acceptance. R6 adapter separately scoped and tested.

Security: no model-authored Python, no arbitrary addons, no HTTP listeners, no Roblox asset publishing, no automatic source file downloading, no overruling source rights or user aesthetic rejection. Experimental exporter stays off by default.

**Definition of success**: more Studio-accepted, owner-approved, editable Blender-authored animations per engineer-hour while keeping model/chat latency, rights and security intact.
