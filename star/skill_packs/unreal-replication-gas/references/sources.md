# Sources for unreal-replication-gas

Checked against the official Unreal Engine documentation (labelled 5.8) on 2026-10-13. Epic's documentation is not openly
licensed: the guidance is written in STAR's own words and only links to the pages. Deeper reference: docs/research/engines/unreal.md.

| Claim in the skill | Documentation page |
|---|---|
| Server-authoritative model, net modes | https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine |
| Roles: Authority, AutonomousProxy, SimulatedProxy | https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-role-and-remote-role-in-unreal-engine |
| bReplicates, Replicated / ReplicatedUsing, GetLifetimeReplicatedProps, DOREPLIFETIME and conditions, REPNOTIFY_Always | https://dev.epicgames.com/documentation/en-us/unreal-engine/replicate-actor-properties-in-unreal-engine |
| Server / Client / NetMulticast RPCs, _Implementation, Reliable, WithValidation disconnects, ownership matrix (Server RPC on an unowned actor is dropped) | https://dev.epicgames.com/documentation/en-us/unreal-engine/remote-procedure-calls-in-unreal-engine |
| Ownership and owning connection | https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-owner-and-owning-connection-in-unreal-engine |
| Relevancy and update frequency | https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-relevancy-in-unreal-engine |
| Iris is opt-in (bUseIris, SetupIrisSupport) | https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-iris-in-unreal-engine |
| Gameplay Ability System overview and components | https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/understanding-the-unreal-engine-gameplay-ability-system |
| Attribute sets and attributes | https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine |
| Gameplay effects | https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-effects-for-the-gameplay-ability-system-in-unreal-engine |
| USaveGame and SaveGameToSlot | https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UGameplayStatics/SaveGameToSlot |

The C++ OnRep server-side behaviour, the ASC-on-PlayerState pattern, InitAbilityActorInfo timing and the replication modes are
long-standing engine behaviour documented in the API reference (UAbilitySystemComponent) and the Lyra sample
(https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine), not spelled out on the overview pages.

API names verified against the official reference on 2026-10-13: HasAuthority, GetLocalRole, ROLE_Authority, ROLE_AutonomousProxy,
ROLE_SimulatedProxy, GetLifetimeReplicatedProps, DOREPLIFETIME, DOREPLIFETIME_CONDITION, DOREPLIFETIME_CONDITION_NOTIFY,
COND_OwnerOnly, REPNOTIFY_Always, UFUNCTION(Server), UFUNCTION(Client), UFUNCTION(NetMulticast), Reliable, WithValidation,
SetOwner, UAbilitySystemComponent, IAbilitySystemInterface, InitAbilityActorInfo, SetReplicationMode, GiveAbility,
FGameplayAttributeData, GAMEPLAYATTRIBUTE_REPNOTIFY, USaveGame, UGameplayStatics::AsyncSaveGameToSlot, LoadGameFromSlot.
No compile or editor run is claimed.
