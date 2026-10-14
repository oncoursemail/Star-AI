# Contract for offline Luau checker findings

This is a regression contract for four offline checkers and their actual
rule-firing tests. It does not execute Roblox Studio or infer engine semantics.

Each finding must have a stable rule ID (kebab-case or established SEC- form),
a 1-based source line, severity `error`, `warning` or `review`,
a nonempty bounded (max 160-character) message, and actionable fix text.
All rule IDs are discovered from Python source AST by the contract test.
A newly introduced rule without a documentation row and an actual failing
sample will break GitHub CI.

## Rule documentation (23 unique IDs)

| Rule ID | Implemented by | Severity | Repair direction | Firing fixture |
| --- | --- | --- | --- | --- |
| `deprecated-task-global` | lint,safety | warning | Use task.wait(), task.spawn() or task.delay() | lint and safety positive cases |
| `instance-parent-argument` | lint,safety | warning | Configure the instance before setting Parent | lint and safety positive cases |
| `service-property` | lint | warning | Use game:GetService for services | lint positive case |
| `humanoid-load-animation` | lint | warning | Load animations through Animator | lint positive case |
| `datastore-unprotected` | lint | error | Wrap yielding DataStore operations in pcall | lint positive case |
| `unchecked-find-child` | lint | warning | Check FindFirstChild result for nil before access | lint positive case |
| `loop-without-yield` | lint,safety | error/warning | Yield or terminate loops | lint and safety positive cases |
| `loop-connection` | lint | review | Own and disconnect event connections | lint positive case |
| `mixed-client-server` | lint | warning | Separate client-only and server-only code | lint positive case |
| `datastore-read-set` | lint | warning | Prefer UpdateAsync when writes depend on reads | lint positive case |
| `touched-debounce` | lint | review | Add a completed debounce or cooldown | lint positive case |
| `remote-unvalidated` | lint | review | Validate server-side remote arguments | lint positive case |
| `runservice-connection-leak` | safety | review | Disconnect RunService connections after work | safety positive case |
| `touched-reward-unguarded` | safety | review | Set a cooldown before granting rewards | safety positive case |
| `server-waitforchild-chain` | safety | warning | Bound chained server WaitForChild calls | safety positive case |
| `SEC-DATASTORE-CLIENT-KEY` | security | warning | Use a server-owned DataStore key | security positive case |
| `SEC-CLIENT-AMOUNT` | security | warning | Validate type, range and entitlement | security positive case |
| `SEC-CLIENT-PRICE` | security | warning | Read prices from the server-owned catalogue | security positive case |
| `SEC-INSTANCE-OWNERSHIP` | security | warning | Validate Instance type and ownership | security positive case |
| `SEC-REMOTE-ALLOWLIST` | security | warning | Use a server-owned key allow-list | security positive case |
| `unknown-class` | api | warning | Use a class in the local validated dump | API checker positive case |
| `unknown-service` | api | warning | Use a service in the local validated dump | API checker positive case |
| `unknown-member` | api | warning | Check receiver and documented member | API checker positive case |

## Existing intentional legacy aliases

The legacy `luau_lint.py` implementation and the opt-in replacement
`luau_safety.py` both contain `loop-without-yield`,
`instance-parent-argument`, and `deprecated-task-global`. The former
removes these legacy diagnostics before extending results with the safety
checker when `safety_checks=True`. Renaming or removing their public IDs
would break existing diagnostics/tests. Contract enforcement permits **only**
these three documented shared IDs and rejects all new overlap. There are
23 unique IDs and 26 module-specific definitions.

## Gap ledger and limits

Before this PR: 23 canonical documentation rows absent; `ApiFinding` exposed
no `severity`, `message` or `suggested_fix` properties (three contract
fields for three API rule IDs); the three intentional shared legacy rule IDs
had not been described together. Existing positive fixtures supplied a
firing example for each known rule. After: 23 rows documented and API
findings expose those three bounded, advisory properties; 3 legacy aliases
remain intentionally shared and explicitly accepted.

Standalone native analyzer output is out of scope. API spelling reports
remain advisory, especially with the small test fixture; Studio's actual
engine type semantics and runtime game behavior are unverified.

Verification is GitHub Actions running `tests/test_luau_findings_contract.py`
with real checker calls, plus the existing Python and frontend suites.
