# Roblox cutscenes and facial expressions: research notes (2026-10-14)

Goal: STAR can author and verify short in-game cinematics (camera flying through a scene while action plays) and
facial expression animation on R15 Dynamic Heads. The owner's two reference videos ("Cutscene Test | Roblox",
"Expression Test (Roblox Animation)") were known only by their titles, so the techniques below come from the
official documentation, DevForum practice and STAR's own Studio measurements, not from the videos.

What was built: the opt-in skill pack `star/skill_packs/roblox-cutscenes/` (SKILL.md, references/sources.md, eight
`--!strict` Luau modules) and `star/roblox_cutscene_studio.py` (validator, craft check, Luau renderer, Studio lab,
evidence parser, frame alignment, critique, CLI). Evidence of the real Studio runs is in
`docs/agents/roblox-cutscenes-20261014/` in the STAR workspace (not in this repository).

## 1. Camera scripting
- The client owns its camera: `workspace.CurrentCamera`, `CameraType = Scriptable` turns off the default camera
  scripts; `CFrame` places it; `Focus` should be set every frame for a Scriptable camera; `FieldOfView` 1..120, default
  70 ([Camera guide](https://create.roblox.com/docs/workspace/camera)).
- Two ways to move it: tweens (`TweenService:Create(camera, info, {CFrame = ...})`) or per-frame sampling. STAR uses
  per-frame sampling at `RenderPriority.Camera + 1` ([RunService](https://create.roblox.com/docs/reference/engine/classes/RunService)):
  multi-point paths, a look target that tracks a moving actor, and a skip that never has to fight a running tween.
  Easing still comes from the tween curves through `TweenService:GetValue`
  ([TweenService](https://create.roblox.com/docs/reference/engine/classes/TweenService)).
- Paths: Catmull-Rom (passes through every point, mirrored end tangents), Bezier (De Casteljau, points are control
  points), linear. A 48-sample arc-length table makes the speed depend only on the easing curve.
- Depth of field: `DepthOfFieldEffect` under the camera with FocusDistance updated to the subject's head every frame
  ([post-processing](https://create.roblox.com/docs/environment/post-processing-effects)).
- Letterbox: two black frames in a ScreenGui with `IgnoreGuiInset`, tweened in at the start and out before the end.

## 2. Timeline design
- Shots back to back (validator: no gaps, they tile the length), cues sorted by time, all in local space relative to
  an origin CFrame the server passes, so one timeline plays anywhere.
- Craft rules the checker enforces (STAR's working rules, measured in the lab): shots >= 1.2 s, FOV change < 25
  degrees per shot, camera < ~25 studs/s, Sine/Quad InOut for moves, captions on screen >= len/15 + 0.8 s, walk
  4-10 studs/s, expression changes inside a shot that looks at that face, bars in at the start and out before the end,
  skippable, <= 20 s.
- Skip and hand-back: DevForum threads show the classic bug: the camera is set back to Custom while a tween still
  writes it ([skip button](https://devforum.roblox.com/t/cutscene-skip-button/911078),
  [skipping](https://devforum.roblox.com/t/implementing-cutscene-skipping/924709)). STAR's player unbinds its render
  step, puts walkers at their destination, restores CameraType Custom, CameraSubject the Humanoid, the old FOV,
  controls (`PlayerModule:GetControls()`), CoreGui and hidden ScreenGuis, then destroys bars and actors.

## 3. Characters
- Actors are client-local clones of a server-built template (`Players:CreateHumanoidModelFromDescriptionAsync`; the
  non-Async method is deprecated per the API lookup). The default Animate LocalScript does not run on such NPCs
  ([DevForum](https://devforum.roblox.com/t/2579192)), so the player drives idle/walk tracks itself; the walk track's
  speed follows a trapezoid speed profile so feet do not slide.
- Gestures in code: KeyframeSequence -> Keyframe -> nested Pose; `KeyframeSequenceProvider:RegisterKeyframeSequence`
  gives a Studio-only id ([reference](https://create.roblox.com/docs/reference/engine/classes/KeyframeSequenceProvider));
  live games need an uploaded id, so the player falls back to the default emotes.
- Measured in STAR Test Place: these rigs use AnimationConstraint joints (not Motor6D).

## 4. Facial expressions (Dynamic Heads)
- `FaceControls` (child of the head MeshPart) has 50 FACS properties, each 0..1, not replicated
  ([FaceControls](https://create.roblox.com/docs/reference/engine/classes/FaceControls),
  [dynamic heads in Studio](https://create.roblox.com/docs/art/avatar/facial-animation/using-heads-in-studio)).
- ExpressionPlayer: presets (neutral, happy, angry, surprised, sad) as FACS tables, eased blends (Cubic Out), overlays
  for blink and talk (jaw syllables at ~9/s with varying peaks), the union of used properties written every frame on
  the client. Fallback for heads without FaceControls: a SurfaceGui face driven by the same values.
- Measured: the default HumanoidDescription head and the free "Dylan Default" head (10687288296) both had FaceControls
  in STAR Test Place; values written by the LocalScript read back exactly (surprised JawDrop 0.55, happy lip corner
  puller 0.85).

## 5. Verification method
Slow-motion playtest (speed 0.35) through the real server -> client path, `screen_capture` frames, and engine-side
samples printed by the lab client every 0.25 s of cutscene time: subject head position and size on screen, FOV, FACS
values, playing tracks, joint transform. Frame times are aligned to the shot cuts (the PC clock lagged ~0.3 s). The
critique checks framing per shot, expressions on camera with the preset reached, cuts only at boundaries, easing,
bars in/out, the VFX cue, and that control came back.

## Limits
- The reference videos themselves were not watched (titles only).
- Critique is metric and advisory; taste was judged by looking at the sheets (Claude), not by a vision model.
- KeyframeSequence gestures are Studio-only ids; the SurfaceGui fallback face was only shown on a dynamic head with
  `face=gui` forced (it overlaps the head's own face there); no classic-decal head was available to show it cleanly.
- Standalone luau-analyze (knowledge service) cannot resolve cross-module requires or Roblox types; the real checks
  are STAR's luau_lint, Studio `require` and the playtest.
