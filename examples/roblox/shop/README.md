# Example shop — server-validated purchases and once-only inventory

**Standalone example, not enabled in STAR or any live game.** Copy to an unpublished Roblox Studio place and test on two clients. All money and ownership live on the server.

## Required Studio tree

- `ReplicatedStorage/ShopCatalog` — ModuleScript containing the public display prices.
- `ServerStorage/ShopTools` — Folder containing three Tools named `WoodenSword`, `BlueLantern` and `HealingKit`, each with a valid `Handle` where appropriate. Never put sellable Tool instances into ReplicatedStorage.
- `ServerScriptService/Inventory`, `ShopCore`, `ShopServer` — two pure ModuleScripts and one server Script. The server creates `ReplicatedStorage.PurchaseItem` as a RemoteFunction.
- `StarterPlayer/StarterPlayerScripts/ShopClient` — LocalScript showing native buttons. It sends only an item ID and the fixed quantity 1.

## What this example guarantees and does not

- The client never controls the price. The server validates item ID, quantity, wallet balance and ownership. It seeds 250 demonstration coins and uses the server's own copied catalog; repeat purchases are refused.
- The server prepares a Tool clone before committing a purchase, then confirms it only after granting to Backpack; a failed grant calls the pure `ShopCore.rollback` exactly once.
- On respawn, the server re-grants owned Tools when missing. `leaderstats.Coins` displays balance, but is not the authority for funds.
- Inventory and coins are **session-only** and reset after leaving: no real currency, DataStore, Robux, MarketplaceService or ProcessReceipt claims. Do not use this sample for paid developer products.
- `Tests/ShopCore.spec.luau` (13 cases) and `Tests/ShopSequence.spec.luau` (8 additional cases) execute the **actual pure ShopCore** on the pinned native Luau CLI. Multi-action cases cover repeated purchases, pending/confirmed/rolled-back grants, departure and reseed, two players purchasing the same item, hostile quantities and prices, and a fixed-seed 144-action three-player reference model. A deliberately incorrect double-debit implementation is confirmed to fail the duplicate-purchase invariant.
- Impossible **server-internal** corruption of pending ownership, price or wallet raises an explicit invariant error **before** `rollback` can alter money or discard pending evidence. This is distinct from routine malformed client input, which is refused without changing state. It is not a recovery mechanism for invalid persistent saves.
- These headless Luau tests do **not** prove Studio replication, Tool parenting, real RemoteFunction behavior or successful grant/rollback across Roblox engine boundaries. A two-client Studio playtest is still required.

## Official documentation

- https://create.roblox.com/docs/scripting/events/remote
- https://create.roblox.com/docs/reference/engine/classes/RemoteFunction#OnServerInvoke
- https://create.roblox.com/docs/reference/engine/classes/ServerStorage
- https://create.roblox.com/docs/reference/engine/classes/Tool
- https://create.roblox.com/docs/reference/engine/classes/Players#PlayerRemoving
