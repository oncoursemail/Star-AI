Addressables keeps a reference count for every asset and every AssetBundle it loads. `Addressables.InstantiateAsync` adds a reference that is only removed by `Addressables.ReleaseInstance`; calling `Destroy(gameObject)` removes the object but leaves the reference in place. Each `Addressables.LoadAssetAsync<AudioClip>` call also adds a reference that must be released through its handle.

A bundle is unloaded only when all the assets loaded from it have been released, so a single leaked reference per enemy keeps the whole enemy bundle (meshes, textures, clips) in memory, and each wave adds more.

Fix:
- When an enemy dies, call `Addressables.ReleaseInstance(gameObject)` instead of `Destroy`.
- Keep the `AsyncOperationHandle<AudioClip>` from each load and call `Addressables.Release(handle)` (or `handle.Release()`) exactly once when the sound is no longer needed, for example in `OnDestroy`. Better, load shared clips once per wave rather than per enemy.
- Verify with the Addressables profiler module or `AsyncOperationHandle.ReferenceCount`, and check `handle.IsValid()` to avoid double releases.
