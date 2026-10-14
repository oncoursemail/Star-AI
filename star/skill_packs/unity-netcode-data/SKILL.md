---
name: unity-netcode-data
description: Netcode for GameObjects authority, RPC and NetworkVariable rules, spawning and ownership, Addressables load and release, and Unity save data. Use for Unity multiplayer code, asset loading leaks, or saving player data.
---
# Unity netcode, Addressables and save data
The server is authoritative by default; clients send requests and the server decides.
- NetworkVariable<T>: everyone reads, only the server writes by default. A client write is rejected and never syncs. Send a request RPC and write on the server, or use NetworkVariableWritePermission.Owner for owner-driven values. No string: use FixedString32Bytes and friends. After changing a collection call CheckDirtyState().
- Subscribe to OnValueChanged (previous, current) in OnNetworkSpawn; unsubscribe in OnNetworkDespawn.
- RPCs: [Rpc(SendTo.Server)], [Rpc(SendTo.ClientsAndHost)], [Rpc(SendTo.Owner)]; the method name must end in Rpc. ServerRpc and ClientRpc are legacy. Take RpcParams last and read Receive.SenderClientId.
- Treat every RPC argument as untrusted: check sender, ownership, range and cooldown on the server.
- RPCs and NetworkVariables work only on a spawned NetworkObject: call them from OnNetworkSpawn or later, never in Awake.
- Only the server spawns in client-server: Instantiate then NetworkObject.Spawn(), or InstantiateAndSpawn. Register the prefab in the Network Prefabs list. Despawn on the authority; clients never Destroy networked objects.
- NetworkTransform is server-authoritative by default; set Authority Mode to Owner for player-driven movement or the client is snapped back. Load scenes through NetworkManager.SceneManager.
- Distributed authority has no host and trusts clients more; avoid it for competitive games.
- Addressables: each LoadAssetAsync needs exactly one Release of its handle; InstantiateAsync needs ReleaseInstance, not Destroy. A bundle unloads only when every asset from it is released. Check the Addressables profiler module and handle.IsValid().
- Saves: files under Application.persistentDataPath, write to a temp file then replace, keep a version field. JsonUtility handles fields only, no top-level arrays; Newtonsoft for dictionaries and properties (keep types from IL2CPP stripping). PlayerPrefs only for settings (int, float, string, unencrypted). Never BinaryFormatter: it is unsafe on untrusted files.
- Local saves are editable; currency and unlocks belong on a backend (UGS Cloud Save or your own).
- Roblox map: RemoteEvent -> Rpc, replicated Attribute -> NetworkVariable, DataStoreService -> Cloud Save or your backend. Unity gives no free hosted server.
