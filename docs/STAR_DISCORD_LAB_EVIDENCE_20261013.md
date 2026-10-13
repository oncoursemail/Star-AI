# STAR Discord Lab Evidence — owner-only progress and screenshots

Research checkpoint: October 13, 2026. This is a development-branch read-only feature, not remote screen sharing, automatic Brain 2 camera capture or proof of a live install.

## Owner commands

Use /star lab for the latest trusted producer-reported job and /star labshot for one explicitly requested viewport or Blender render. In an authorized owner DM, natural phrases such as "What are you working on in the test studio?" and "send screenshot from Brain 2" use the same local evidence reader rather than inventing an AI answer. Unauthorized Discord users receive no evidence, and slash results are ephemeral.

## Operator setup

In the machine running the Discord bot, update the local discord-settings.env:

    STAR_DISCORD_LAB_STATUS=1
    STAR_DISCORD_LAB_REPORT=/absolute/approved/folder/latest.json

Use an actual host-native absolute path. Default is OFF. Discord prompts cannot select files, remote hosts or processes.

## Receipt schema

Trusted Studio Lab or Blender producers stage an image and atomically replace latest.json in the host-configured folder:

    {
      "version": 1,
      "job_id": "studio-obby-17",
      "engine": "roblox-studio",
      "state": "running",
      "phase": "playtesting",
      "task": "Check the obstacle course jumps",
      "next_step": "Compare all four Studio camera angles",
      "checked": 3,
      "total": 8,
      "evidence": "native-studio",
      "updated_at": "2026-10-13T23:35:00Z",
      "capture_kind": "studio-viewport",
      "capture_file": "studio-frame.png",
      "capture_sha256": "ACTUAL_64_CHARACTER_LOWERCASE_SHA256_OF_IMAGE"
    }

The digest in the example is a placeholder and must be replaced by the real 64-character lowercase SHA-256. To omit the image, omit all three capture fields. The only accepted capture kinds are studio-viewport on the roblox-studio engine, and blender-render on the blender engine. Supported states: queued, running, paused, completed, failed. Supported phases: planning, building, rendering, playtesting, inspecting, verifying, learning, waiting. Evidence labels are producer declarations and NOT independent verification by Discord: native-studio, native-blender, static-only, simulated, not-tested.

Active reports older than 15 minutes become unknown, never falsely reported as currently running; even completed status includes the timestamp. User-facing progress is only a count reported by the trusted producer, not a verification performed by Discord.

Screenshot access is constrained to a same-directory basename: no user-supplied or model-generated filesystem path, no URL, no symlinks, no desktop-wide screenshot. STAR checks file size (max 6 MiB), hash, file signature and decoded image dimensions, then re-encodes a stripped-metadata JPEG to the explicitly requesting owner only. It refuses stale captures. An image hash proves the file matches the manifest, not that its source and content are authentic.

## Actual Brain 2 linkage still required

This feature reads a local report. It DOES NOT trigger captures, directly connect to Roblox Studio or reach Brain 2. After #268/#277 review, a trusted Studio Lab producer should generate viewport-only screenshot evidence through the official Studio MCP and stage its immutable build ID and hash. Blender should produce a fixed-camera preview via the already-reviewed first-party worker. If the bot host is on another machine, an operator-approved authenticated transfer stages only the two fixed files, image first and manifest last, with no arbitrary filesystem browsing. Never unattended-capture the full desktop or send credentials.

Official Roblox Studio Assistant documentation confirms viewport screenshots are available to third-party MCP clients: https://create.roblox.com/docs/assistant/guide . Blender still-render API: https://docs.blender.org/api/current/bpy.ops.render.html .

## Verified learning DMs already in STAR

Do not duplicate Night School notifier. The existing discord_bot/digest_task.py and learning_sender.py support owner-only opt-in, cooldown and deduplication based on verifiable counts; optional reviewed screenshots are supported by ApprovedVisual. Configure STAR_DISCORD_LEARNING_DM_OPT_IN=1 with a valid report source in local settings to receive evidence-backed updates, not a message for each untested model claim. Future integrations can add task-specific lesson names and Studio capture hashes, guarded by source authenticity and human review.

## Follow-up for visual image feedback

Add a reference-vs-result comparison command: two sanitized user-uploaded images -> private vision model -> observed mismatches and uncertainty -> owner corrections stored as unapproved candidates -> exact build/run iteration -> native Studio screenshot and objective validation -> review. Preserve negative constraints like no neon, no overlap, proper R6 rigs and correct effects placement. An image alone cannot establish motion quality: animation needs a timed series of frames and rig/track inspection. VFX needs emission rate, lifetime, overdraw and lower-end mobile tests.

