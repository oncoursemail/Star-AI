# Sources for roblox-animation-craft

Official Roblox Creator Documentation (CC-BY-4.0), checked against the STAR Knowledge index (creator-docs af5f853).

| Claim in the skill | Documentation page |
|---|---|
| Animation editor: priorities, easing style and direction | https://create.roblox.com/docs/animation/editor |
| Animation events and GetMarkerReachedSignal | https://create.roblox.com/docs/animation/events |
| Use animations: Animator, weights | https://create.roblox.com/docs/animation/using |
| Inverse kinematics and IKControl properties | https://create.roblox.com/docs/animation/inverse-kinematics |
| Enum.AnimationPriority: per-joint evaluation, blending by weight | https://create.roblox.com/docs/reference/engine/enums/AnimationPriority |
| AnimationTrack: Play, Stop, AdjustWeight, AdjustSpeed, GetMarkerReachedSignal | https://create.roblox.com/docs/reference/engine/classes/AnimationTrack |
| IKControl and Enum.IKControlType | https://create.roblox.com/docs/reference/engine/classes/IKControl |
| UI animation/tweens: TweenInfo and easing styles | https://create.roblox.com/docs/ui/animation |

API names verified with the knowledge service /api-lookup on 2026-10-11: Animator:LoadAnimation, AnimationTrack:Play, AnimationTrack:Stop, AnimationTrack:AdjustWeight, AnimationTrack:AdjustSpeed, AnimationTrack:GetMarkerReachedSignal, AnimationTrack.Priority, Enum.AnimationPriority (Core, Idle, Movement, Action, Action2, Action3, Action4), IKControl (ChainRoot, EndEffector, Target, Type, Weight, Enabled, SmoothTime), Enum.IKControlType (Transform, Position, LookAt, Rotation), TweenInfo.new, Enum.EasingStyle, Enum.EasingDirection. /api-lookup reports AnimationTrack.KeyframeReached as deprecated. The principles themselves (anticipation, follow-through, frame data) are general animation craft, not Roblox API facts; the official documentation covers the easing options and the API, not the principles.
