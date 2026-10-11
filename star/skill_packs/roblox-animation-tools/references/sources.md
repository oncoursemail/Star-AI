# Sources for roblox-animation-tools

Official Roblox Creator Documentation (CC-BY-4.0), checked against the STAR Knowledge index (creator-docs af5f853).

| Claim in the skill | Documentation page |
|---|---|
| Play animations from scripts: Humanoid contains an Animator, Animation + AnimationId, Animator:LoadAnimation, AnimationTrack:Play | https://create.roblox.com/docs/animation/using |
| Animator:LoadAnimation; loading on a client-owned character also loads it for the server | https://create.roblox.com/docs/reference/engine/classes/Animator |
| Humanoid:LoadAnimation is deprecated (/api-lookup reports deprecated: true) | https://create.roblox.com/docs/reference/engine/classes/Humanoid |
| Animation events, AnimationTrack:GetMarkerReachedSignal | https://create.roblox.com/docs/animation/events and https://create.roblox.com/docs/reference/engine/classes/AnimationTrack |
| Enum.AnimationPriority, AnimationTrack.Priority / Looped / Stopped | https://create.roblox.com/docs/reference/engine/classes/AnimationTrack |
| A tool needs a part named Handle; it attaches to RightHand (R15) or Right Arm (R6); grip properties | https://create.roblox.com/docs/players/tools |
| Tool.Grip is one CFrame stored as GripPos, GripForward, GripRight, GripUp | https://create.roblox.com/docs/reference/engine/classes/Tool |
| Enum.HumanoidRigType, Humanoid.RigType | https://create.roblox.com/docs/reference/engine/enums/HumanoidRigType |

API names verified with the knowledge service /api-lookup on 2026-10-10: Animator:LoadAnimation, AnimationTrack:GetMarkerReachedSignal,
AnimationTrack.Priority, AnimationTrack.Stopped, Enum.AnimationPriority, Humanoid.RigType, Enum.HumanoidRigType, Tool.Grip, Tool.GripPos,
Tool.Equipped, Tool.Unequipped, Animation.AnimationId. (Tool.Handle is a child part, not a property.)
