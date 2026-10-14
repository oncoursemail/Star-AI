A plain `@rpc` uses the defaults `("authority", "call_remote", "reliable", 0)`. In "authority" mode only the node's multiplayer authority (the server, peer 1, by default) may call it remotely, so a client's call is rejected.

Fix: declare it `@rpc("any_peer", "reliable")`. Because now anyone can call it, validate on the server:
- `var sender := multiplayer.get_remote_sender_id()` and check that this peer controls the attacking character.
- Check range, cooldown and that the target exists.
- Do not accept `damage` from the client: the server should compute damage from the weapon it knows the player has, then apply it.

Not run; test with two instances (Debug > Run Multiple Instances).
