# Roblox compilers

## Remote compiler

`star.roblox_remote_compiler.compile_remotes` is a standalone, deterministic,
standard-library-only Python compiler. It accepts a JSON string or a Python list
of message dictionaries. It does not write files, contact Roblox, register an
application tool, or import desktop code. The return value maps filenames to
UTF-8 Luau source strings:

- `Server.luau` and `Client.luau`: the two application entry modules.
- `Validators.luau` and `RateLimiter.luau`: pure-Luau support modules.
- `Remote.spec.luau`: a pure-Luau specification with injected dependencies.

### Schema

```python
from star.roblox_remote_compiler import compile_remotes

files = compile_remotes([
    {"name": "Count", "direction": "client_to_server", "reliable": True,
     "reply": True, "rate_limit": 3,
     "arguments": [{"name": "count", "type": "number", "min": 1, "max": 5}]},
    {"name": "Changed", "direction": "server_to_client", "reliable": False,
     "rate_limit": 20,
     "arguments": [{"name": "state", "type": "string", "enum": ["idle", "moving"]}]},
])
```

Each message requires `name`, `direction` (`client_to_server` or
`server_to_client`), and boolean `reliable`. `arguments` defaults to an empty
ordered list, `rate_limit` defaults to 10, and boolean `reply` defaults to false.
A reply requires a **reliable client-to-server** message; server-to-client
requests for replies and unreliable reply messages are rejected.

Argument types in this version are `number`, `string`, and `boolean`. Each
argument has a unique `name` and its `type`, with optional inclusive `min`/`max`
and a nonempty `enum`. Numeric ranges are finite. String ranges count **UTF-8
bytes**, not Unicode characters, matching Luau's `#` operator. Boolean arguments
may have an enum but not a range. A range and an enum may be combined; every enum
member must satisfy the range. Without a range or enum, the primitive type is
still checked; all numbers must still be finite. There are no optional arguments,
nullable arguments, tables, instances, or arbitrary code fragments in this schema.

Unknown fields, explicit null constraints, duplicate JSON fields, invalid types,
NaN/infinity, inverted ranges, duplicate message/argument/enum values, and generated
API name collisions raise `ValueError`. Integer literals outside
`[-(2**53 - 1), 2**53 - 1]` are rejected rather than silently rounded by Luau.
`1` and `1.0` are duplicate enum values. Unicode strings are emitted as safely
escaped UTF-8 bytes, not JSON-style `\uXXXX` sequences.

Generation limits are 64 messages, 32 arguments per message, 64 enum values per
argument, and 4096 UTF-8 bytes per string enum value. Declared string byte-length
bounds must be integers from 0 through 1,000,000. Identifiers use 1–64 ASCII
letters/digits/underscores, cannot start with a digit, and cannot be Luau keywords.
The message name `on` is reserved for handler registration. Argument names are
API labels, not generated implementation variables, so names such as `typeof`,
`math`, or `player` cannot shadow validation code.

### Installation and API

Place `Server`, `Validators`, and `RateLimiter` as sibling ModuleScripts in a
server-only folder. Place `Client` and a copy of the same generated `Validators`
as siblings in client-accessible storage. The support modules contain only schema
checks and limiter logic; keep trusted game handlers in server code. Require one
server-module copy before clients begin using the protocol. Roblox's normal
ModuleScript require caching provides the singleton initialization boundary.

The server creates or reuses the `ReplicatedStorage.StarRemotes` folder and one
correctly named instance per message. Reliable events use `RemoteEvent`,
unreliable events use `UnreliableRemoteEvent`, and reply messages use
`RemoteFunction`. Existing instances must have the exact expected class. Creation
and binding do not yield after support modules are loaded; no remote instance is
created inside an invocation handler. Independent protocols must not install
multiple server-module copies into this same fixed namespace.

Register trusted incoming handlers with `server.on("Count", callback)`. The
callback receives the engine-supplied player followed by the message arguments.
Unknown/outgoing names, non-function handlers, and duplicate registrations fail.
For outgoing messages, call `server.Changed(player, "idle")`; it returns true on
send, or `nil, error_code` on rejection. The typed client provides
`client.Count(count)` and `client.on_Changed(callback)`. Listener registration
returns an `RBXScriptConnection` for the caller to disconnect. String/boolean enums
appear as singleton unions in the exported client type. Reply values remain an
opaque `...any` tuple because the input schema does not describe return types.

