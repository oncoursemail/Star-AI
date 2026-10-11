---
name: unity-input-system
description: Unity C# Input System guidance.
---
# Unity Input System
## When to use
Use for Unity C# Input System implementation and review.
## Ten rules that prevent common bugs
1. Install and activate the Input System package.
2. Author actions and bindings in an asset.
3. Enable actions before use.
4. Disable actions when no longer needed.
5. Unsubscribe callbacks on disable.
6. Read callback value using correct type.
7. Handle canceled input.
8. Avoid creating actions every Update.
9. Check keyboard and gamepad.
10. Do not unintentionally mix input backends.
## Compact Unity C# skeleton
```csharp
using UnityEngine;
using UnityEngine.InputSystem;
public sealed class MoveInput : MonoBehaviour {
 [SerializeField] private InputActionReference move;
 private void OnEnable() { if (move != null && move.action != null) move.action.Enable(); }
 private void OnDisable() { if (move != null && move.action != null) move.action.Disable(); }
}
```
## Verification checklist
- Confirm required packages and Inspector references.
- Compile in a Unity LTS editor.
- Test missing references and enable/disable cycles.
- Test intended interactions in a player build.
