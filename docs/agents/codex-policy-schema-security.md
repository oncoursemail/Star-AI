# Policy schema security: focused item 12 repair

Owner: Codex; claimed scope: `star/policy.py`, `star/mcp_connections.py`,
`tests/test_policy_schema_security.py`, `tests/test_mcp_schema_security.py`, this note. Branch:
`star/policy-schema-security-20261011`; worktree
`worktrees/wt-codex-policy-schema-security`; exact base PR51
`4cad59efd43302f6402705f4f8772b92d5919681`.

Status: source frozen for independent root review; no commit, push, PR, integration
merge, full suite or live acceptance performed by this worker.

## Confirmed failure and repair

On the base, a `script_read` input schema containing nested `$dynamicRef` passed
`allowed_registry`. `enforce` asked the actual jsonschema default remote retriever
to resolve it before rejecting a mismatched Studio target. The offline reproduction
patched `urllib.request.urlopen` to return an in-memory fixed schema: one intercepted
lookup, zero actual network/credential/connector calls.

The policy now uses a local import of `studio.validate_tool_schema` at registration
and before each argument validation. That existing helper rejects `$ref`,
`$dynamicRef` and `$recursiveRef` at any depth, including local fragments, and
applies its existing 4,000-node, depth-32 and 64,000-byte schema bounds. Its
`StudioTransportError` becomes a fixed `ValueError` with suppressed exception
context; no schema URLs or raw resolver errors enter the policy refusal.

Cheap selected-target, write, Luau/Edit and screenshot-camera permission checks run
before schema work. Rechecking at enforcement also rejects directly supplied or
mutated registries. Normal argument validation remains
`Draft202012Validator(...).validate(...)` and retains `ValidationError` behavior.
Existing tool names, grants, target choices, native guards, retry behavior and source
pins are unchanged. The policy reuses the transport's existing schema budgets
instead of adding another traversal.

The curated HTTP MCP gateway had the same `$dynamicRef` gap. `valid_schema` now
uses the same Studio validator while retaining its stricter object requirement,
16,000 serialized-character limit and header annotation checks. Serialization is
inside the refusal handler, so cyclic or unserializable schemas return `None`.
Gateway calls recheck disclosed cached schemas before validation or factory
dispatch. Direct `StreamableHTTP.call_tool` also checks schema and arguments before
connection options, handshake or transport. The existing eight-call budget,
disclosure rule, preset opt-ins and read-only allowlists remain unchanged.

`CALL_SECONDS = 30` adds one `asyncio.timeout` around the complete HTTP connection
operation, including legacy initialization/notification and the requested
operation. Existing socket timeouts remain. A stream that keeps delivering tiny
chunks cannot reset this aggregate elapsed deadline. Timeout and cancellation
never replay a request. This is a cooperative asynchronous network deadline, not
proof of a CPU/regex or operating-system scheduling bound.

## Executed offline checks

- `tests/test_policy_schema_security.py`, `tests/test_mcp_schema_security.py`,
  `tests/test_mcp_connections.py`, `tests/test_studio_loop.py`,
  `tests/test_studio_loop_repair.py`, `tests/test_local_mcp.py`: **300 passed in
  7.41 seconds**, audit Python, isolated APPDATA/LOCALAPPDATA/XDG_DATA_HOME, OS
  keyring deliberately unavailable for the process.
- New controls cover all three reference forms, external/local fragments, root,
  property and list nesting, forged and mutated catalogs, every cheap permission
  gate before schema evaluation, shared bounds and cyclic schemas, sanitized
  exception context, all 30 stored native tool schemas and permitted argument calls.
- Curated HTTP controls cover injected factory and actual MockTransport discovery,
  nested references, mutated cached catalogs, direct-call refusal before transport,
  cyclic/oversized/deep/node-bounded schemas, header metadata, ordinary argument
  validation, disclosure and the unchanged eight-call limit. A tiny-chunk stream
  expires and closes once without retry; legacy handshake plus operation share the
  same deadline; explicit cancellation propagates.
- The actual jsonschema resolver positive control is intercepted in memory;
  all policy-refusal cases produce zero lookup attempts.
- Compileall for the changed source/test and `git diff --check` passed.

Frozen source SHA-256:
`1da9d37ff3f83558ec1c19b64ed5c5e2dfec229edd3461fc38ede605c79bddf6`.
Frozen test SHA-256:
`847b6ffcf69c33f3bdeb593fab37dfcdcf2ee3dec2e5606ba3f2a43b17290dd4`.
Frozen HTTP source SHA-256:
`71750192f0b70e1105f9ae074557266cee16fe7e4fb8805a91952b5eaf2f68ea`.
Frozen HTTP test SHA-256:
`a201c448e5a4e89bd61283a90b796f4bb41f374f37a24ba0ffada92fd43ec2ff`.

## Scope limits and next handoff

This is a focused schema and HTTP elapsed-budget repair, not completion of the
broader OpenConnector review or a CPU execution sandbox. Transport discovery
already checked Studio schemas; this repair closes policy and curated-gateway use
through direct, forged or subsequently changed catalogs.
No remote, native Studio, provider, model, account, service, release or installed-app
operation occurred. Claude's live integration/training/Settings work is untouched.
Root independently reproduced both pre-repair reference lookups on frozen PR51
through in-memory urllib/factory adapters (one intercepted lookup each, zero real
network, credential or live MCP calls). An independent reviewer confirmed all four
source/test hashes and found no blocker in the combined source. Root full suite:
1610 passed / 11 optional skips in 73.56 seconds, Graphify available and OS keyring
deliberately unavailable in an isolated profile. The identical frontend tree passed
146 tests, TypeScript and Vite; changed Python compile/diff checks passed. Source
is ready for an exact-path CLI commit and draft PR; no live acceptance is implied.
