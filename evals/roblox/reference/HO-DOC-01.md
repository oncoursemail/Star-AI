An attribute can hold a string, a boolean or a number, or one of these Roblox datatypes: UDim, UDim2, BrickColor, Color3, Vector2, Vector3, CFrame, NumberSequence, ColorSequence, NumberRange, Rect or Font [1]. Tables and Instances are not in that list, so use a Folder with values or a ModuleScript for them [1].

To react to one attribute changing, connect `Instance:GetAttributeChangedSignal("Name")`; the `AttributeChanged` event fires for any attribute [2].

Attribute values replicate: when the server sets one, clients can read it right away with `GetAttribute` [1][2].

---
**Sources retrieved by STAR** (official documentation)

1. [Properties and attributes in Studio](https://create.roblox.com/docs/studio/properties#instance-attributes) · cited
2. [Attributes in scripts](https://create.roblox.com/docs/scripting/attributes) · cited
