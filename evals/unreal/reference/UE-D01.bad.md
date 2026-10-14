This is a threading issue. Wrap the access in a critical section, or allocate the inventory with `new UInventory()` so Unreal does not manage it.
