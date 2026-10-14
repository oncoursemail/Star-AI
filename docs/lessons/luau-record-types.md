# Named Luau record types and ModuleScript contracts — correction candidates

Status: unreviewed candidate reference

These 12 original examples are **teaching candidates**, not imported into STAR's lessons or enabled skill packs. Their status is not a claim that STAR generated them or that they fix the 24 reported compilation/type-check occurrences in the night-school snapshot. The snapshot's reported count is a motivation, not an independently verified distribution. The checked-in night-school report generator groups failures under their first failed check; it cannot establish which of the categories here is most common without reviewing underlying examples.

## Taxonomy and boundaries

- RT-01–RT-03: missing named record/dictionary aliases in moving-platform, checkpoint and inventory code.
- RT-04–RT-06: exported ModuleScript type visibility, imported type qualification and re-exporting a type rather than a table value.
- RT-07: confusing a compile-time alias with a runtime ModuleScript value.
- RT-08–RT-09 and RT-11: scalar, branched-record and function return contracts.
- RT-10: optional named record value; RT-12: incompatible local versus imported record shapes. Luau is structurally typed; a matching name alone does not make two shapes equivalent.

Each **Incorrect** block illustrates its failure in the described context; each **Corrected** block illustrates the intended fix. `pure-luau-illustrative` snippets have no Roblox engine globals and can be inspected by the standalone Luau tools. `multi-file-illustrative` snippets use `-- File:` dividers that represent separate ModuleScripts/Scripts, **not one executable file**; these require project-aware Studio type checking. The static **Witness** substring only checks whether the designated correction appears. It cannot prove type correctness, Roblox behavior, or that there are no other errors. Do not promote these records or change STAR's inference from them without independently validated improvements.

## Tool and delivery comparison

| Approach | Licence/upkeep/cost | Verification burden | Decision |
| --- | --- | --- | --- |
| Bounded Markdown candidate file + read-only Python loader | New STAR-owned teaching text; no extra third-party package or paid call. Maintain the 12 examples and official documentation links. Official Luau CLI is MIT-licensed and already checksum-pinned in STAR. | Deterministic loader/witness regressions plus existing native Luau spec runner; real Studio still needed for multi-file module types. | **Chosen:** no runtime or prompt behavior changes. |
| Extend opt-in `eng-debugging` skill pack | That pack already attributes MIT-licensed upstream debugging material; no purchase, but increased prompt tokens and overlapping selector guidance. | Review active instructions, selection, prompt-isolation and downstream answer quality; text alone is not proof of improvement. | Not changed; avoid repeating its NPC lessons. |
| Enable night-school worked-example retrieval | Existing STAR-owned pipeline without an added dependency or licence fee; requires storage, curation and maintained verification. | Retest samples, check provenance, compare fixed training and held-out validation before trusting examples. | Deferred until these candidates are validated. |

