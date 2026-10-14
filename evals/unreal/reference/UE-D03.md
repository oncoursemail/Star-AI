1. Clients see nothing because the property is not registered for replication. Replication needs all three: the actor replicates (`bReplicates = true` in the constructor), the property is marked `Replicated`/`ReplicatedUsing`, and the class overrides `GetLifetimeReplicatedProps`, calls `Super::GetLifetimeReplicatedProps`, includes `Net/UnrealNetwork.h` and registers it with `DOREPLIFETIME(AMyCharacter, Health)`. Also only change `Health` on the server.

2. In C++ an OnRep function runs on clients when the new value arrives; the server never receives its own replication, so it does not call it. After changing `Health` on the server, call `OnRep_Health()` manually so the listen-server host updates too (Blueprint RepNotify variables do this automatically).

Not compiled here; verify in PIE with a listen server and one client.
