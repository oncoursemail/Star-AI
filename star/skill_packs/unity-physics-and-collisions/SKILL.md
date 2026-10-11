---
name: unity-physics-and-collisions
description: Unity C# Physics and collisions guidance.
---
# Unity Physics and collisions
## When to use
Use for Unity C# Physics and collisions implementation and review.
## Ten rules that prevent common bugs
1. Use Rigidbody on dynamic objects.
2. Drive forces from FixedUpdate.
3. Avoid writing Transform for dynamic physics.
4. Configure colliders appropriately.
5. Distinguish triggers from collisions.
6. Check layer matrix.
7. Avoid duplicate force application.
8. Use appropriate detection mode for fast bodies.
9. Do not assume static colliders collide with each other.
10. Profile and playtest contact behavior.
## Compact Unity C# skeleton
```csharp
using UnityEngine;
[RequireComponent(typeof(Rigidbody))]
public sealed class Thrust : MonoBehaviour {
 private Rigidbody body;
 private void Awake() { body = GetComponent<Rigidbody>(); }
 private void FixedUpdate() { body.AddForce(Vector3.forward, ForceMode.Acceleration); }
}
```
## Verification checklist
- Confirm required packages and Inspector references.
- Compile in a Unity LTS editor.
- Test missing references and enable/disable cycles.
- Test intended interactions in a player build.
