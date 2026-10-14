---
name: godot-multiplayer-data
description: Godot 4 high-level multiplayer (ENet peers, @rpc modes, multiplayer authority, MultiplayerSpawner and MultiplayerSynchronizer, server validation) and safe save data in user://. Use for Godot networking, RPC errors, replication that does not appear on clients, or saving and loading game state.
---
# Godot 4 multiplayer and save data (the server decides)
- Host: ENetMultiplayerPeer.create_server(port, max_clients); client: create_client(address, port); assign to multiplayer.multiplayer_peer and check the returned Error. The server is peer 1. ENet is UDP only.
- @rpc defaults to ("authority", "call_remote", "reliable", 0). A client-to-server request needs @rpc("any_peer"); add "call_local" when the host also plays; use "unreliable" or "unreliable_ordered" for frequent state. Call with f.rpc(args) or f.rpc_id(1, args).
- Validate every any_peer RPC on the server: sender = multiplayer.get_remote_sender_id(); check the sender owns the character, range, cooldown and amounts. Never accept damage, price or position from a client as truth (same rule as Roblox OnServerEvent).
- RPCs need the same NodePath and the same set of @rpc functions on every peer: name nodes deterministically (add_child(node, true), name players after their peer id) and declare every RPC on both sides. Arguments are plain data, never Objects or Callables.
- Authority: set_multiplayer_authority(id) the same way on every peer (for example in _enter_tree from the node name); test is_multiplayer_authority() before reading input. Keep health and score server-owned.
- MultiplayerSpawner replicates only scenes in its spawnable list, added by the authority as direct children of spawn_path; spawn_function plus spawn(data) for custom spawns. MultiplayerSynchronizer sends only properties in its replication config, from its authority; use visibility filters for interest management.
- Peers: peer_connected, peer_disconnected, connected_to_server, connection_failed, server_disconnected. Dedicated server: --headless and OS.has_feature("dedicated_server").
- Saves go to user:// (res:// is read-only after export). Use JSON (JSON.stringify, JSON.parse_string), ConfigFile for settings, or store_var/get_var with allow_objects false. Never load a player-editable .tres or .res save: resources can embed scripts that run on load. FileAccess.open returns null on failure; read FileAccess.get_open_error(). Write to a temp file, then rename; store a version number.
- Godot has no hosted servers or cloud data store: online saves need your own backend.
