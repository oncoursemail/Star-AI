---
name: roblox-animation-tools
description: Play character animations and attach tools correctly on R6 and R15 rigs. Use for Animator, AnimationTrack, animation events, Tool grips, Equipped and Unequipped, and held props.
---
# Animation and tool attachment (R6 and R15)
- Play animations through the character's Animator: Instance.new("Animation") with an AnimationId, animator:LoadAnimation(animation), track:Play(). Humanoid:LoadAnimation is deprecated. Load each track once and reuse it.
- Set track.Priority (Enum.AnimationPriority.Action is above Movement and Idle) and track.Looped. Use track.Stopped to resume an idle loop; stop what you started and disconnect events when the character goes away.
- For a moment inside a clip use track:GetMarkerReachedSignal("Name"), not wait; connect before Play, disconnect when the track stops.
- humanoid.RigType is Enum.HumanoidRigType.R6 or R15. A Tool needs a part named Handle; the engine attaches it to RightHand (R15) or Right Arm (R6). Align with Tool.Grip (GripPos, GripForward, GripUp, GripRight) before equipping and test both rigs; do not weld the Handle yourself.
- Use Tool.Equipped, Tool.Unequipped and Tool.Activated; stop the animation on Unequipped.
