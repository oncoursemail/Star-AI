A MessagingService message can be at most 1,024 characters (1 KiB), and a topic name at most 80 characters [1]. Each game server may send 600 + 240 * (the number of players in that server) messages per minute; beyond that, calls are throttled, so batch updates and wrap `PublishAsync` in `pcall` [1][2].

---
**Sources retrieved by STAR** (official documentation)

1. [MessagingService](https://create.roblox.com/docs/reference/engine/classes/MessagingService) · cited
2. [Cross-server messaging](https://create.roblox.com/docs/cloud-services/cross-server-messaging) · cited