Official authoritative primary references: [Roblox Luau type checking](https://create.roblox.com/docs/luau/type-checking), [Luau syntax](https://luau.org/syntax/), and [Roblox ModuleScript](https://create.roblox.com/docs/reference/engine/classes/ModuleScript). These sources cover the specific alias, export, parameter/return, optional and single-module-return contracts cited in each entry. Links are pointers to documentation, not a copied corpus. New code introduces no automatic lesson promotion and no Studio-success claims.

### RT-01: Moving platform missing named record
**Context:** Moving-platform movement state in a server-side controller.
**Failure:** Unknown type PlatformMotion: a record name in an annotation is not created by assigning a table value.
**Correction:** Declare a file-local type alias describing the platform record before using it.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** pure-luau-illustrative
**Witness:** type PlatformMotion = {
**Incorrect (Luau):**
```luau
--!strict
local motion: PlatformMotion = {active = false, speed = 8}
return motion
```
**Corrected (Luau):**
```luau
--!strict
type PlatformMotion = {active: boolean, speed: number}
local motion: PlatformMotion = {active = false, speed = 8}
return motion
```

### RT-02: Checkpoint map missing numeric index type
**Context:** A server-owned checkpoint index keyed by player user IDs (represented as numbers, without Roblox globals).
**Failure:** Unknown type CheckpointByUser: the map annotation names an undeclared type.
**Correction:** Define a dictionary alias with number keys and number checkpoint values, then use that alias.
**Source:** https://luau.org/syntax/
**Verification:** pure-luau-illustrative
**Witness:** type CheckpointByUser = {
**Incorrect (Luau):**
```luau
--!strict
local stages: CheckpointByUser = {[10] = 2}
return stages
```
**Corrected (Luau):**
```luau
--!strict
type CheckpointByUser = {[number]: number}
local stages: CheckpointByUser = {[10] = 2}
return stages
```

### RT-03: Inventory entry missing named shape
**Context:** Inventory item records used by server-authoritative item bookkeeping.
**Failure:** Unknown type InventoryEntry: naming an inventory record does not declare its shape.
**Correction:** Define InventoryEntry as a record with itemId and quantity fields of the proper types.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** pure-luau-illustrative
**Witness:** type InventoryEntry = {
**Incorrect (Luau):**
```luau
--!strict
local entry: InventoryEntry = {itemId = "potion", quantity = 3}
return entry
```
**Corrected (Luau):**
```luau
--!strict
type InventoryEntry = {itemId: string, quantity: number}
local entry: InventoryEntry = {itemId = "potion", quantity = 3}
return entry
```

### RT-04: Export the shared inventory type
**Context:** ReplicatedStorage/ItemTypes ModuleScript with a separate inventory consumer Script.
**Failure:** A file-local type Item is invisible to a second script importing ItemTypes.Item.
**Correction:** Declare export type Item in the ModuleScript; require that module in the consumer for its qualified type name.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** multi-file-illustrative
**Witness:** export type Item = {
**Incorrect (Luau):**
```luau
-- File: ReplicatedStorage/ItemTypes (ModuleScript)
--!strict
type Item = {id: string, count: number}
return {}
-- File: ServerScriptService/Inventory (Script)
--!strict
local ItemTypes = require(game.ReplicatedStorage.ItemTypes)
local item: ItemTypes.Item = {id = "potion", count = 1}
```
**Corrected (Luau):**
```luau
-- File: ReplicatedStorage/ItemTypes (ModuleScript)
--!strict
export type Item = {id: string, count: number}
return {}
-- File: ServerScriptService/Inventory (Script)
--!strict
local ItemTypes = require(game.ReplicatedStorage.ItemTypes)
local item: ItemTypes.Item = {id = "potion", count = 1}
```

### RT-05: Qualify an imported type at the use site
**Context:** Consumer of an exported checkpoint-state type in a shared ModuleScript.
**Failure:** Unknown type State in the consumer: require binds a module value, not a top-level type named State in this file.
**Correction:** Use CheckpointTypes.State after requiring CheckpointTypes; the type remains namespaced.
**Source:** https://luau.org/syntax/
**Verification:** multi-file-illustrative
**Witness:** local record: CheckpointTypes.State
**Incorrect (Luau):**
```luau
-- File: ReplicatedStorage/CheckpointTypes (ModuleScript)
--!strict
export type State = {stage: number}
return {}
-- File: ServerScriptService/CheckpointConsumer (Script)
--!strict
local CheckpointTypes = require(game.ReplicatedStorage.CheckpointTypes)
local record: State = {stage = 1}
```
**Corrected (Luau):**
```luau
-- File: ReplicatedStorage/CheckpointTypes (ModuleScript)
--!strict
export type State = {stage: number}
return {}
-- File: ServerScriptService/CheckpointConsumer (Script)
--!strict
local CheckpointTypes = require(game.ReplicatedStorage.CheckpointTypes)
local record: CheckpointTypes.State = {stage = 1}
```

### RT-06: Re-export a ModuleScript type, not its table value
**Context:** ModuleScript facade that re-exports a data shape from a shared save-state module.
**Failure:** The imported State name is a runtime table; export type Snapshot = State does not name a type.
**Correction:** Re-export the actual exported alias State.Snapshot instead.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** multi-file-illustrative
**Witness:** export type Snapshot = State.Snapshot
**Incorrect (Luau):**
```luau
-- File: ReplicatedStorage/SaveState (ModuleScript)
--!strict
export type Snapshot = {level: number}
return {}
-- File: ReplicatedStorage/SaveFacade (ModuleScript)
--!strict
local State = require(script.Parent.SaveState)
export type Snapshot = State
return {}
```
**Corrected (Luau):**
```luau
-- File: ReplicatedStorage/SaveState (ModuleScript)
--!strict
export type Snapshot = {level: number}
return {}
-- File: ReplicatedStorage/SaveFacade (ModuleScript)
--!strict
local State = require(script.Parent.SaveState)
export type Snapshot = State.Snapshot
return {}
```

### RT-07: A type alias cannot be returned as a runtime constructor
**Context:** Receipt factory ModuleScript used by a shop backend.
**Failure:** The type-only alias Receipt is not a runtime variable that a ModuleScript can return.
**Correction:** Return a real table of functions and annotate the constructed record with Receipt.
**Source:** https://create.roblox.com/docs/reference/engine/classes/ModuleScript
**Verification:** pure-luau-illustrative
**Witness:** return {makeReceipt = function(
**Incorrect (Luau):**
```luau
--!strict
type Receipt = {itemId: string}
return Receipt
```
**Corrected (Luau):**
```luau
--!strict
type Receipt = {itemId: string}
return {makeReceipt = function(itemId: string): Receipt
    return {itemId = itemId}
end}
```

### RT-08: Named currency return type must match actual value
**Context:** Reward amount function in a tycoon currency module.
**Failure:** Function annotated to return CoinBalance (number) returns a string instead.
**Correction:** Return a number, preserving the exported function's declared return contract.
**Source:** https://luau.org/syntax/
**Verification:** pure-luau-illustrative
**Witness:** return 75
**Incorrect (Luau):**
```luau
--!strict
type CoinBalance = number
local function reward(): CoinBalance
    return "75"
end
return reward
```
**Corrected (Luau):**
```luau
--!strict
type CoinBalance = number
local function reward(): CoinBalance
    return 75
end
return reward
```

### RT-09: Every branch must return the named round record
**Context:** Round-start decision helper used in a multiplayer arena loop.
**Failure:** The success branch returns boolean, while the declared RoundDecision record needs allowed and reason fields.
**Correction:** Return the same record shape on both branches; do not make a mixed return contract.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** pure-luau-illustrative
**Witness:** return {allowed = true, reason = ""}
**Incorrect (Luau):**
```luau
--!strict
type RoundDecision = {allowed: boolean, reason: string}
local function decide(players: number): RoundDecision
    if players < 2 then return {allowed = false, reason = "waiting"} end
    return true
end
return decide
```
**Corrected (Luau):**
```luau
--!strict
type RoundDecision = {allowed: boolean, reason: string}
local function decide(players: number): RoundDecision
    if players < 2 then return {allowed = false, reason = "waiting"} end
    return {allowed = true, reason = ""}
end
return decide
```

### RT-10: Unequipped inventory slot needs an optional named type
**Context:** An empty selected inventory slot before the player equips an item.
**Failure:** An annotation of EquippedItem alone does not permit nil at initialization.
**Correction:** Use EquippedItem? for a slot whose valid states are a record or nil.
**Source:** https://luau.org/syntax/
**Verification:** pure-luau-illustrative
**Witness:** local equipped: EquippedItem? = nil
**Incorrect (Luau):**
```luau
--!strict
type EquippedItem = {itemId: string}
local equipped: EquippedItem = nil
return equipped
```
**Corrected (Luau):**
```luau
--!strict
type EquippedItem = {itemId: string}
local equipped: EquippedItem? = nil
return equipped
```

### RT-11: ModuleScript function must satisfy its typed return contract
**Context:** An inventory-builder ModuleScript returning an implementation table.
**Failure:** The declared create function returns an InventoryRecord but its implementation returns a string.
**Correction:** Return an InventoryRecord from the implementation and keep the module table annotated to its contract.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** pure-luau-illustrative
**Witness:** return {itemId = "potion", count = 1}
**Incorrect (Luau):**
```luau
--!strict
type InventoryRecord = {itemId: string, count: number}
type InventoryBuilder = {create: () -> InventoryRecord}
local builder: InventoryBuilder = {
    create = function(): string
        return "potion"
    end,
}
return builder
```
**Corrected (Luau):**
```luau
--!strict
type InventoryRecord = {itemId: string, count: number}
type InventoryBuilder = {create: () -> InventoryRecord}
local builder: InventoryBuilder = {
    create = function(): InventoryRecord
        return {itemId = "potion", count = 1}
    end,
}
return builder
```

### RT-12: A local alias is not the imported inventory record
**Context:** Script with its own type Item while a shared ModuleScript also exports Item.
**Failure:** The local Item record has coins:number, which is incompatible with imported SharedTypes.Item requiring itemId:string; aliases are structurally checked, not nominally identical by spelling.
**Correction:** Refer to the exported alias with SharedTypes.Item rather than accidentally keeping an incompatible same-named local shape.
**Source:** https://create.roblox.com/docs/luau/type-checking
**Verification:** multi-file-illustrative
**Witness:** type Item = SharedTypes.Item
**Incorrect (Luau):**
```luau
-- File: ReplicatedStorage/SharedTypes (ModuleScript)
--!strict
export type Item = {itemId: string}
return {}
-- File: ServerScriptService/Inventory (Script)
--!strict
local SharedTypes = require(game.ReplicatedStorage.SharedTypes)
type Item = {coins: number}
local entry: Item = {coins = 2}
local function save(item: SharedTypes.Item) end
save(entry)
```
**Corrected (Luau):**
```luau
-- File: ReplicatedStorage/SharedTypes (ModuleScript)
--!strict
export type Item = {itemId: string}
return {}
-- File: ServerScriptService/Inventory (Script)
--!strict
local SharedTypes = require(game.ReplicatedStorage.SharedTypes)
type Item = SharedTypes.Item
local entry: Item = {itemId = "potion"}
local function save(item: SharedTypes.Item) end
save(entry)
```

## Independent verification still required

The offline witness tests assert that **all 12 designated corrections** are missing from the incorrect sample and present in the corrected sample; this is a bounded structural check, **not** a typechecker success. The native pinned Luau spec suite exercises corresponding *pure language* alias/return patterns, not copied per-case compilation. Roblox ModuleScript `require` resolution and type names need Studio or a project-aware analyzer. No held-out improvement, model response speed, Studio simulation or model-weight change has been measured.
