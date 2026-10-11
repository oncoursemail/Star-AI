# STAR Animation Direction — authored motion, rig fidelity and sync

Use when creating animations that must feel intentional rather than generic procedural motion, including combat, movement, stylized emotes, prop/tool motions, cinematics and creature animation.

## Animation is acting and mechanical contact, not random CFrame tweening

Before keyframing, record:
- Character identity: existing R6, R15, skinned character, mechanical object, or bespoke rig. Include joint/bone names, root/pivot, real proportions, attached prop, weapon grip, and target stance. Preserve the actual avatar design.
- Reference evidence: timestamps actually observed, animation intensity and art style, frame rate of footage if known, camera and movement direction, what can be inferred versus exactly seen.
- Intent: action verb (swing, dodge, recoil, open, land), gameplay startup/contact/recovery events, locomotion constraints, root motion and cancellation rules.
- Reference sheet: front, three-quarter, side contact silhouettes with line-of-action, center-of-mass arrow and planted foot position.

## Twelve traditional principles adapted to Roblox

Prioritize (1) staging (clear subject), (2) anticipation, (3) strong readable poses, (4) arcs, (5) spacing/easing, (6) follow-through and overlapping action, (7) secondary action that supports the primary, (8) timing, (9) exaggeration appropriate to style, (10) solidity and weight, (11) appeal/shape rhythm, and (12) intentional squash/stretch where rig/art direction supports it. These are craft heuristics; blindly applying all of them is not a scoring shortcut.

For a fast sword slash, the hand may lead, wrist lag, torso rotate, blade trace a coherent arc, and feet lock during contact. A combat clip often benefits from asymmetry and a short hold before acceleration. Do not independently oscillate every body part.

## Keyframe construction workflow

1. Choose rig and test existing default movement before editing.
2. Thumbnail 4–8 major poses: idle/anticipation/extreme/contact/follow-through/recover, not dozens of meaningless in-between poses.
3. Solve gravity and balance: line of action, planted foot, support leg, hip/shoulder counter-rotation; use references when physically plausible.
4. Work in the Roblox Animation Editor https://create.roblox.com/docs/animation/editor or animate in Blender then import using documented Studio 3D Importer workflows https://create.roblox.com/docs/studio/importer . Existing Blender rig controls do not automatically map to a Roblox skeleton.
5. Edit easing and tangents in Curve Editor https://create.roblox.com/docs/animation/curve-editor . **Caution:** switching quaternion animation to Euler curves can be destructive; verify rotation handling.
6. Select clip priorities and layers consciously. Use Animator:LoadAnimation; adjust weight and fade time as needed. AnimationTrack documentation https://create.roblox.com/docs/reference/engine/classes/AnimationTrack .
7. Where supported, explore the Animation Graph Editor https://create.roblox.com/docs/animation/graph-editor and state machines https://create.roblox.com/docs/animation/graph-editor-state-machine for complex locomotion and transition blending. Verify engine version rather than assuming the feature exists everywhere.
8. Add named markers for Release, Impact, FootLeft, FootRight and Recover in the editor, using https://create.roblox.com/docs/animation/events . Connect before playing and disconnect when done.
9. IKControl https://create.roblox.com/docs/reference/engine/classes/IKControl can support hand aiming, environment response or foot targeting; verify ChainRoot, EndEffector, Target, SmoothTime and blending. Do not force IK on authored actions if it harms silhouettes.
10. Capture and inspect: start, anticipation, contact, peak, recovery and loop seam, plus multiple view angles. Confirm tool alignment to the hand on the actual rig.

## Playback system responsibilities

Separate three concerns:
- The **server** decides whether a gameplay action is permitted and whether a hit is valid; a local visual marker is not authoritative proof of damage.
- The **animation controller** starts/stops/fades tracks, handles respawn/cancellation and makes timing intent explicit.
- The **presentation system** triggers local sounds, beams, particles and camera cues from validated state and marker timing.

Runtime API sample, for an EXISTING published animation ID and existing animator; do not invent the asset ID:

~~~luau
--!strict
local function playAttack(animator: Animator, animationId: string)
    assert(animationId:match("^rbxassetid://%d+$"), "Use a published animation asset ID")
    local clip = Instance.new("Animation")
    clip.AnimationId = animationId
    local track = animator:LoadAnimation(clip)
    track.Priority = Enum.AnimationPriority.Action
    track.Looped = false

    local connections = {}
    connections[#connections + 1] = track:GetMarkerReachedSignal("Impact"):Connect(function()
        -- A visual cue only; game damage must remain server-authoritative.
        print("Impact visual cue at authored keyframe")
    end)
    connections[#connections + 1] = track.Stopped:Connect(function()
        for _, connection in connections do connection:Disconnect() end
        clip:Destroy()
    end)
    track:Play(0.1, 1, 1)
    return track
end

return playAttack
~~~

This is a scoped illustration, not a whole production state machine. Cleanup on interruption, character destruction and player leaving must be handled in the actual controller; reusing tracks is better than reloading for every swing.

## Free learning motions and capture

- Roblox native Animation Editor https://create.roblox.com/docs/animation/editor and Curve Editor; inspect official motion events and IK.
- Blender https://www.blender.org/ plus Rigify documentation https://docs.blender.org/manual/en/latest/addons/rigging/rigify/ .
- Adobe Mixamo https://www.mixamo.com/ free bipedal humanoid rig/motion samples with Adobe account; Adobe FAQ https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html . **DO NOT** use its raw motion data to train AI models, and do not redistribute it as an animation pack; detailed explanation https://community.adobe.com/questions-696/mixamo-faq-licensing-royalties-ownership-eula-and-tos-589400 .
- Quaternius Universal Animation Library https://quaternius.itch.io/universal-animation-library — free name-your-price Standard archive with 120+ motions as advertised, individual pack advertises CC0, Roblox retargeting not automatic. Quaternius site-wide new QAL terms https://quaternius.com/license.html are different; check which terms govern the downloaded file.
- Roblox Animation Capture https://create.roblox.com/docs/animation/capture — facial/body capture from eligible recordings; body capture documentation describes feature availability/beta and R15-specific requirements.

## Failure patterns that visually expose cheap animation

- Feet slide because the clip and Humanoid movement speed disagree.
- Character moves without a planted support foot or readable center of mass.
- Imported animation has broken bone mapping, mirrored hands or rotated root.
- Tool floats above/beside the palm or ignores grip offset; check both R6 and R15 where supported.
- Locomotion idles and attack clips conflict due to priority/weight; no coherent blending.
- Every pose is equally spaced, giving mechanical uniform speed rather than weight.
- Camera shake and VFX fire at guessed wall-clock times and drift from impact markers.
- Loops pop because first/last poses mismatch; repeated attacks leave track connections behind.
- Animator changes one character while camera/cutscene tracks another.
- Character uses fake geometric stand-ins rather than the user's actual avatar.

## Evidence and acceptance gate

A reviewable animation task should show (1) existing rig name/hierarchy, (2) saved/editable keyframes or imported clip provenance, (3) explicit timeline + markers, (4) side/front/three-quarter contact sheets, (5) actual Studio playtest with movement speed, (6) proof of prop grip, feet, clip transitions, (7) alternate mobile camera/framerate test if relevant, and (8) an honest statement of anything untested.

User experience evaluation is independent of code/test pass: low test failure count never proves emotional weight, appealing poses or good visual animation.
