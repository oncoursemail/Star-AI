---
name: unity-scriptableobjects-and-data
description: Unity C# ScriptableObjects and data guidance.
---
# Unity ScriptableObjects and data
## When to use
Use for Unity C# ScriptableObjects and data implementation and review.
## Ten rules that prevent common bugs
1. Use ScriptableObject for authored data.
2. Use CreateAssetMenu for assets.
3. Do not store runtime player state on shared assets.
4. Use CreateInstance rather than new.
5. Serialize private fields.
6. Validate bounds in OnValidate.
7. Separate runtime copies from definitions.
8. Do not rely on runtime asset persistence.
9. Version save schemas separately.
10. Test reloading and build behavior.
## Compact Unity C# skeleton
```csharp
using UnityEngine;
[CreateAssetMenu(fileName = "Item", menuName = "Game/Item")]
public sealed class Item : ScriptableObject {
 [SerializeField] private string displayName;
 [Min(0)] [SerializeField] private int price;
 public int Price => price;
 private void OnValidate() { price = Mathf.Max(0, price); }
}
```
## Verification checklist
- Confirm required packages and Inspector references.
- Compile in a Unity LTS editor.
- Test missing references and enable/disable cycles.
- Test intended interactions in a player build.
