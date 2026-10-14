# Luau server/client trust warnings (opt-in)

The existing tokenizer-based linter is in `star/luau_lint.py`. The optional
`star/luau_server_security.py` scanner adds targeted client-input security warnings
without executing code, launching Roblox Studio, or accessing the network.

## Enable and output

Call `star.luau_lint.lint(source, server_security=True)` or
`star.luau_server_security.lint_server_trust(source)`. The default
`lint(source)` is unchanged and emits **no SEC- findings**. This is a per-call
opt-in switch, not a globally enabled setting or an automatic answer-time audit.
The output is the existing immutable `Finding(rule_id, line, message,
suggested_fix, severity)` type, sorted deterministically by line and rule ID.
All new findings have severity `warning`; none automatically execute or repair
untrusted code.

| Rule | Recognized unsafe sink | Guarding pattern or remediation |
| --- | --- | --- |
| `SEC-CLIENT-AMOUNT` | Client number added to/subtracted from a server currency balance, or passed to `IncrementAsync` | Server-side `typeof`/`type` check **and** a bounded range (or typed, clamped local alias); calculate rewards on the server |
| `SEC-CLIENT-PRICE` | Client `price`/`cost` used in balance adjustment, even when type/range-checked | Select the authoritative price from a server-owned catalogue based on a validated item identifier |
| `SEC-INSTANCE-OWNERSHIP` | Client Instance mutated through `Destroy`, `PivotTo`, `SetAttribute`, `ClearAllChildren`, `BreakJoints`, or property assignment | Check actual Instance type and expected class; guard with `instance:IsDescendantOf(player.Character)` or appropriate `Parent` comparison |
| `SEC-DATASTORE-CLIENT-KEY` | Client-supplied argument (including simple copies/concatenations) used as the first key argument to `GetAsync`, `SetAsync`, `UpdateAsync`, `RemoveAsync`, `IncrementAsync` | Build keys from server-owned `player.UserId`, or limit to a **server-owned** explicit allow-list |
| `SEC-REMOTE-ALLOWLIST` | Client identifier writes to indexed `Inventory`/`Data`/`Profile`/`Owned`/`Entitlements` table | Check the identifier against a server-owned `ALLOWED_KEYS`/`CATALOG`/`PRODUCTS` table before writing |

Both inline forms are recognized:
`remote.OnServerEvent:Connect(function(player, request) ... end)` and
`remote.OnServerInvoke = function(player, request) ... end`. The first argument
is treated as the server-supplied player; subsequent arguments are untrusted.
A warning is issued only at a recognized sensitive operation. Logging a client
argument does not itself trigger a SEC- rule. Comments and strings are skipped.

### Limits and cautions

This is intentionally **not** full Luau syntax parsing, interprocedural taint
tracking, or a security guarantee. Named remote callbacks, advanced aliases,
module-level forwarding, helper validation functions, authorization state,
nested tables, multi-line transformations, and complex control flow may evade
detection or produce review-worthy false positives. A name-based catalogue
heuristic assumes the table is server-owned; the tool cannot prove that.
A character-ownership guard may also be wrong for non-character objects.

A type check and two-sided numeric range check alone do **not** reject NaN;
production Luau must also reject NaN/infinity as documented by Roblox, and
verify permissions, action distance, rate limits, item ownership and context
server-side. An Instance type check by itself never proves authorization.
When the scanner is uncertain, manually audit the remote boundary.

## Existing tooling considered

| Option | Licence | Upkeep / install cost | Fit |
| --- | --- | --- | --- |
| Existing STAR Python tokenizer + small opt-in rules **(selected)** | No new third-party dependency/licence | Zero download or runtime service; maintain local patterns/tests | Reuses the existing `Finding` interface and supports these targeted sink/guard pairs offline |
| Official `luau-analyze` from Luau | MIT | Install/update external binary; keep API/type definitions current | Excellent type/lint second opinion but does not provide this client-origin to sensitive-sink policy by itself |
| `selene` | MPL-2.0 | Install/update Rust-built linter and configuration | Excellent configurable Lua linting, not a substitute for checking Roblox server trust boundaries |

These approaches complement each other; the new rules do not replace official
type checking or code review. The opted-in module adds no packages, binary
downloads, network requests, GPU requirement, or keyring access.

### References

- Roblox: [Securing the client-server boundary](https://create.roblox.com/docs/scripting/security/client-server-boundary) — type/value/permission validation, Instances, numerical finiteness, and DataStore risks.
- Roblox: [Remote events and callbacks](https://create.roblox.com/docs/scripting/events/remote) — remote callback semantics.
- Roblox: [Data stores](https://create.roblox.com/docs/cloud-services/data-stores) — DataStore keys and methods.
- Luau: [official Luau language tools and MIT licence](https://github.com/luau-lang/luau).
- Selene: [source repository and MPL-2.0 licence](https://github.com/Kampfkarren/selene).
