---
name: roblox-animation-craft
description: Animation craft for Roblox: timing, anticipation, follow-through, easing, combat move-set frame data, priorities and blending, animation events, springs and IK.
---
# Animation craft (Roblox)
- Timing sells weight: anticipation, action, follow-through, settle. Combat moves are frame data at 60 fps: startup, active (only these frames hit), recovery, with input buffering and a cancel window late in recovery. Open hit windows with animation events (track:GetMarkerReachedSignal("Name")), not wait; KeyframeReached is deprecated.
- Easing: ease out for arrivals, ease in for departures, overshoot (Back, Elastic) for emphasis: TweenInfo.new(time, Enum.EasingStyle.X, Enum.EasingDirection.Y). Secondary motion uses a closed-form damped spring driven by dt (frame-rate independent).
- Priorities, highest first: Action4, Action3, Action2, Action, Movement, Idle, Core. Per joint the higher wins; equal priorities blend by weight. Fade with track:Play(fadeTime, weight, speed), :AdjustWeight(weight, fadeTime), :AdjustSpeed(speed), :Stop(fadeTime).
- IK: an IKControl under the Humanoid with ChainRoot, EndEffector, Target and Type (Enum.IKControlType.Position, Transform, LookAt, Rotation); tween Weight and set SmoothTime so the limb does not snap.