Every incoming server dispatch checks exact argument count, each argument's
`typeof`, finite numbers, and constraints **before handler lookup or execution**.
Additional arguments, including an extra trailing nil, are rejected. Outgoing
server sends and client wrappers also validate payloads; client event callbacks
run only after incoming payload validation. Client remote lookups use explicit
10-second timeouts and verify instance classes. These are shape and transport
checks, not authorization: handlers must still enforce authoritative game state,
permissions, ownership, inventory, and other domain rules.

### Rate limits and lifecycle

`rate_limit` is an integer from 1 through 10,000, counted per player **and message**
in a one-second fixed window beginning with that player's first accepted attempt.
Both client-to-server calls and server-to-client sends consume their respective
quotas. Boundary-adjacent windows may allow a burst spanning two windows; this is
not a sliding-window or average-rate guarantee. Malformed payloads do not allocate
buckets. Valid attempts without a registered handler still consume quota.

`PlayerRemoving` removes all limiter buckets for the player and aborts pending
invocations. A weak departing-player set prevents a late queued callback from
recreating a bucket even while the player still has `Players` as its parent.
Other players and other message names have independent windows. The pure limiter
accepts explicit timestamps so tests do not sleep; backward/non-finite clocks are
rejected.

### Bounded handlers and replies

All incoming handlers, including event handlers, run in a protected deferred
worker. A five-second timer is armed **before** scheduling that worker. Normal
completion preserves the complete return tuple, including false values and
interior/trailing nils. Failure codes are `invalid_arguments`, `rate_limited`,
`no_handler`, `player_left`, `handler_error`, and `timeout`; raw handler errors
never cross the remote. Events discard replies as usual.

On timeout or departure the wrapper attempts to cancel the suspended worker,
settles the caller once, and destroys its waiting event. Successful calls cancel
their timers and release pending-call records. The server never invokes
`InvokeClient`. The timeout is a **cooperative scheduler deadline**, not a hard
wall-clock preemption guarantee: CPU-bound handlers can block the scheduler,
cancellation cannot undo earlier side effects, and independently spawned child
tasks are not automatically canceled. Keep trusted handlers bounded and make
state changes idempotent; use a separate event request/response protocol for long
work. The generated client calls `InvokeServer` directly; it does not add an
independent network/transport deadline beyond the server-side handler timeout.

### Verification

`tests/test_roblox_remote_compiler.py` executes schema normalization and generation,
compares all five outputs against checked-in full-file goldens, checks that every
dispatch follows a fail-closed guard grammar, and mutates that grammar to verify
the checker rejects bypasses. It also checks the typed client interface and pure
spec generation. An optional native-Luau test runs the generated spec when the
`luau` executable is already installed; it does not download a runtime.

`tests/test_roblox_remote_compiler_runtime.py` additionally executes the unchanged
generated server, validators, limiter, and specs using an installed Lua 5.4 shared
library with deterministic service/scheduler doubles. These modules intentionally
use a shared Lua/Luau syntax subset; **this compatibility execution is not a native
Luau typecheck or a Roblox Studio run**. The test skips when that optional local
library is absent. It covers invalid packets, rate-limit boundaries/isolation,
remote reuse/class mismatches, reply tuples, errors, timeout races, departure,
and cleanup, and verifies that removing a validation guard reaches a handler.
No test needs a network, GPU, real player account, or keyring.

For a standalone native Luau run, save the emitted files together and add
`run.luau` with:

```lua
local run = require("./Remote.spec")
assert(run(require("./Validators"), require("./RateLimiter")))
```

Run `luau run.luau`. In Roblox, require the spec ModuleScript and pass the two
support modules to the returned function instead. The spec itself depends on
neither `script`, `game`, nor a test framework. Native client typechecking and
real-engine integration remain separate acceptance checks.

API references: [Luau syntax and number/string literals](https://luau.org/syntax/),
[Roblox task scheduling](https://create.roblox.com/docs/reference/engine/libraries/task),
and [RemoteFunction](https://create.roblox.com/docs/reference/engine/classes/RemoteFunction).
