# Sources for roblox-physics-constraints

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated; BodyVelocity, BodyPosition and BodyGyro are tagged Deprecated with LinearVelocity, AlignPosition and AlignOrientation as preferred replacements). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Mover constraints, attachments and legacy BodyMover conversion | https://create.roblox.com/docs/physics/mover-constraints |
| S2 | BodyVelocity is deprecated in favour of LinearVelocity | https://create.roblox.com/docs/reference/engine/classes/BodyVelocity |
| S3 | AlignPosition modes, MaxForce, Responsiveness and RigidityEnabled | https://create.roblox.com/docs/reference/engine/classes/AlignPosition |
| S4 | AlignOrientation OneAttachment mode and CFrame goal | https://create.roblox.com/docs/reference/engine/classes/AlignOrientation |
| S5 | LinearVelocity VelocityConstraintMode, VectorVelocity, RelativeTo and MaxForce | https://create.roblox.com/docs/reference/engine/classes/LinearVelocity |
| S5 | LinearVelocity guide | https://create.roblox.com/docs/physics/constraints/linear-velocity |
| S6 | BasePart ApplyImpulse ownership rules, AssemblyMass and SetNetworkOwner | https://create.roblox.com/docs/reference/engine/classes/BasePart |
| S7 | Workspace Gravity | https://create.roblox.com/docs/reference/engine/classes/Workspace |
| S8 | Network ownership: automatic client ownership, anchored parts, SetNetworkOwner(nil) jitter | https://create.roblox.com/docs/physics/network-ownership |
| S9 | Clients control their character's physics | https://create.roblox.com/docs/scripting/security/network-ownership |
| S10 | VectorForce Force, RelativeTo and ApplyAtCenterOfMass | https://create.roblox.com/docs/reference/engine/classes/VectorForce |
| S11 | Attachment | https://create.roblox.com/docs/reference/engine/classes/Attachment |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
