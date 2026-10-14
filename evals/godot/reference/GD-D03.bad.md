The RPC is probably dropped by the network. Switch the transfer mode to unreliable and call it every frame until it arrives; the client already knows the damage so the server can just apply it.
