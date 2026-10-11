---
name: unity-monobehaviour-lifecycle
description: Unity C# MonoBehaviour lifecycle guidance.
---
# MonoBehaviour lifecycle
## When to use
Use for Awake, Start, Update, OnEnable and OnDisable behavior in Unity.
## Ten rules
1. Cache references in Awake.
2. Never depend on Awake ordering across objects.
3. Subscribe in OnEnable.
4. Unsubscribe in OnDisable.
5. Initialize dependent behavior in Start.
6. Do not start coroutines in constructors.
7. Multiply Update movement by Time.deltaTime.
8. Use FixedUpdate for physics.
9. Avoid allocations per frame.
10. Guard destroyed references.
## C# skeleton
```csharp
using UnityEngine;
public sealed class Spin : MonoBehaviour {
    [SerializeField] private float speed = 90f;
    private void Update() { transform.Rotate(Vector3.up, speed * Time.deltaTime); }
}
```
## Verification checklist
- Compile in the editor.
- Test missing Inspector dependencies.
- Enable and disable twice.
- Validate scene transitions and a player build.
