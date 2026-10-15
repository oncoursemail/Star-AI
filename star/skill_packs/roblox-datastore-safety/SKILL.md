---
name: roblox-datastore-safety
description: Save Roblox player data safely with DataStoreService. Use for saving and loading, retries, UpdateAsync, BindToClose, autosave, request limits, session locking and purchase records.
---
# DataStore safety
- Wrap yielding data-store calls in pcall. Retry transient failures in key order with bounded exponential backoff and jitter; do not retry invalid requests. A failed response can have an unknown write outcome: retain unsaved state while the server lives and do not promise recovery after shutdown.
- Use UpdateAsync when the new value depends on the current key or several servers may write. Its transform receives the current value, returns a new value or nil to cancel, must not yield, and can be retried. SetAsync is valid for an independent replacement/new key, but can lose concurrent changes.
- Use a stable per-player key such as "Player_" .. player.UserId. Store serializable values and keep the JSON-serialized key value within 4,194,304 characters; check its encoded length.
- Save on Players.PlayerRemoving and game:BindToClose; BindToClose callbacks run in parallel with a bounded shutdown window (30 seconds). Finish critical saves within it; a shutdown save is not guaranteed.
- Do not persist every change. Stagger autosaves and check budgets; throttled requests can queue (30 per queue), then drop (error codes 301-306) when queues fill. An interval such as 60 s is a design choice, not an engine limit.
- For a retryable developer product, persist the award and its PurchaseId atomically before ProcessReceipt returns PurchaseGranted; return NotProcessedYet for uncertain or failed persistence and never grant the same ID twice.
- When multiple servers can hold a live profile, consider an owner-checked session lock with lease renewal, release and crash recovery. A lock alone does not prevent stale writes without ownership checks.
