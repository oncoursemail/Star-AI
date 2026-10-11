---
name: roblox-performance-streaming
description: Improve Roblox script performance and make code safe with StreamingEnabled. Use for polling loops, lag, frame time, Heartbeat and RenderStepped, object pooling and instance streaming.
---
# Performance and instance streaming
Measure first (MicroProfiler, Script Profiler); change one thing at a time.
- No per-frame polling (while true do wait() loops). React to events (Touched, ProximityPrompt.Triggered, GetPropertyChangedSignal, PlayerAdded) or loop with task.wait(0.25) or more. Use task.wait, not wait.
- RunService.Heartbeat runs every frame: keep handlers tiny and spread heavy work across frames. RenderStepped is for client camera and visuals only.
- Find nearby things with workspace:GetPartBoundsInRadius and OverlapParams, not loops over every part or player.
- Reuse instead of create and destroy: a fixed pool of parts, idle ones parked (Parent = nil), state reset on reuse; Debris:AddItem for timed cleanup. Disconnect unused connections.
- With StreamingEnabled use WaitForChild with a timeout, react to ChildAdded or CollectionService:GetInstanceAddedSignal, and never index long paths such as workspace.Map.Building.Door.
- Set Model.ModelStreamingMode (Atomic or Persistent) from a server Script, never a LocalScript.
