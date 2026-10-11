# Roblox compilers

## Remote compiler

The standalone `star.roblox_remote_compiler.compile_remotes` accepts a JSON string or a Python list of message objects and returns five deterministic Luau source strings: `Server.luau`, `Client.luau`, `Validators.luau`, , `RateLimiter.luau`, and `Remote.spec.luau`. This pure-Python generator is not connected to the desktop app.

Each message has `name` (safe Luau identifier), `direction` (`client_to_server` or `server_to_client`), `reliable` (boolean), `arguments` (ordered list), optional `rate_limit` (1–10000 messages per second per player; default 10), and optional `reply` (boolean; default false). Reply is allowed only for reliable client-to-server messages. Each argument has a unique `name`, `type` (`string`, `number`, or `boolean`), optional `min`/`max` (numeric bounds, or string length bounds), and optional nonempty `enum`.

Example:

```python
from star.roblox_remote_compiler import compile_remotes

files = compile_remotes([
    {"name": "Buy", "direction": "client_to_server", "reliable": True,
     "reply": True, "rate_limit": 3,
     "arguments": [{"name": "quantity", "type": "number", "min": 1, "max": 5}]},
])
```

Place `Server.luau`, `Validators.luau`, and `RateLimiter.luau` as sibling ModuleScripts under ServerScriptService and `Client.luau` in client-accessible code. Require the server module once before clients access the generated functions. The server creates or reuses instances inside `ReplicatedStorage.StarRemotes` and verifies their classes. Register trusted handlers with `server.on("Buy", callback)`; the wrapper checks `typeof`, constraints and per-player quota before looking up and executing the handler.

The per-player limiter clears buckets on `PlayerRemoving`. Remote functions execute in a detached protected task and unblock callers after five seconds even when a handler yields. **A timed-out handler is not forcibly cancelled** and can continue executing; design sensitive operations to be idempotent and cancellation-aware. An async request/response event protocol is preferable for long tasks. This generated code never invokes `InvokeClient`. Validators and the limiter are separate pure-Luau modules, with `Remote.spec.luau` providing runnable pure-Luau assertions. The Python tests assert generated output and guard-ordering; they do not constitute Luau runtime execution.
