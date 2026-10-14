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


## Optional API-confusion corpus suggestions (default OFF)

~~~sh
python -m star.roblox_project_preflight path/to/project --api-confusions
python -m star.roblox_project_preflight path/to/project --api-dump path/to/local-fullApi.json --api-confusions
~~~

Only the explicit --api-confusions flag reads the existing offline reviewed
80-entry corpus in data/roblox_api_confusions.json. Without it, the command and
JSON schema are unchanged. With the flag, already admitted Luau source
(20 KB per file maximum) is scanned after existing static checks; it adds
"api-confusion:possible-method-spelling" records with category "advisory",
severity "info", 1-based line and column, exact wrong/right spellings,
source_url pointing to the official Creator Hub class reference, and
receiver_evidence ("unverified" or "api-dump-inferred-class", plus an optional
receiver_class). A suggestion is **never a confirmed Roblox engine error**.
A Lua table or other custom object may intentionally define the same method.
Unterminated or otherwise malformed Luau is not parsed or validated by this
scanner; a hit still needs manual review.

If a validated local dump is supplied, its *existing* conservative
check_luau_api inference may provide additional context for a uniquely
matched same-line method call when the class inherits from the cited official
reference class and the replacement appears in the dump's member set. This
is still not a typechecker, class proof or Studio validation; conflicting or
ambiguous matches remain "unverified." The pre-existing API-dump findings
stay separate from these low-severity suggestions.

No additional files, project assets, or oversized scripts are scanned; the
advisories share the existing 50-total-findings-per-file cap with other
checkers and cannot evict existing security/API findings. A truncation warning
is emitted if candidates exceed the remaining output budget. Opt-in output
adds summary fields api_confusion_candidates (all scanned lexical matches),
api_confusion_advisories (reported subset), and
api_confusion_confirmed_engine_errors (always 0: no Studio test).
A report containing suggestions is partial as to receiver verification and
has status "findings"/exit 1; malformed corpus/dump data is invalid/exit 2.
It does not rewrite code, call a model or network, or run automatically in chat.

Implementation options compared: (1) reuse the current original offline
Python corpus, stdlib scanner and existing API-dump checker (PSF-2.0 Python
runtime; no API cost, low maintenance; selected); (2) require a native Luau
analyzer (MIT, free, but installation/version tracking and incomplete Roblox
class context); (3) depend on Lune (MPL-2.0, free, extra runtime upkeep and no
Studio engine proof). A web API name lookup adds network costs and changing
content without solving the unknown-receiver problem. This is static evidence,
not a measured improvement in generated Roblox code quality.
## Optional installed native Luau analysis (explicit opt-in)

By default, the command and JSON output are unchanged. To add a bounded
second opinion from an **already installed** official standalone Luau analyzer:

~~~sh
python -m star.roblox_project_preflight path/to/project --api-dump local-fullApi.json --native-luau
~~~

The sole new flag is --native-luau. The existing star.luau_analyze locator uses
STAR_LUAU_TOOLS_DIR/luau-0.691/luau-analyze (or the Windows .exe), then PATH.
Nothing is downloaded or installed by preflight. Each script is written only
inside an isolated temporary staging directory for the analyzer subprocess;
the **project** remains read-only. A six-second timeout applies to each script.
At most the first 12 scripts within the 20 KB static-source budget are
attempted. Extra or oversized scripts are reported as skipped; the full
project is never said to pass when a required check could not run.

With the flag, each file has a native_luau record containing:
status, diagnostic_count, engine_symbols_ignored, and scope. The
top-level native_analysis includes requested, checked_files,
unverified_files, attempted_files, skipped_files, file_limit,
per-status counts and the explicit non-Studio scope.

Native status means:

- checked: the standalone tool ran and exited zero without diagnostics.
- diagnostics: it ran and produced recognized file/line Luau findings.
- engine_limited: only unsupported Roblox global/type diagnostics were emitted,
  which are omitted as game errors but disclosed as unverified engine context.
- unavailable: no suitable analyzer executable was installed.
- failed: the tool could not be started or read.
- timed_out: it exceeded its per-file six-second limit.
- malformed: invalid status, unrecognized stderr, a silent nonzero exit,
  conflicting success/error records, or diagnostics for the wrong file/line.
- truncated: the analyzer produced more than 48 KB output or more than
  20 diagnostics; any partial diagnostics shown are NOT complete evidence.
- skipped: the source exceeded 20 KB or the 12-file invocation budget.

checked and diagnostics add native-luau-syntax-limited-types to the
file's checked_scope. All other native statuses force partial file coverage
and nonzero CLI exit. Roblox engine-symbol suppressions also force
partial coverage, even when other diagnostics exist. Native diagnostic rows
use checker=native-luau and have project-relative file, source line, rule,
severity and a bounded sanitized message. No analyzer stderr, absolute file
paths, environment tokens or source snippets are emitted.

Standalone Luau has **no complete Roblox engine type definitions**: its
absence of syntax/type findings is not proof of correct Roblox APIs,
replication, runtime game behavior or a Roblox Studio pass. A locally
supplied API dump is still separate and optional; omitting it keeps API-name
coverage partial even if native analysis succeeds.

Offline regressions: tests/test_roblox_project_preflight.py uses fake
native subprocesses for successful and refused evidence paths. The existing
pinned Luau quality-smoke job also exercises a clean and an intentionally
broken project through the real preflight entry point, without changing its
pinned runtime or any workflow.
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
