---
name: roblox-secure-remotes
description: Secure client-server communication in Roblox. Use for RemoteEvent and RemoteFunction handlers, argument validation, anti-exploit checks, rate limits and developer-product purchases.
---
# Secure RemoteEvents (the server is authoritative)
Everything a client sends is untrusted; validate on the server before use.
- The server decides prices, damage, amounts and time. A handler takes (player, request) only: never a price, damage, position or timestamp from the client.
- Check each argument: type, then range. NaN and inf are valid numbers: reject with math.isfinite(). Strings go through a server allowlist with a length cap; for an Instance check its class and place in the DataModel.
- Check context on the server: player alive, close enough (measure Magnitude yourself), owns the item, cooldown on the server clock (os.clock()).
- Rate limit per player on the server; clear it in Players.PlayerRemoving.
- Never call RemoteFunction:InvokeClient from the server: a client can hang or lie. Use FireClient; let the client send request events.
- UnreliableRemoteEvent for frequent updates that may be lost (under 1000 bytes); RemoteEvent for what must arrive.
- ProcessReceipt returns PurchaseGranted only after the grant is saved, else NotProcessedYet; record the PurchaseId.
