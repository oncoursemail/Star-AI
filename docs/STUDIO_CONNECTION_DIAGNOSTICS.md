# Studio connection diagnostics

STAR reports a bounded connection failure with fixed host-authored codes. These
codes identify the gate that refused the current attempt; they do not prove the
root cause, that a process never started, or that Studio is writable.

`StudioTransportError(message, *, stage="unknown", reason="connection_failed")`
accepts only the fixed stage/reason pairs defined in `star/studio.py`. Its message
must be written by host code, never copied from a connector, launcher or raw
exception. Use `studio.connection_diagnostic(error)` for public receipts. It
copies only validated codes and returns `unknown/connection_failed` for legacy,
untyped or tampered errors. Do not serialize `str(error)`, its arbitrary
attributes, traceback context, raw initializer, stderr or launcher arguments.

The shared desktop status DTO adds `diagnostic`, either `null` or
`{"stage": "initialization", "reason": "invalid_response"}`. Existing
`reason_code` behavior is preserved: `connection_failed`, the outer probe's
`timeout`, and `host_launcher_unavailable` for absent/invalid host configuration.
A typed native stage timeout retains `connection_failed` at that outer level;
its diagnostic identifies the actual timeout gate. A successful discovery has
`diagnostic: null`. A validated empty attachment window has
`instance_discovery/no_instances` and state `no_instances`, never `connected`.
Connector-supplied diagnostic fields are discarded, including fields in an
otherwise valid STAR local MCP status response.

| Stage | Fixed reasons |
| --- | --- |
| `configuration` | `invalid`, `unknown_target`, `not_configured`, `unsupported_platform`, `missing_environment`, `missing_launcher` |
| `process_startup` | `failed`, `timeout` |
| `initialization` | `failed`, `timeout`, `invalid_response` |
| `capability` | `tools_not_declared` |
| `tool_discovery` | `failed`, `timeout`, `invalid_catalog`, `duplicate_names`, `limit_exceeded`, `invalid_schema`, `unsupported_schema_reference`, `empty_catalog`, `invalid_cursor`, `repeated_cursor` |
| `instance_discovery` | `failed`, `timeout`, `invalid_response`, `limit_exceeded`, `representations_disagree`, `no_instances`, `tool_unavailable` |
| `selection` | `required`, `unavailable` |
| `shutdown` | `failed`, `timeout` |
| `request` | `failed` |
| `probe` | `timeout`, `invalid_evidence` |
| `unknown` | `connection_failed` |

`initialization/invalid_response` means the actual MCP SDK rejected the response
schema. `capability/tools_not_declared` means initialization passed but the tools
capability was absent or null. A tools capability with `listChanged: false` is
valid. Unsupported protocol negotiation and other initializer exceptions remain
`initialization/failed`; STAR never classifies them by searching exception text.
Failures while opening the transport or entering the SDK session, before the
initialize request begins, are startup failures. That label does not attest
whether its child was already dispatched.

Caller-owned errors and cancellation retain their existing propagation behavior.
If cleanup adds a different failure after the caller raises, the sanitized result
is a shutdown failure. Multiple distinct typed failures before the caller receives
a session have no single established phase and report `unknown/connection_failed`.
Existing untyped bridge errors also remain unknown. The outer aggregate timeout
is `probe/timeout`, rather than a guessed native transport stage.

The transport, deadlines, host-command precedence, configuration homes, selected
instance, permissions, native guards and durable uncertainty ledger are unchanged.
The existing bounded attachment poll retries only validated empty instance lists;
these diagnostics add no connection replay, remote calls, fallback or writes.
This source change does not update an already installed application or render a
new frontend error panel.

The saved 09:12 host discovery receipt recorded only `StudioTransportError`, and
there is no raw initializer available. These new codes cannot retroactively
identify that refusal or justify relaxing the capability check. A future single
read-only MCP diagnostic attempt requires a separately reviewed exact source
commit, explicit host profile, bounded readiness handoff and quiet lifecycle
conditions. It must not select an instance, edit, restart, retry or call a model.
Offline initializer fixtures establish classification and sanitization, not
remote readiness or successful live Studio acceptance.
