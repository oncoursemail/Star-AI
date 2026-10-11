---
name: unity-ui-toolkit-and-ugui
description: Unity C# UI Toolkit and uGUI guidance.
---
# Unity UI Toolkit and uGUI
## When to use
Use for Unity C# UI Toolkit and uGUI implementation and review.
## Ten rules that prevent common bugs
1. Choose UI Toolkit or uGUI deliberately.
2. Provide UIDocument in Inspector.
3. Query elements after initialization.
4. Null-check query results.
5. Register callbacks on enable.
6. Unregister on disable.
7. Avoid duplicate subscriptions.
8. Keep UI work on main thread.
9. Test navigation on multiple devices.
10. Do not assume geometry is resolved in Awake.
## Compact Unity C# skeleton
```csharp
using UnityEngine;
using UnityEngine.UIElements;
public sealed class Menu : MonoBehaviour {
 [SerializeField] private UIDocument doc;
 private Button button;
 private void OnEnable() { if (doc == null) return; button = doc.rootVisualElement.Q<Button>("play"); if (button != null) button.clicked += Play; }
 private void OnDisable() { if (button != null) button.clicked -= Play; }
 private void Play() { Debug.Log("Play"); }
}
```
## Verification checklist
- Confirm required packages and Inspector references.
- Compile in a Unity LTS editor.
- Test missing references and enable/disable cycles.
- Test intended interactions in a player build.
