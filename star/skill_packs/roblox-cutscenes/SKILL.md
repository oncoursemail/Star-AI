---
name: roblox-cutscenes
description: Roblox cutscenes and facial expressions - a data timeline of camera shots (Catmull-Rom/Bezier paths, arc-length speed, TweenService easing, FOV, depth of field, letterbox) and cues (actors walk, gestures, FaceControls expressions, blinks, talking, captions, VFX composer cues), a skip button that returns control, and a server-triggers / client-plays structure, with typed Luau modules in luau/.
---
# Cutscenes and facial expressions

A cutscene is DATA: shots back to back plus timed cues, in the cutscene's own local space (positions relative to an origin CFrame the server passes), so one timeline plays anywhere. Ready modules in luau/: CutsceneTypes (types + validate), CameraPath, ExpressionPlayer, ActorMotion, CutsceneUi, CutscenePlayer, CutsceneClient (ReplicatedStorage) and CutsceneService (ServerScriptService).

## Structure (server triggers, client plays)
- Server: CutsceneService.play(player, name, origin) from gameplay (zone, quest step, boss intro). Allow list with cooldowns, one open cutscene per player, a deadline (length + grace) closes it if the client never answers, optional freeze (WalkSpeed/JumpHeight 0, restored after). The remote carries only ("play", name, origin, token); the client may only answer ("finished", token, state), type-checked, token-matched, rate limited.
- Client: plays only timelines it registered itself (never sent over the network) and checks every received value. Camera, UI, expressions and actors are local; FaceControls properties are not replicated, so faces are animated on each client.
- Actors are client-local clones of a template the server built (Players:CreateHumanoidModelFromDescriptionAsync is server-only) in ReplicatedStorage; root anchored, moved by CFrame, no physics or network ownership. Strip scripts from the clone.

## Camera
- Each frame: CameraType Scriptable, set CFrame, FieldOfView and Focus. Bind at RenderPriority.Camera + 1 (after the default camera scripts); a shake bound at Camera + 2 then shakes the cutscene view without accumulating.
- Paths: Catmull-Rom passes through every point (flythroughs); Bezier treats points as control points (one smooth sweep). Re-parameterise by arc length so speed comes from the easing curve, not point spacing. Ease with TweenService:GetValue (Sine/Quad InOut for moves; Linear starts and stops abruptly).
- Interpolate look target, FOV and roll with the same eased alpha. Track a moving actor with a look target on the head plus an offset (lead room in the direction of travel, look room toward what they look at: put the face on a third).
- DepthOfFieldEffect under the camera: FocusDistance = distance to the subject's head every frame, InFocusRadius 4-6, FarIntensity 0.4-0.5 for close-ups only.
- Keep near geometry out of shot: a bright part 2 studs from the lens fills half the frame. Check where the sun is for the shot's direction.

## Shots and timing
- Establishing (wide, moving) -> medium close-up reaction -> over-the-shoulder on the object -> close-up -> pull-back. Shots of 1.2 s or more; FOV change under 25 degrees within a shot (dolly instead of zooming); camera speed under about 25 studs/s.
- Expression changes must happen in a shot that looks at that face (head at least 4% of the frame height; close-ups 20-27%).
- Letterbox bars (two black frames, IgnoreGuiInset) slide in at the start and out before the end: they tell the player control is taken and given back.
- Captions: about 15 characters per second of reading plus 0.8 s; type them on at about 40 characters/s; speaker line above.
- Skip: a 44 px tall button plus a key/gamepad action (ContextActionService). Skip puts actors in their end state, then restores: CameraType Custom, CameraSubject the Humanoid, the old FOV, controls (PlayerModule:GetControls():Enable()), hidden CoreGui and ScreenGuis, destroys bars and actors. Cancel running tweens before restoring (a tween still writing the camera undoes the restore).

## Characters
- Walks: trapezoid speed profile (short acceleration, cruise, short stop); the walk track's speed follows the real speed (default walk cycle authored for 16 studs/s), so feet do not slide. 4-10 studs/s reads as walking.
- Gestures in code: KeyframeSequence -> Keyframe -> Pose nested like the rig (HumanoidRootPart > LowerTorso > UpperTorso > arms/head). KeyframeSequenceProvider:RegisterKeyframeSequence gives a temporary id that works only in Studio; a live game plays an uploaded animation id (fallback: the default emotes wave/point/cheer). Rigs from a HumanoidDescription may use AnimationConstraint joints instead of Motor6D.

## Facial expressions (FaceControls)
- A Dynamic Head is a head MeshPart with a FaceControls child: 50 FACS properties, each 0..1. An expression is a set of values; animate by blending from the current values to the target (ease out, 0.15-0.4 s) and write the union of every property you use each frame.
- Presets: happy = lip corner pullers 0.85, cheek raisers 0.6, eyes closed 0.2, dimplers 0.3; angry = brow lowerers 0.9, Corrugator 0.7, nose wrinklers 0.4, LipPresser 0.6; surprised = inner/outer brow raisers 0.9, upper lid raisers 0.85, JawDrop 0.55, Funneler 0.25; sad = inner brow raisers 0.8, lip corner down 0.75, ChinRaiser 0.4, EyesLookDown 0.3.
- Overlays on top of the expression: blink (eyes closed 0 -> 1 -> 0 in about 0.22 s, every 2-5 s), talk (JawDrop syllables at about 9 per second with varying peaks, rounder lips on some).
- No FaceControls (classic head): fall back to a SurfaceGui face (eyes, brows, mouth) driven by the same values and hide the face decal while it is on.

## VFX cues
A vfx cue names an ability and a style of the VFX composer (roblox-vfx-composer) and plays it locally with the cutscene's speed; leave the burst 15-25 studs from the camera so its layers read instead of filling the frame.

## Reviewing
Capture frames in slow motion across the whole timeline and print engine-side samples (subject head position and size on screen, FOV, FACS values, playing tracks). Check framing per shot, expressions on camera, cuts only at shot boundaries, easing (slow at the ends of a moving shot), bars in and out, and that control returns.
