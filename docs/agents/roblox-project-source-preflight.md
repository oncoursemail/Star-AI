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