Relevant source: star/environment_craft.py already provides palette/luminance/edge diagnostics, while Studio Lab #268 includes screenshot evidence and #277 adds device simulation. Do not claim visual fidelity from low-level pixel statistics alone.


## Reference-image review: implementation in this branch

The owner can use /compare with two attached PNG/JPEG/WebP images, or send
**two images in a one-to-one owner DM**, in the order desired reference then
STAR result. The bot validates dimensions and file signatures, removes metadata,
and sends both only to the configured **local or private LAN vision model**.
Public cloud vision cannot receive them through this command. The output
prioritizes observed mismatch and a concrete revision proposal; it does not
modify Roblox Studio, train weights, or permanently store screenshot pixels.
Temporary chat history retains only a short text record and both image-hash
prefixes to link follow-up corrections.

If private owner DM learning candidates are separately enabled, and the
immediately preceding exchange was an image discussion, messages such as
"I don't like that", "you messed up the animation", "that looks wrong" or
"the VFX is too big" become **pending** owner correction/regression candidates.
They are not applied, promoted to facts, or used for neural model training
without STAR Desktop review. Generic unrelated dislikes do not become training
data. Explicit "wrong: ..." retains the existing path regardless.

A single screenshot cannot establish moving animation quality, mesh topology,
network behavior, correct R6/R15 rigging or particle frame rate. For high
fidelity, the next native iteration should run this multi-evidence sequence:

1. Owner reference and negative style constraints -> persistent reviewed task
   brief with named layout parts, object types, desired camera/lighting and
   explicit non-goals.
2. Analyze reference at a usable resolution, then re-crop tiny labels/icons
   instead of extrapolating from downscaled images. Ground every identified UI
   element in actual Studio GuiObject geometry and devices, and 3D shapes in
   scene instance metadata + multiple matched camera angles. Do not guess object
   transforms from one screenshot.
3. Produce editable native geometry/materials, UI, ParticleEmitters, Beams,
   Trails and named animation tracks. Preserve real Roblox R6/R15 rigs,
   Motion/Animator semantics, hand attachment alignment, color/size sequences,
   animation-event markers and loop continuity. Blender previews are not
   Studio playable tests.
4. Capture edit-mode and play-mode viewport frames at fixed cameras; test
   phone/tablet/desktop visual layout, text clipping and touch targets; compare
   silhouette, edge grouping, contrast, alignment, palette, authored style,
   particle occlusion and alpha overdraw to owner reference. Pixel difference
   is one measurement, not proof of semantic fidelity.
5. Animation must be judged from a multi-frame sequence plus Motor6D/Bone/IK
   and Animator track data: pose continuity, foot sliding, weapon grip,
   event synchronization, priority transitions, replication and frame time.
   VFX must be verified at multiple graphics qualities and mobile particle
   density with occlusion/overdraw and lifetime budgets. Roblox's creator
   docs note emitter-rate ceilings of 400/s (100/s mobile) per emitter, not a
   recommended quality target. Measure actual scene performance.
6. Present concise before/after images and a diff checklist to the owner.
   Owner critique overrides AI's aesthetic opinions. Reject mismatched builds,
   repair one bounded issue at a time, keep immutable exact run/screenshot hashes,
   and only promote a lesson after independent native checks plus approval.

Research:
- Official Studio screenshot subagent via MCP: https://create.roblox.com/docs/assistant/guide
- Official ParticleEmitter guidance including mobile/overdraw:
  https://github.com/Roblox/creator-docs/blob/main/content/en-us/effects/particle-emitters.md
- Roblox animation editor, interpolation and loop continuity:
  https://create.roblox.com/docs/animation/editor
- Roblox animation graphs and state blending:
  https://create.roblox.com/docs/animation/graph-editor
- Roblox animation events:
  https://create.roblox.com/docs/animation
- Microsoft Research November 2025 UI grounding benchmark warns existing
  VLM benchmarks use unrealistically big controls; test the actual small
  icons and labels: https://www.microsoft.com/en-us/research/articles/ui-e2i-synth-realistic-and-challenging-ui-grounding-benchmark-for-computer-use-agents/

## Release and security gates

Require GitHub Ubuntu and Windows tests, owner-only authorization, disabled-path checks, stale/malformed/oversized/symlink/hash mismatch regression tests, live Discord interaction smoke, a real approved Roblox Studio test place capture, a Blender render, and host-to-host transfer QA before describing the feature as released. This PR does not activate the bot, install Blender, grant cloud rights, enable guild message reading or publish screenshots proactively.
