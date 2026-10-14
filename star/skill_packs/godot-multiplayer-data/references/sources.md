# Sources for godot-multiplayer-data

Checked against the official Godot documentation (stable = Godot 4.7) on 2026-10-13. The Godot documentation is CC BY 3.0
(class reference MIT); the guidance is written in STAR's own words. Deeper reference: docs/research/engines/godot.md.

| Claim in the skill | Documentation page |
|---|---|
| ENet host/client, server is peer 1, UDP only, connection signals | https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html |
| @rpc defaults ("authority", "call_remote", "reliable", 0), any_peer, call_local, transfer modes | https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html |
| get_remote_sender_id, set_multiplayer_authority | https://docs.godotengine.org/en/stable/classes/class_multiplayerapi.html and https://docs.godotengine.org/en/stable/classes/class_node.html |
| Same NodePath and same RPC set on every peer (checksum); no Objects or Callables as arguments | https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html |
| MultiplayerSpawner spawn_path, spawnable scenes, spawn_function, spawned/despawned on remote peers | https://docs.godotengine.org/en/stable/classes/class_multiplayerspawner.html |
| MultiplayerSynchronizer replication config and visibility | https://docs.godotengine.org/en/stable/classes/class_multiplayersynchronizer.html |
| ENetMultiplayerPeer create_server / create_client | https://docs.godotengine.org/en/stable/classes/class_enetmultiplayerpeer.html |
| user:// for saves, res:// read-only after export | https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html |
| JSON / store_var save approaches, ConfigFile for settings | https://docs.godotengine.org/en/stable/tutorials/io/saving_games.html and https://docs.godotengine.org/en/stable/classes/class_configfile.html |
| get_var(allow_objects) warning: deserialized objects can contain code; FileAccess.open returns null, get_open_error | https://docs.godotengine.org/en/stable/classes/class_fileaccess.html |
| Runtime loading of external files | https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html |

The risk that a .tres/.res file can embed a script that runs on load is not stated on the resource pages; it follows from the
FileAccess.get_var warning and is widely reported by the community (for example https://github.com/derkork/godot-safe-resource-loader).

API names verified against the official reference on 2026-10-13: ENetMultiplayerPeer.create_server, ENetMultiplayerPeer.create_client,
MultiplayerAPI.get_remote_sender_id, MultiplayerAPI.multiplayer_peer, Node.set_multiplayer_authority, Node.is_multiplayer_authority,
Node.rpc, Node.rpc_id, MultiplayerSpawner.spawn_path, MultiplayerSpawner.spawn_function, MultiplayerSpawner.spawn,
MultiplayerSynchronizer.replication_config, FileAccess.open, FileAccess.get_open_error, FileAccess.get_var, JSON.stringify,
JSON.parse_string, ConfigFile.
No live Godot editor run is claimed.
