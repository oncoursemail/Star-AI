A `NetworkVariable<T>` created with default settings uses `NetworkVariableReadPermission.Everyone` and `NetworkVariableWritePermission.Server`: everyone can read, but by default only the server can write. When the client assigns `health.Value`, Netcode rejects the change and logs the permission error, so nothing replicates.

Health is authoritative state, so keep the server write permission and let the client ask instead:
- Add a method like `[Rpc(SendTo.Server)] void RequestDamageRpc(int amount, RpcParams rpcParams = default)` on the NetworkBehaviour. The name must end in `Rpc`.
- On the server, validate the request before applying it: check the sender from `rpcParams.Receive.SenderClientId`, that the amount is in range, cooldowns and distance. Then the server writes `health.Value -= amount`.
- Clients subscribe to `health.OnValueChanged` in `OnNetworkSpawn` to update the UI, and call the RPC only once the object is spawned.
- `NetworkVariableWritePermission.Owner` exists for values the owning client legitimately controls (cosmetics, aim), but not for health, because a client could set any value.
