# Sources for roblox-collection-tags

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | CollectionService tags, GetTagged, added and removed signals, replication and cleanup warnings | https://create.roblox.com/docs/reference/engine/classes/CollectionService |
| S2 | Instance AddTag, SetAttribute naming rules, GetAttribute and attribute signals | https://create.roblox.com/docs/reference/engine/classes/Instance |
| S3 | Streaming techniques: detect tagged objects streaming in and out | https://create.roblox.com/docs/workspace/streaming/techniques |
| S4 | Properties and attributes guide: set, get, delete and listen for changes | https://create.roblox.com/docs/scripting/attributes |
| S5 | Client-server boundary: client changes do not replicate and must not be trusted | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| S6 | BasePart Touched | https://create.roblox.com/docs/reference/engine/classes/BasePart |
| S7 | Players GetPlayerFromCharacter | https://create.roblox.com/docs/reference/engine/classes/Players |
| S8 | RunService Heartbeat | https://create.roblox.com/docs/reference/engine/classes/RunService |
| S9 | Part Shape and creation | https://create.roblox.com/docs/reference/engine/classes/Part |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
