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
