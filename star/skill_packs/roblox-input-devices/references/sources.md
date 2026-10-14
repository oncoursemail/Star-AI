# Sources for roblox-input-devices

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Input overview: PreferredInput, why TouchEnabled is not a mobile check, detection template | https://create.roblox.com/docs/input |
| S2 | Input Action System: contexts, actions, bindings, events, context changes, displaying bindings | https://create.roblox.com/docs/input/input-action-system |
| S3 | InputAction Pressed, Released, StateChanged, GetState and PreferredBinding | https://create.roblox.com/docs/reference/engine/classes/InputAction |
| S3 | InputBinding KeyCode and UIButton | https://create.roblox.com/docs/reference/engine/classes/InputBinding |
| S4 | InputContext Enabled, Priority and Sink | https://create.roblox.com/docs/reference/engine/classes/InputContext |
| S5 | ContextActionService BindAction, touch buttons (at most 7), priority of recent binds, UnbindAction, SetTitle, SetPosition | https://create.roblox.com/docs/reference/engine/classes/ContextActionService |
| S6 | UserInputService InputBegan, gameProcessedEvent and PreferredInput | https://create.roblox.com/docs/reference/engine/classes/UserInputService |
| S7 | Mouse and keyboard input: return early on processed input | https://create.roblox.com/docs/input/mouse-and-keyboard |
| S8 | InputActionLabel shows the binding for the current device | https://create.roblox.com/docs/reference/engine/classes/InputActionLabel |
| S9 | Client-server boundary: send intent, validate on the server | https://create.roblox.com/docs/scripting/security/client-server-boundary |
| S10 | Players LocalPlayer | https://create.roblox.com/docs/reference/engine/classes/Players |
| S11 | ReplicatedStorage | https://create.roblox.com/docs/reference/engine/classes/ReplicatedStorage |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
