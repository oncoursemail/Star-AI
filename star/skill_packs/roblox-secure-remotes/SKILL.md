---
name: roblox-secure-remotes
description: Secure client-server communication in Roblox. Use for RemoteEvent and RemoteFunction handlers, argument validation, anti-exploit checks, rate limits and developer-product purchases.
---
# Secure RemoteEvents (the server is authoritative)
Everything a client sends is untrusted; validate on the server before use.
- The server decides authoritative prices, damage, amounts and time. OnServerEvent supplies the sender Player first; other client arguments may be accepted only as untrusted requests and must be validated before any effect.
- Check each argument: type, then range. NaN and inf are valid numbers: reject with math.isfinite(). Strings go through a server allowlist with a length cap; for an Instance check its class and place in the DataModel.
- Check context on the server: player alive, close enough (measure Magnitude yourself), owns the item, cooldown on the server clock (os.clock()).
- Rate limit per player on the server; clear it in Players.PlayerRemoving.
- Do not depend on RemoteFunction:InvokeClient for authorization or critical server progress: the client can error, disconnect or never reply. Use RemoteEvent:FireClient for asynchronous notifications instead.
- Use UnreliableRemoteEvent for transient updates that may be dropped or reordered; use RemoteEvent for state changes that need reliable ordered transport while connected, with explicit state recovery on reconnect. Recheck live payload/rate limits instead of hard-coding a disputed ceiling.
- ProcessReceipt returns PurchaseGranted only after the grant and PurchaseId are durably recorded together; return NotProcessedYet when confirmation fails or is uncertain. Replayed PurchaseIds must not grant twice.
