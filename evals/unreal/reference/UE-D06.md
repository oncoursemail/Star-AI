For player characters put the `UAbilitySystemComponent` on the `PlayerState`. The PlayerState survives the pawn's death, so cooldowns, granted abilities and attributes persist across respawns; the character implements `IAbilitySystemInterface` and returns the PlayerState's component. Raise the PlayerState's `NetUpdateFrequency` because it replicates slowly by default.

Initialise the actor info on both sides with `InitAbilityActorInfo(PlayerState, Character)` (owner = PlayerState, avatar = the pawn): on the server in `PossessedBy`, and on the owning client in `OnRep_PlayerState`. Without the client call, local prediction and activation fail.

Use `SetReplicationMode(EGameplayEffectReplicationMode::Mixed)` for player-controlled characters (Minimal for AI, Full for single player), and grant abilities only on the server with `GiveAbility`. Not compiled or run here.
