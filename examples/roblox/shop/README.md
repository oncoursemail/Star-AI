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
- The thirteen pure Luau cases are run by STAR's pinned native interpreter and test forged prices, double clicks, invalid quantity, unknown IDs, insufficient funds, isolated wallets, rollback and inventories. Headless Luau tests do NOT prove Studio replication, Tool parenting or actual RemoteFunction behavior.

## Official documentation

- https://create.roblox.com/docs/scripting/events/remote
- https://create.roblox.com/docs/reference/engine/classes/RemoteFunction#OnServerInvoke
- https://create.roblox.com/docs/reference/engine/classes/ServerStorage
- https://create.roblox.com/docs/reference/engine/classes/Tool
- https://create.roblox.com/docs/reference/engine/classes/Players#PlayerRemoving
