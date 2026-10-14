No. A client can be modified by an exploiter, so everything it sends through a RemoteEvent is untrusted and the server must validate it [1]. Check the type and range of every argument, check that the player is allowed to do the action right now, and let the server decide the outcome and the amounts [2].

---
**Sources retrieved by STAR** (official documentation)

1. [Securing the client-server boundary](https://create.roblox.com/docs/scripting/security/client-server-boundary) · cited
2. [Remote events and callbacks](https://create.roblox.com/docs/scripting/events/remote) · cited
