# Sources for roblox-cutscenes

Official Roblox Creator Documentation (CC-BY-4.0); community techniques are marked as such. Read on 2026-10-14.

| Claim in the skill | Source |
|---|---|
| Scripting the camera: each client has a local Camera (Workspace.CurrentCamera); CameraType Scriptable overrides the default camera scripts; CFrame is the main property; set Focus every frame for a Scriptable camera; FieldOfView 1..120, default 70 | https://create.roblox.com/docs/workspace/camera |
| Camera class (CameraType, CameraSubject, CFrame, Focus, FieldOfView, WorldToViewportPoint) | https://create.roblox.com/docs/reference/engine/classes/Camera |
| TweenService and TweenService:GetValue (an eased alpha for any curve, same easing styles and directions as tweens) | https://create.roblox.com/docs/reference/engine/classes/TweenService |
| RunService:BindToRenderStep priorities (Enum.RenderPriority.Camera; lower values run first), UnbindFromRenderStep | https://create.roblox.com/docs/reference/engine/classes/RunService |
| Post-processing effects incl. DepthOfFieldEffect (FocusDistance, InFocusRadius, FarIntensity, NearIntensity; under Lighting or the camera) | https://create.roblox.com/docs/environment/post-processing-effects |
| DepthOfFieldEffect reference | https://create.roblox.com/docs/reference/engine/classes/DepthOfFieldEffect |
| FaceControls: 50 FACS properties (JawDrop, LeftLipCornerPuller, Corrugator, Funneler, EyesLookDown, ...), Not Replicated, Animation capability | https://create.roblox.com/docs/reference/engine/classes/FaceControls |
| Dynamic heads in Studio: FaceControls is a child of the head MeshPart; property values 0..1; combinations make expressions and expressions over time make animation; facial bones are not exposed | https://create.roblox.com/docs/art/avatar/facial-animation/using-heads-in-studio |
| Testing dynamic heads (Animation Editor face tracks / Face Animation Editor) | https://create.roblox.com/docs/avatar/dynamic-heads/test |
| KeyframeSequenceProvider:RegisterKeyframeSequence: a temporary id for testing; works only in Studio; upload the sequence for an id that works online | https://create.roblox.com/docs/reference/engine/classes/KeyframeSequenceProvider |
| KeyframeSequence, Keyframe (Time), Pose (CFrame, EasingStyle, EasingDirection; nested like the rig) | https://create.roblox.com/docs/reference/engine/classes/KeyframeSequence |
| Animator:LoadAnimation, AnimationTrack (Play, Stop, AdjustSpeed, Priority, Looped, WeightCurrent) | https://create.roblox.com/docs/reference/engine/classes/AnimationTrack |
| Players:CreateHumanoidModelFromDescriptionAsync (server; the non-Async method is deprecated), HumanoidDescription.Head | https://create.roblox.com/docs/reference/engine/classes/Players |
| AnimationConstraint (avatar joints that may replace Motor6D; Transform) | https://create.roblox.com/docs/reference/engine/classes/AnimationConstraint |
| ScreenGui.IgnoreGuiInset, TextLabel.MaxVisibleGraphemes (typewriter text) | https://create.roblox.com/docs/reference/engine/classes/ScreenGui |
| ContextActionService:BindAction (keyboard/gamepad skip) | https://create.roblox.com/docs/reference/engine/classes/ContextActionService |
| StarterGui:SetCoreGuiEnabled / GetCoreGuiEnabled | https://create.roblox.com/docs/reference/engine/classes/StarterGui |
| Remote events and server validation | https://create.roblox.com/docs/scripting/events/remote |
| Community: skip buttons fail while a camera tween still runs; keep the tween, Cancel() it, snap to the end, then CameraType Custom and CameraSubject the Humanoid; sequence with Completed instead of waits | https://devforum.roblox.com/t/cutscene-skip-button/911078 , https://devforum.roblox.com/t/how-do-i-skip-a-cutscene/1192583 , https://devforum.roblox.com/t/implementing-cutscene-skipping/924709 |
| Community: the default Animate script is a LocalScript and does not run on NPC copies made with CreateHumanoidModelFromDescription; animate them yourself | https://devforum.roblox.com/t/2579192 |

STAR's own observations in Studio (docs/agents/roblox-cutscenes-20261014/, not documented guarantees):
- Rigs made with CreateHumanoidModelFromDescription(Async) in STAR Test Place use AnimationConstraint joints, not
  Motor6D (the lab printed `joint=AnimationConstraint` for RightShoulder).
