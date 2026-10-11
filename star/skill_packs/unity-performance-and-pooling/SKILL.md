---
name: unity-performance-and-pooling
description: Unity C# Performance and pooling guidance.
---
# Unity Performance and pooling
## When to use
Use for Unity C# Performance and pooling implementation and review.
## Ten rules that prevent common bugs
1. Measure with Profiler.
2. Pool frequently spawned objects.
3. Warm pools if needed.
4. Use ObjectPool Get.
5. Release each object once.
6. Reset state on Get.
7. Deactivate objects on Release.
8. Guard null objects.
9. Avoid per-frame allocations.
10. Bound max pool size.
## Compact Unity C# skeleton
```csharp
using UnityEngine;
using UnityEngine.Pool;
public sealed class SpawnPool : MonoBehaviour {
 [SerializeField] private GameObject prefab;
 private ObjectPool<GameObject> pool;
 private void Awake() { pool = new ObjectPool<GameObject>(() => Instantiate(prefab), x => x.SetActive(true), x => x.SetActive(false), x => Destroy(x), collectionCheck: true, defaultCapacity: 8, maxSize: 64); }
 public GameObject Get() => pool.Get();
 public void Release(GameObject x) { if (x != null) pool.Release(x); }
 private void OnDestroy() { pool.Clear(); }
}
```
## Verification checklist
- Confirm required packages and Inspector references.
- Compile in a Unity LTS editor.
- Test missing references and enable/disable cycles.
- Test intended interactions in a player build.
