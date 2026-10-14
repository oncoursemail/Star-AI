# Sources for roblox-combat-hitboxes

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | The server is authoritative; clients may send fabricated data | https://create.roblox.com/docs/scripting/security/security-tactics |
| S2 | Weapon hit validation, latency tolerance, NaN-safe checks, rate limits | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| S3 | GetPartBoundsInBox, GetPartBoundsInRadius, GetPartsInPart and Raycast on WorldRoot | https://create.roblox.com/docs/reference/engine/classes/WorldRoot |
| S4 | OverlapParams FilterType, FilterDescendantsInstances and MaxParts | https://create.roblox.com/docs/reference/engine/datatypes/OverlapParams |
| S5 | RaycastParams filtering | https://create.roblox.com/docs/reference/engine/datatypes/RaycastParams |
| S6 | Raycasting guide and RaycastResult fields | https://create.roblox.com/docs/workspace/raycasting |
| S6 | RaycastResult Instance and Position | https://create.roblox.com/docs/reference/engine/datatypes/RaycastResult |
| S7 | Humanoid TakeDamage and ForceField protection, Health | https://create.roblox.com/docs/reference/engine/classes/Humanoid |
| S8 | Players PlayerRemoving and GetPlayerFromCharacter | https://create.roblox.com/docs/reference/engine/classes/Players |
| S9 | FindFirstAncestorOfClass and FindFirstChildOfClass | https://create.roblox.com/docs/reference/engine/classes/Instance |
| S10 | RemoteEvent FireServer and OnServerEvent | https://create.roblox.com/docs/scripting/events/remote |
| S11 | UserInputService InputBegan and GetMouseLocation | https://create.roblox.com/docs/reference/engine/classes/UserInputService |
| S12 | Camera ViewportPointToRay | https://create.roblox.com/docs/reference/engine/classes/Camera |
| S13 | BasePart Touched fires only from physical movement | https://create.roblox.com/docs/reference/engine/classes/BasePart |
| S14 | ReplicatedStorage holds the RemoteEvent both sides use | https://create.roblox.com/docs/reference/engine/classes/ReplicatedStorage |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