- The default HumanoidDescription (Head = 0) already produced a head with FaceControls in this place; the free
  "Dylan Default" bundle's head (asset 10687288296) did too. FaceControls values written by a LocalScript every frame
  were read back unchanged (the lab's samples).
- KeyframeSequenceProvider:RegisterKeyframeSequence worked from a LocalScript in a Studio playtest (`recoil`, `nod`).
- Default R15 idle (507766666) holds the arms 12-37 degrees from rest on this rig (measured RightShoulder transform).
  Correction (v4): 507766666 is the Animate script's rare look-around idle, not the main one (507766388).

Craft numbers (shot length >= 1.2 s, FOV change < 25 degrees per shot, reading time ~15 characters per second + 0.8 s,
walk 4-10 studs/s, head size 4% / 20-27% of frame height) are STAR's working rules from the lab critique, not
Roblox documentation.

API names verified with the knowledge service /api-lookup on 2026-10-14 (all found; deprecated ones removed from the
code: Players:CreateHumanoidModelFromDescription -> ...Async, PoseBase.Weight no longer set):
Camera.CameraType, Enum.CameraType.Scriptable, Camera.CFrame, Camera.FieldOfView, Camera.Focus, Camera.CameraSubject,
Camera:WorldToViewportPoint, TweenService:GetValue, Enum.EasingStyle.Sine, RunService:BindToRenderStep,
RunService:UnbindFromRenderStep, Enum.RenderPriority.Camera, DepthOfFieldEffect.FocusDistance,
DepthOfFieldEffect.InFocusRadius, DepthOfFieldEffect.FarIntensity, DepthOfFieldEffect.NearIntensity,
FaceControls.JawDrop, FaceControls.LeftLipCornerPuller, FaceControls.Corrugator, FaceControls.Funneler,
FaceControls.EyesLookDown, KeyframeSequenceProvider:RegisterKeyframeSequence, KeyframeSequence.Priority, Keyframe.Time,
Pose.CFrame, Pose.EasingStyle, Enum.PoseEasingStyle.Cubic, Animator:LoadAnimation, AnimationTrack:AdjustSpeed,
AnimationTrack.WeightCurrent, Animator:GetPlayingAnimationTracks, Players:CreateHumanoidModelFromDescriptionAsync,
HumanoidDescription.Head, Enum.HumanoidRigType.R15, AnimationConstraint.Transform, Motor6D.Transform,
TextLabel.MaxVisibleGraphemes, ScreenGui.IgnoreGuiInset, ContextActionService:BindAction, StarterGui:SetCoreGuiEnabled,
StarterGui:GetCoreGuiEnabled, Humanoid.JumpHeight, HttpService:GenerateGUID, SurfaceGui.CanvasSize,
Instance:FindFirstChildWhichIsA, Humanoid:SetStateEnabled.

## v4 cinematic pass (2026-10-14), verified by running in Studio (STAR Test Place, brain 2)
Every API below ran without error in the lab playtests v4a-v4-final (no `[StarCutscene]` or script errors in the
console; the frames show each effect). Not looked up with /api-lookup this time (no brain-1 requests in this pass).
- Lighting.ClockTime / Brightness / ExposureCompensation / Ambient / OutdoorAmbient / ColorShift_Top /
  ColorShift_Bottom / EnvironmentDiffuseScale / EnvironmentSpecularScale, Lighting:GetSunDirection (sun at -x/-z in the
  evening: (-0.90, 0.17, -0.40) at 17.3), Atmosphere (Density, Offset, Color, Decay, Glare, Haze), ColorCorrectionEffect,
  BloomEffect (Threshold above 1 keeps sky and lit walls from blooming), SunRaysEffect, DepthOfFieldEffect, SpotLight
  (Face, Angle, Range, Brightness): create.roblox.com/docs/reference/engine/classes/<ClassName>.
- HumanoidDescription:SetAccessories(list, includeRigid=true) with AccessoryType Hair / Eyebrow (rigid) and TShirt /
  Jacket / Pants / LeftShoe / RightShoe (IsLayered = true). `HumanoidDescription.EyebrowAccessory` does NOT exist
  (the first v4 run failed on it). The built actor had 5 WrapLayers and a FaceControls head.
- Free catalog items used (price 0 or part of a free Roblox bundle; nothing bought): Man Face head 10725826963 and
  brows 10725837187 (bundle 949), Brown Charmer Hair 376548738, Basic T-Shirt Gray 9112474888, Leather Jacket Black
  7192549218, Cargo Pants Brown 6984740059, Roblox Sneakers Gray 7193165925/7193166879 (bundle 872). Checked with the
  public catalog API (catalog.roblox.com/v1/search/items/details, economy.roblox.com/v2/assets/<id>/details).
- Default Animate script of a CreateHumanoidModelFromDescriptionAsync rig (read in Studio): idle Animation1 =
  507766388 (weight 9), Animation2 = 507766666 (weight 1, the look-around); walk = 913402848.
- Terrain:FillBlock / FillCylinder / FillBall (FillBall takes a Vector3 centre, not a CFrame), Terrain:ReadVoxels,
  workspace:Raycast. In a playtest a 4-stud slab filled at y 0..4 surfaced at y 6 (raycast); in Edit, ReadVoxels showed
  the fill in cell 0..4 only. The lab therefore measures the ground and lifts the set's origin.
- settings().Rendering.QualityLevel (Studio, Edit context): Automatic dropped DOF/sun rays/bloom on brain 2's GPU;
  Level21 shows them. It was back at Automatic after a later playtest (cause not confirmed); the lab now sets it
  for each capture and restores the previous value.
