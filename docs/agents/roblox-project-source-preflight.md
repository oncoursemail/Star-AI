# Roblox project source preflight (explicit command)

Run from the STAR repository:

~~~sh
python -m star.roblox_project_preflight path/to/project --api-dump path/to/local-fullApi.json
~~~

The tool only **reads** the script-only service-tree format supported by
star.roblox_place.read_tree. It never builds a place, executes Luau,
downloads tools, launches Roblox Studio, writes project files or contacts
Roblox. The API dump is optional; without one, API names are explicitly
**unchecked** and the result is partial. Supply a locally acquired Studio
--fullApi JSON dump to activate the conservative API-name check. Invalid
dumps fail closed. API dump authenticity/completeness is not verified.

## Evidence contract

Stdout is one deterministic JSON object: schema version, top-level status,
coverage, sorted per-file records (project-relative filename, trusted
Script/LocalScript/ModuleScript class, checked scopes, source
findings with line/rule/severity/checker, and unverified limitations), ignored
files and a bounded summary. No absolute filesystem paths or source contents
are written to JSON. Checkers may produce warnings even for valid Luau.

- **checked** (exit 0): all recognized script sources got their applicable
  static checks, with no reported findings or unsupported files. This is **not**
  a gameplay, engine, parser, typechecker or Roblox Studio pass.
- **findings** (exit 1): one or more static findings; file-level partial
  warnings and unsupported paths still appear.
- **partial** (exit 1): a required check was unavailable, or source exceeded
  its 20 KB per-file budget. Files list skipped scopes explicitly.
- **unsupported** (exit 1): extra project files/unknown service paths were
  ignored by the script-only parser, and are listed (up to 32 paths).
- **invalid** (exit 2): project structure, input reading, bounded enumeration
  or supplied API dump failed validation; no script is claimed checked.

Only 400 script files, 3 MB total source (place parser), 20 KB per script for
static analysis, 20 MB per supplied API dump, 50 findings per file and 1,200
project entries are accepted. A truncated enumeration is invalid, not clean.

## Composition and limits

1. Existing star.roblox_place.read_tree defines supported services, parses
   .lua/.luau/init.luau, enforces source limits and rejects symlinks
   in parsed source; the preflight reads its in-memory Node contents, not a
   second mutable file snapshot.
2. Existing star.luau_lint.lint(safety_checks=True) supplies static patterns and
   lifetime warnings. Inline server remote-trust heuristics are enabled only
   for trusted Script class metadata. ModuleScript runtime context is unknown.
3. Existing star.roblox_api_checker.load_api_dump validates a local schema,
   and check_luau_api checks only inferable API class/service/member names.
   Dynamic receivers, hidden branches, runtime replication, physics and
   project assets are not proven correct.

Tool options compared: the existing Python standard-library composition
(PSF-2.0; free, no additional runtime or upkeep) was chosen; official Luau
CLI/analyzer (MIT; free, pinned elsewhere in STAR) is better for syntax and
types but lacks real engine services; Lune (MPL-2.0; free, new engine/runtime
maintenance surface) would also not prove Studio behavior. This feature
does not automatically run the analyzer, launch a CLI or install tools.

Tests: tests/test_roblox_project_preflight.py exercises main()
and preflight() with valid trees, three injected problem categories, bad
API dumps, unmatched assets, missing inputs, init modules, resource limits and
side-effect guards. GitHub CI, not local Studio execution, is the test run.


## Optional ModuleScript require graph (OFF by default)

Use `--module-requires` to add bounded, read-only static require evidence:

~~~sh
python -m star.roblox_project_preflight path/to/project --module-requires
python -m star.roblox_project_preflight path/to/project --api-dump local-fullApi.json --module-requires
~~~

With the flag absent, all existing JSON fields, return codes, permissions and
check scopes stay unchanged. The scanner runs **only** on already-loaded
`read_tree` source under the existing 20 KB per-script limit, and
reuses its trusted Script/LocalScript/ModuleScript metadata. It does not
reopen project files, rewrite source, execute Luau, call Roblox, or use a model.

Supported, exact static paths (including additional `.Parent` ascents
and direct children):

- `require(script.Parent.Config)` and
  `require(script.Parent.Parent.Shared.Config)`
- `require(script.Child)` (if the source-tree node is a ModuleScript child)
- `require(game:GetService("ReplicatedStorage").Shared.Config)`
  when the named service is in the recognized source-tree subset

Only admitted ModuleScripts become target edges. A directory with an
`init.luau` is represented by that ModuleScript node, not an
additional Folder; directory and similarly named ModuleScripts are never
guessed from partial names. A missing source-tree target is distinguished
from a non-ModuleScript target and is **not proof** that an Instance could
not be created dynamically at runtime.

The optional `module_require_graph` output contains source-relative
1-based line evidence for exact edges, missing static targets and unresolved
calls, plus strongly connected ModuleScript cycles (including self-require),
scanned-call/source/module totals, `skipped_sources`,
`truncated`, an explicit `coverage` and limitations.
Dynamic expressions, aliases, shadowed `require`, `script` or `game` roots
(including function parameters),
bracket indexing, out-of-tree services and unclosed calls are
**unresolved**, never misreported as an absent module or all-clear. Cycles
describe syntactic static edges, not proof of runtime reachability:
branch conditions and runtime construction remain outside this checker.

Maximum 256 recognized lexical require calls are classified across at most
400 scripts / 3 MB admitted by `read_tree`, and only source
under 20 KB per script is tokenized. At most 32 strongly connected cycle
groups are emitted. Any unmatched call, skipped oversized source or
truncation leaves graph coverage partial. Missing targets or static cycles
produce a findings status; purely unresolved calls a partial status (exit 1).
A graph with no detected issue says only `checked-static`, **not**
Studio-valid or gameplay-safe. The ordinary preflight report still carries
its own API/type/runtime limitations and exit status.

### Tool choice

| Option | Licence and cost | Installation/upkeep | Decision |
| --- | --- | --- | --- |
| Existing Python stdlib + STAR source-tree and tokenizer | Python PSF-2.0, free, no new dependency | Maintain a deliberately small supported grammar and tests | Selected: conservative, offline and stays within preflight bounds |
| Pinned `luau-analyze` 0.691 | MIT, free | Pinned native binary and Studio type definitions required for trustworthy engine Instance resolution | Stronger syntax/type analysis, but cannot derive Roblox service hierarchy alone |
| Rojo 7.7.1 source mapping | MPL-2.0, free | External executable, configuration and version tracking | Useful for full projects, but this preflight only admits the existing subset and must not install tools |

Regression fixtures run `preflight()` and the actual
`main()` CLI entrypoint on deterministic small script trees.
GitHub Actions supplies executed Python/Windows/frontend evidence; this is
not an engine execution or benchmark of generated-game correctness.
