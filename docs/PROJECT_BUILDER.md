# Incremental Rojo project builder

Generate a reviewable project on disk using STAR's selected model and provider:

```console
python -m star.project_builder --plan plan.json --out generated-project
```

Configure the provider and model in STAR Settings first. The command loads the
same `app_data()/settings.json` as the desktop and uses `providers.open_client`,
including its credential lookup, endpoint validation, timeouts and proxy policy.
It does not override the selected provider with legacy local-model environment
variables, choose a fallback provider, start Studio, execute Luau or publish a game.

The output folder must be new or empty. Existing projects are never overwritten.
Exit codes are **0** for all modules generated, **1** for an incomplete project
with a failure manifest, and **2** for invalid input/configuration or a filesystem
error. The manifest is also printed to stdout. Raw provider exceptions are not
printed, saved or returned to the model because they can contain sensitive data.

## Plan schema

The root is a module list or an object with a `modules` list. For example:

```json
{
  "modules": [
    {
      "name": "Items",
      "kind": "shared",
      "purpose": "Describe the available item types.",
      "interface": {"getItem": "(id: string) -> Item?; return nil for an unknown id"},
      "requires": []
    },
    {
      "name": "Inventory",
      "kind": "server",
      "purpose": "Maintain an in-memory inventory using the Items catalog.",
      "interface": ["getItem", "addItem"],
      "requires": ["Items"]
    }
  ]
}
```

`interface` is a non-empty list of public **function names**, or a mapping from
those names to non-empty signature/behavior summaries. Mapping values are given
to the model but are not type-checked. The presence of a name in prose, a string,
a comment or a different table is not an implementation of that interface.

Names are ASCII Luau identifiers, at most 64 characters. Module names are unique
case-insensitively across the project. Path separators, traversal, drive names,
Windows device names, `init`, language keywords and the injected `dependencies`
binding are not valid module names. `init` is reserved because Rojo treats
`init.lua` specially rather than as an ordinary sibling module.
Module and public interface names matching forbidden API/service identifiers
(including `load`, `request`, `debug`, `os` and `GetService`) are rejected before
model calls; use alternatives such as `loadData` and `saveData`.

Dependencies must be declared by exact name, must exist, and cannot form a cycle.
Server modules may require server/shared modules; client modules may require
client/shared modules; shared modules may require only shared modules. A server
cannot require a client's runtime module, and a shared module cannot import a
server-only implementation. Validation precedes all model calls and writes.

## One module per turn

Generation is sequential and dependency-ordered. Each stateless call receives:

- The current module's name, kind, purpose, public interface and requirements.
- Only its direct dependencies' names, kinds and public interfaces.
- Fixed output and safety rules, plus a fixed diagnostic on the one repair attempt.

No other module's purpose or implementation, conversation history, unrelated
briefs or unknown plan fields are sent. Interface descriptions keep dependencies
usable without making the model reread their implementations.

The writer inserts deterministic bindings for the declared dependencies:

```lua
local dependencies = {
    Items = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("Items")),
}
```

Generated code uses `dependencies.Items.getItem(...)`. It must not replace the
`dependencies` binding or add its own `require` calls. Client-to-client bindings
use `script.Parent`, so they refer to the player's runtime clone rather than the
StarterPlayer template. No model-authored output path is accepted.

The model function is injected for offline use:

```python
from star.project_builder import build_project

def generate(prompt: str) -> str:
    # Supply one completion, without retaining prompt/response history.
    return "```luau\nlocal M = {}\nfunction M.run() return true end\nreturn M\n```"

manifest = build_project([
    {"name": "Example", "kind": "shared", "purpose": "Expose a readiness check",
     "interface": ["run"], "requires": []}
], "generated-example", generate)
```

## Static validation and repair

Responses must contain exactly one non-empty `lua`/`luau` (or unlabelled) fenced
block, with no extra prose. A deliberately small static subset keeps validation
inspectable. Declare a top-level table with `local M = {}`, implement public
functions at top level, and end with `return M`. The table can have another name.
Dot functions, colon methods and anonymous-function member assignments are
supported. Returning inline table literals, using a typed table initializer,
if-expressions and backtick interpolation require a manual implementation or a
rewrite into the documented subset.

The checker distinguishes comments and ordinary/long strings from code, checks
balanced conventional statement blocks and delimiters, and checks public
functions on the actual returned table. Obvious replacement of the table or a
required method is rejected. Comments and strings are never rewritten in the
saved module body. The writer only adds the strict-mode/import preamble.

The built-in forbidden policy rejects model-written `require`, dynamic loading,
environment/executor/file/network access, unsafe `os` access, and the
HttpService, DataStoreService, MessagingService, TeleportService and InsertService
APIs. Literal service names are required. Recognized forbidden bracket lookups
and escaped member lookups are also rejected. This is conservative: even a
shadowed identifier with a forbidden API name may be rejected.

