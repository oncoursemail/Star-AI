---
name: roblox-datastore-safety
description: Save Roblox player data safely with DataStoreService. Use for saving and loading, retries, UpdateAsync, BindToClose, autosave, request limits, session locking and purchase records.
---
# DataStore safety
- Wrap every DataStore call in pcall: requests fail when throttled or the service is down. Retry a bounded number of times (for example 3) with growing task.wait delays, then give up and keep the data in memory.
- For data that exists use UpdateAsync, not GetAsync then SetAsync: the callback gets the old value and returns the new one, or nil to cancel. It must not yield. Never overwrite existing player data with SetAsync.
- Key: "Player_" .. player.UserId. Plain serializable tables, under the 4 MB per-key limit.
- Save on Players.PlayerRemoving and in game:BindToClose. Bound functions run in parallel and the server waits 30 seconds: save players with task.spawn and wait with a deadline.
- Never save on every change. Autosave on an interval (for example 60 s), staggered, to stay in the request budget; past it requests queue, then drop (error codes 301-306).
- ProcessReceipt returns PurchaseGranted only after the grant and PurchaseId are saved, else NotProcessedYet.
- Several servers may write one key: use session locking (a lock id kept in the data).
