The `UInventory` is a UObject managed by Unreal's garbage collector. The GC only follows references it can see through reflection, and a raw `UInventory*` member without `UPROPERTY()` is invisible to it, so after the next GC pass the object is collected and your pointer dangles.

Fix: declare the member as a reflected property, in UE5 style:

```cpp
UPROPERTY()
TObjectPtr<UInventory> Inventory;
```

Now the actor keeps the inventory alive. Use `TWeakObjectPtr` only for references that should not keep it alive, and check `IsValid()` before using those. Not compiled here; build and run with `obj gc` to force a collection and confirm.