**This is not a Luau parser, type checker, data-flow analyzer or execution
sandbox.** It does not prove runtime behavior, signature correctness, absence of
obfuscated API access, or safety of arbitrary generated code. It intentionally
rejects some valid Luau. Review the source and validate it in your usual isolated
Luau/Roblox environment before use. Passing static checks is not a playtest.

A failed validation or model exception receives exactly one retry with a fixed
failure message. Previous code is not replayed. Truncated, filtered or tool-call
provider responses are rejected even when they contain a plausible code block.
After two failures, no source is written for that module. Its dependents are
reported as blocked with zero attempts; unrelated modules can still complete.

## Output and manifest

All planned entries are ModuleScripts (`.lua`). Kind determines placement:

| Kind | Folder |
| --- | --- |
| shared | `src/ReplicatedStorage/Shared/` |
| server | `src/ServerScriptService/Server/` |
| client | `src/StarterPlayer/StarterPlayerScripts/Client/` |

`default.project.json` declares the DataModel and explicit service/container
classes. All three source trees exist even for a single-kind or wholly failed
build. `manifest.json` contains the generation order, complete/incomplete status,
generated/failed entries, declared interfaces/dependencies, attempt counts,
validation errors and blocked dependencies. Generated entries also contain a
relative path and SHA-256 of the exact saved UTF-8 bytes. The manifest contains
neither provider settings nor raw failed responses.

The project supplies the planned modules, not an invented bootstrap convention:
public functions are not automatically invoked. Partial projects are clearly
marked incomplete and must not be treated as finished games.

Names and relative paths are guarded on all hosts, including Windows-style path
syntax. Symlinks, broken links, junctions/reparse points and existing files are
refused. Paths are checked again after model calls, and files use exclusive
creation to avoid following or overwriting an existing leaf/hard link. These
checks are not an OS sandbox against another process concurrently rewriting the
filesystem. Filesystem failures abort rather than claim a completed project;
a manifest is not guaranteed after a disk error or external interruption.

Rojo references: [project format](https://rojo.space/docs/v7/project-format/) and
[sync details](https://rojo.space/docs/v7/sync-details/). A generated project has
not been built by Rojo or run in Studio merely because this builder succeeds.

## Tests

```console
pytest -q tests/test_project_builder.py tests/test_project_builder_review.py tests/test_project_builder_windows_workflow.py
pytest -q
```

The focused suite uses scripted model responses and fake Settings/provider
boundaries; no network, GPU, real credential store or running model is required.
It drives the actual builder and CLI. Symlink cases explicitly skip only on hosts
that cannot create symlinks; reparse-point handling also has an offline simulated
attribute test. The full repository suite remains a separate integration gate.

Review regressions also load and validate real Settings from an isolated profile,
replacing only the provider boundary while blocking network and credential-store
access. They exercise native Windows paths, a four-module shared/server/client
build, and rejection of every forbidden module/interface name before generation.
The workflow regression executes the actual offline-test step in PowerShell with
stubbed command results to prove that failed pytest cannot be hidden by compileall;
it skips only when PowerShell is unavailable on a non-Windows host.


## Optional StyLua parsing and formatting (off by default)

The project builder can pass generated Luau through an **already-installed**
[StyLua](https://github.com/JohnnyMorganz/StyLua/blob/main/README.md) executable:

```console
python -m star.project_builder --plan plan.json --out generated-project --stylua
```

Without `--stylua`, the original generation path is unchanged, and no formatter
is resolved or run. With the flag, STAR checks for the `stylua` executable
before loading provider settings or writing output. STAR does **not** install or
download StyLua. The released upstream tool is [MPL-2.0](https://github.com/JohnnyMorganz/StyLua/blob/main/LICENSE.md);
check its installed version and licence terms independently.

For each generated module, STAR sends **only** the model-produced code (not
STAR's trusted `--!strict` or dependency prefix) to StyLua via stdin with
`--syntax Luau`, spaces, LF line endings and a 10-second timeout. It formats
only the new generated source; existing workspaces are not traversed. Nonzero
exit, timeout or invalid output counts as a failed validation attempt, with
the existing maximum of two attempts. The formatted code must pass STAR's
safety and public-interface validator again before it can be written. Raw
external stderr is never shown to the model or stored in the manifest.

The **CI regression tests use fake StyLua processes**, not an installed
formatter, so their success does not establish actual version-specific parsing
coverage or Luau runtime correctness. Use an explicitly approved operator
smoke test with StyLua v2.6.0 and a real Studio/Luau run before treating
formatting as a full code-quality gate.
