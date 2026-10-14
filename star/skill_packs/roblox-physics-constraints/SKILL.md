---
name: roblox-physics-constraints
description: Opt-in Roblox physics recipes with modern mover constraints (LinearVelocity, AlignPosition, AlignOrientation, VectorForce), impulses, knockback and network ownership in typed Luau.
---
# roblox-physics-constraints
## When to use
Use for Roblox forces and physical motion: knockback, moving or hovering platforms, floating objects, pushes, replacing deprecated BodyVelocity, BodyPosition, BodyGyro or BodyForce, and deciding who simulates a part. Not for tweened, anchored animation.

## Ten concrete rules
1. BodyVelocity, BodyPosition, BodyGyro, BodyForce, BodyAngularVelocity and BodyThrust are deprecated; use LinearVelocity, AlignPosition, AlignOrientation, VectorForce and AngularVelocity. [S1][S2]
2. A mover acts through Attachment0 inside the moving assembly. OneAttachment modes aim at the constraint's own Position or CFrame. [S1][S3][S4]
3. LinearVelocity uses VelocityConstraintMode Line, Plane or Vector instead of zeroing force components; set RelativeTo on purpose. [S1][S5]
4. Size forces from mass: AssemblyMass * workspace.Gravity holds an assembly up. A MaxForce that is too low cannot move it. [S6][S7]
5. ApplyImpulse changes velocity at once: impulse = AssemblyMass * velocity change. [S6]
6. Unanchored parts near a player may be simulated by that client; the server always owns anchored parts. [S8]
7. Call SetNetworkOwner(nil) from the server on gameplay-critical unanchored parts; it can make them look jittery to players. [S8]
8. ApplyImpulse on a server-owned part must run on the server; from a LocalScript it has no effect. [S6]
9. Each client controls its own character's physics. For knockback, parent a short-lived LinearVelocity to the character's root and remove it after the push. [S9][S5]
10. Tune Align movers with Responsiveness, MaxVelocity or MaxTorque; RigidityEnabled reacts as fast as possible. Destroy temporary constraints and attachments. [S3][S4]

## Three correct Luau examples
Each is independent and runs in a server Script.

### Example 1: knockback with a temporary LinearVelocity
~~~luau
--!strict
local function knockback(character: Model, from: Vector3, speed: number, duration: number)
	local root = character:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") then
		return
	end
	local flat = (root.Position - from) * Vector3.new(1, 0, 1)
	if flat.Magnitude < 0.01 then
		return
	end
	local attachment = Instance.new("Attachment")
	attachment.Parent = root
	local push = Instance.new("LinearVelocity")
	push.Attachment0 = attachment
	push.RelativeTo = Enum.ActuatorRelativeTo.World
	push.VelocityConstraintMode = Enum.VelocityConstraintMode.Vector
	push.VectorVelocity = flat.Unit * speed + Vector3.new(0, speed * 0.4, 0)
	push.MaxForce = root.AssemblyMass * workspace.Gravity * 10
	push.Parent = root
	task.delay(duration, function()
		push:Destroy()
		attachment:Destroy()
	end)
end

return knockback
~~~
The force cap scales with the character's mass, so light and heavy rigs move alike. [S5][S6]

### Example 2: platform moved by AlignPosition and held level
~~~luau
--!strict
local platform = workspace:WaitForChild("Platform") :: BasePart
platform.Anchored = false
local attachment = Instance.new("Attachment")
attachment.Parent = platform

local move = Instance.new("AlignPosition")
move.Mode = Enum.PositionAlignmentMode.OneAttachment
move.Attachment0 = attachment
move.MaxForce = platform.AssemblyMass * workspace.Gravity * 4
move.Responsiveness = 20
move.Parent = platform

local hold = Instance.new("AlignOrientation")
hold.Mode = Enum.OrientationAlignmentMode.OneAttachment
hold.Attachment0 = attachment
hold.CFrame = platform.CFrame.Rotation
hold.RigidityEnabled = true
hold.Parent = platform
platform:SetNetworkOwner(nil)

local a = platform.Position
local b = a + Vector3.new(0, 0, 40)
while platform.Parent do
	move.Position = b
	task.wait(4)
	move.Position = a
	task.wait(4)
end
~~~
Players ride a simulated part, and the server owns it so no client can fling it. [S3][S4][S8]

### Example 3: floating balloon and a server-side push
~~~luau
--!strict
local balloon = workspace:WaitForChild("Balloon") :: BasePart
local attachment = Instance.new("Attachment")
attachment.Parent = balloon
local lift = Instance.new("VectorForce")
lift.Attachment0 = attachment
lift.RelativeTo = Enum.ActuatorRelativeTo.World
lift.ApplyAtCenterOfMass = true
lift.Force = Vector3.new(0, balloon.AssemblyMass * workspace.Gravity * 1.05, 0)
lift.Parent = balloon

local crate = workspace:WaitForChild("Crate") :: BasePart
crate:SetNetworkOwner(nil)
crate:ApplyImpulse(Vector3.new(0, crate.AssemblyMass * 50, 0)) -- +50 studs/s upward
~~~
Five percent more than the weight makes the balloon rise slowly. [S6][S7][S10]

## Three common mistakes
1. Writing new code with deprecated BodyMover classes. [S1][S2]
2. Calling ApplyImpulse from a LocalScript on a server-owned part, which does nothing. [S6]
3. Forgetting Attachment0 or leaving MaxForce too low, so the constraint never moves the part. [S1][S5]

## Checklist
- [ ] No deprecated BodyMover classes.
- [ ] Every mover has Attachment0 inside the moving assembly.
- [ ] Forces are sized from AssemblyMass and workspace.Gravity.
- [ ] Ownership is decided on purpose for gameplay-critical parts.
- [ ] Temporary constraints and attachments are destroyed.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S10]. Multipliers and speeds are illustrative.
