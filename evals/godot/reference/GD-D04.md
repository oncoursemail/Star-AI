A `MultiplayerSpawner` only replicates nodes that match all of these:

1. The scene is in the spawner's spawnable list (set it in the inspector or with `add_spawnable_scene("res://player.tscn")`).
2. The node is added as a direct child of the node that `spawn_path` points to. Adding it under the root, when `spawn_path` points at `Players`, is not seen.
3. Only the server (the spawner's authority) adds it; clients must not add their own copy.
4. The spawner and the `spawn_path` node exist at the same paths on the clients.

Fix: `$Players.add_child(player, true)` on the server only, with the player scene in the list. For state, add a `MultiplayerSynchronizer` to the player scene. Not run; check the Remote tree on a client.
