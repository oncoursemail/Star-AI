# Schema regex security — Codex claim 49

Status: independently reviewed final source; root full suite passed. Claim49 source path was temporarily released for the unchanged PR51 merge480ded0, then re-reserved after bus140. Source edits remain frozen for the exact-path commit.

Worktree: `worktrees/wt-codex-schema-regex-security`  
Branch: `star/schema-regex-guard-20261011`  
Exact base: `62b34f4d20d56fbf3583bdef1b668a1689028482`

Owned paths: `star/studio.py`, `tests/test_schema_regex_security.py`, this note. No policy/MCP, UI, owner integration, controller, permission, credential or source-pin files changed.

## Problem and repair

Independent review demonstrated that accepted untrusted schema regex keywords can block synchronous JSON Schema argument validation. The aggregate asynchronous network deadline does not interrupt that CPU work. This implementation does not repeat the expensive attack in pytest.

The shared `validate_tool_schema` now refuses **all** `pattern` and `patternProperties` keywords at actual schema positions before validator selection or `check_schema`. It does not strip them, run them, or try to classify a regex as harmless. Refusal uses the fixed host-authored `tool_discovery/unsupported_schema_regex` diagnostic and a generic message; the raw pattern is never included in that message.

The new traversal follows recognized subschema positions: property/definition/dependent-schema maps; schema-valued dependencies; combinators; single or tuple items/prefixItems; additional/unevaluated items and properties; propertyNames/contains; not/if/then/else/contentSchema; and older Draft 3 extends/type/disallow schema forms. Map keys are instance/definition names, not schema keywords. Annotation/default/example/enum/const data are not traversed as executable schemas. Literal input fields named `pattern` or `patternProperties` remain valid and callable. Boolean subschemas remain valid; the existing dict-only tool-schema root contract is unchanged.

Existing whole-tree node/depth/reference bounds, serialized-byte bound, validator choice, strict type checks and arguments remain unchanged. The regex traversal follows the already-bounded tree. All external/local reference forms remain unsupported.

Existing routes already call the shared guard: Studio discovery (input/output), local MCP bridge registration, policy registration and every policy call, general MCP discovery/cached calls, and direct StreamableHTTP calls. No alternate duplicated validator was added.

## Actual offline validation

Audit interpreter: `worktrees/pr39/.venv-audit/Scripts/python.exe` (Python 3.12.14). Process-only isolated APPDATA/LOCALAPPDATA/XDG_DATA_HOME under the Codex scratch work directory; keyring explicitly unavailable through `sys.modules`. No network, connector, native Studio, provider, account, model or installer operation ran. No graph exists in this worktree; direct source is the authority.

Final focused slice: **517 passed, 2 skipped in 10.49 s**:

- `tests/test_schema_regex_security.py` (74 new controls)
- `tests/test_studio_transport_repair.py`
- `tests/test_policy_schema_security.py`
- `tests/test_mcp_schema_security.py`
- `tests/test_mcp_connections.py`
- `tests/test_local_mcp.py`
- `tests/test_studio_loop.py`
- `tests/test_studio_loop_repair.py`

New controls cover root/nested/alternative/dependency/property-name schema positions; declared Draft 3 bypass forms; both regex keywords including empty and harmless ones; validator-selection/check-schema/format-check spies proving no regex evaluation; unchanged annotation/literal field data; bool subschemas and ordinary validation errors; actual 30-tool offline native catalog; real SDK in-memory MCP refusal of a forged cached registry before guard dispatch; mutated general MCP cache refusal before factory/call count; direct HTTP refusal before options/credentials/transport; and valid policy/MockTransport HTTP routes. `urllib.request.urlopen` is forbidden in every new test.

Changed-source/test compileall and `git diff --check` passed. The two skips belong to the existing platform-gated transport controls. No uncontrolled regex benchmark or claim of measured aesthetic/model/runtime performance was made.

Frozen SHA-256:

- `star/studio.py`: `f1c83fcdbb4ba24c87090303f26fd11a24e566bf9909ed5a7fb0876b95cdaaa4`
- `tests/test_schema_regex_security.py`: `ffc50c9a62fb82ed298e0698eaf7ab2d860cae81d6326cceb1b3b6b5dc8e89f9`

## Limits and next owner step

This closes untrusted schema `pattern`/`patternProperties` evaluation at these shared boundaries. It is not a general CPU sandbox, OS scheduling guarantee, arbitrary custom-vocabulary validator review, or completion of all item 12/OpenConnector security work. Native tool search strings and model-authored Luau are separate existing permission-controlled behaviors; this patch does not grant, revoke or reinterpret them.

Root owns independent review, combined full checks, claim re-reservation, safe CLI commit/push and PR. No guard relaxation or successful live connection is inferred from these offline checks.


Root independent final verification: **1684 passed, 11 optional skips in82.80s** with Graphify available and OS keyring deliberately unavailable. Independent author-separate source/test/route reviewer found no scoped blockers; exact source/test hashes match. Frontend Git tree63c8bafd516cecead35818bc4654f9107dbb7f5e equals the already validated146-test/TypeScript/Vite source and green PR52 CI. No redundant frontend source change or model/provider/native operation. Root owns final safe commit/draft PR and exact-head CI verification.
