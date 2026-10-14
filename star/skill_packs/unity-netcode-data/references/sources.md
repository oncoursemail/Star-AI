# Sources for unity-netcode-data

Checked against official Unity documentation (Netcode for GameObjects 3.1, Addressables 4.1, Unity 6.6 manual and scripting reference) on 2026-10-13. The guidance is written in STAR's own words; Unity documentation is licensed CC BY-NC-ND, so no text is copied.

| Claim in the skill | Documentation page |
|---|---|
| NetworkVariable defaults: read Everyone, write Server; Owner write option; OnValueChanged(previous, current) subscribed in OnNetworkSpawn; FixedString instead of string; CheckDirtyState for collections | https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/basics/networkvariable.html |
| [Rpc(SendTo.X)] attribute, Rpc name suffix, SendTo targets, RpcParams and Receive.SenderClientId, InvokePermission, Delivery | https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/advanced-topics/message-system/rpc.html |
| ServerRpc/ClientRpc are legacy and replaced by the universal Rpc attribute | https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@2.9/manual/migratingfromUNet.html |
| Only the server spawns in client-server; Network Prefabs list registration; Spawn, InstantiateAndSpawn, Despawn; clients never Destroy | https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/basics/object-spawning.html |
| NetworkTransform is server-authoritative by default; Authority Mode Owner; authoritative state overrides non-authority changes | https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/components/helper/networktransform.html |
| Distributed authority: session owner, trades security for no host | https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@3.1/manual/terms-concepts/distributed-authority.html |
| Addressables reference counting; bundles unload only when all assets are released; ReferenceCount; profiler module | https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/memory-assets.html |
| Addressables.LoadAssetAsync, AsyncOperationHandle.Release, AssetReference.ReleaseAsset | https://docs.unity3d.com/Packages/com.unity.addressables@4.1/manual/load-assets.html |
| JsonUtility: fields only, no top-level arrays, FromJsonOverwrite | https://docs.unity3d.com/Manual/json-serialization.html |
| PlayerPrefs stores int, float, string, unencrypted | https://docs.unity3d.com/ScriptReference/PlayerPrefs.html |
| BinaryFormatter is insecure and cannot be made secure | https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide |
| Cloud Save for player and game data | https://docs.unity.com/ugs/en-us/manual/cloud-save/manual |

API names verified against the official reference on 2026-10-13: NetworkVariable, NetworkVariableReadPermission, NetworkVariableWritePermission, NetworkVariable.OnValueChanged, NetworkVariable.CheckDirtyState, NetworkList, RpcAttribute, SendTo.Server, SendTo.ClientsAndHost, SendTo.Owner, RpcParams, RpcTarget.Single, NetworkObject.Spawn, NetworkSpawnManager.InstantiateAndSpawn, NetworkObject.Despawn, Addressables.LoadAssetAsync, AsyncOperationHandle.Release, AsyncOperationHandle.ReferenceCount, AssetReference.ReleaseAsset, JsonUtility.FromJsonOverwrite, PlayerPrefs.Save. Not re-fetched for 4.1 (long-standing names): Addressables.InstantiateAsync, Addressables.ReleaseInstance, AsyncOperationHandle.IsValid, Application.persistentDataPath.
