---
name: roblox-cutscenes
description: Roblox cutscenes and facial expressions - a data timeline of camera shots (Catmull-Rom/Bezier paths, arc-length speed, TweenService easing, FOV, handheld drift, depth of field with focus pulls, letterbox) and cues (actors walk, gestures, FaceControls expressions, blinks, talking, captions, accent-sized VFX composer cues), cinematic look presets (golden_hour, dusk, battle) with a rim light, a skip button that returns control, and a server-triggers / client-plays structure, with typed Luau modules in luau/.
---
# Cutscenes and facial expressions

A cutscene is DATA: shots back to back plus timed cues, in the cutscene's own local space (positions relative to an origin CFrame the server passes), so one timeline plays anywhere. Modules in luau/: CutsceneTypes (types + validate), CameraPath, ExpressionPlayer, ActorMotion, CutsceneLook, CutsceneUi, CutscenePlayer, CutsceneClient (ReplicatedStorage) and CutsceneService (ServerScriptService).

## Structure (server triggers, client plays)
- Server: CutsceneService.play(player, name, origin) from gameplay. Allow list with cooldowns, one open cutscene per player, a deadline closes it if the client never answers, optional freeze (WalkSpeed/JumpHeight 0, restored). The remote carries only ("play", name, origin, token); the client may only answer ("finished", token, state), type-checked, token-matched, rate limited.
- Client: plays only timelines it registered itself and checks every received value. Camera, UI, look, expressions and actors are local (FaceControls do not replicate).
- Actors: client-local clones of a server-built template (CreateHumanoidModelFromDescriptionAsync is server-only; CutsceneService.describe builds the HumanoidDescription from a Dynamic Head, eyebrows, hair and layered clothing ids). Root anchored, moved by CFrame; strip scripts.

## Cinematic defaults (always)
- Look: set timeline.look = golden_hour, dusk or battle (Atmosphere haze/glare, ColorCorrection grade, Bloom threshold above 1 so only emissives glow, a touch of SunRays; restored at the end). Midday default light reads flat. Low sun behind the subject (contre-jour) with a motivated key (the glowing object) looks best.
- Composition: keep every camera on one side of the action line (180-degree rule). Faces on a third (x 0.33/0.67) with look room toward what they look at, eyes at y 0.35-0.45; MCU head 22-27% of frame height, CU 30-34%. Solve lookOffset from the head height, do not guess.
- Motion: no static shots. Eased dolly push-ins (Sine/Quad), 1-2 studs over a shot; shot.handheld = 0.3-0.5 degrees on reaction shots.
- Close-ups: shot.rim = actor (warm kicker behind and beside the head), dof with radius 2.5-3; a focus pull (dof.pullFrom, pullAt, pullTime) racks from the background to the face; raise NearIntensity while the subject is near-field.
- Expressions: hold each one 1.2 s or more on a shot that looks at that face; check the face turns to the lens (head LookVector toward camera above 0.25).
- VFX: an accent, never the frame: CutsceneLook.ACCENTS (accent_pulse, accent_hit) or cue.scale 0.4-0.8, cue.screen at most 0.5 (flash, tint, bloom, shake share); place the effect 15-25 studs from the camera, in frame.

## Camera
- Each frame: CameraType Scriptable, set CFrame, FieldOfView and Focus at RenderPriority.Camera + 1 (a shake at Camera + 2 shakes the cutscene view without accumulating).
- Catmull-Rom passes through every point; Bezier treats points as control points. Re-parameterise by arc length so speed comes from the easing curve. Interpolate look target, FOV and roll with the same eased alpha. FOV change under 25 degrees in a shot (dolly instead); camera speed under about 25 studs/s; shots of 1.2 s or more.
- Keep near geometry and glowing props (lanterns, neon) out of the eye line behind a head.

## Shots, UI, skip
- Establishing (wide, moving) -> MCU reaction -> over-the-shoulder on the object -> CU -> pull-back. Fade in from black (hides the frame where layered clothing fits itself).
- Letterbox bars slide in at the start and out before the end. Captions: 15 characters/s plus 0.8 s, typed at 40 characters/s.
- Skip: 44 px button plus key/gamepad (ContextActionService). Skip puts actors in their end state, then restores camera (Custom, Humanoid subject, old FOV), controls (PlayerModule:GetControls():Enable()), CoreGui/ScreenGuis and the look, and destroys bars and actors. Cancel running tweens first (a tween still writing the camera undoes the restore).

## Characters
- Walks: trapezoid speed profile; the walk track's speed follows the real speed (default walk authored for 16 studs/s). Idle: the Animate script's main idle 507766388 (507766666 is its look-around variant: heads turn away in close-ups).
- Gestures: KeyframeSequence poses nested like the rig; RegisterKeyframeSequence ids work only in Studio (live games: uploaded ids or emotes). Rigs may use AnimationConstraint joints.
- Place actors on the measured ground (raycast), not an assumed height: terrain slabs can surface above their fill.

## Facial expressions (FaceControls)
- Dynamic Head = head MeshPart with FaceControls (50 FACS values 0..1). Blend to a preset (ease out 0.15-0.4 s); write the union of used properties each frame. Presets: happy (lip corner pullers 0.85, cheek raisers 0.6), angry (brow lowerers 0.9, Corrugator 0.7), surprised (brow raisers 0.9, upper lid raisers 0.85, JawDrop 0.55), sad (inner brow raisers 0.8, lip corner down 0.75).
- Overlays: blink (0.22 s every 2-5 s), talk (JawDrop syllables about 9/s). No FaceControls: SurfaceGui face driven by the same values.

## Reviewing
Capture slow-motion frames at high render quality (Automatic quality drops DOF, sun rays and bloom on weak GPUs) and print engine samples: head position/size/facing, FOV, FACS, tracks, ground height. Check thirds, eye line, expressions on camera, VFX coverage, blown highlights, cuts only at shot boundaries, easing, bars in/out, control returned.
