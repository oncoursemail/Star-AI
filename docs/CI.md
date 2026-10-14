# CI layout

## STAR Desktop — Build, Test & Release (`windows-desktop.yml`)
- `frontend` (Linux): installs, type-checks, tests and builds the React app once and hands
  `frontend/dist` to the Windows jobs as the `star-frontend-dist` artifact (kept 1 day).
- `windows-tests` (2 Windows shards): the whole offline suite, split by test file with
  `STAR_TEST_SHARD=i/N` (see `tests/sharding.py`; unset runs everything). Each shard uploads its JUnit
  XML (per-test timings) as `windows-tests-shard-i`.
- `windows-build`: PyInstaller, packaged-EXE doctors, ZIP, Inno Setup, checksums and preview uploads.
  It runs beside the test shards instead of after them.
- `attest-release` and `publish-release` (main only): attestation needs the build **and** every test
  shard; publishing needs attestation. A red shard therefore blocks a release.

The two PyInstaller commands (this workflow and `scripts/build_windows.ps1`) must stay identical;
`tests/test_pyinstaller_data_files.py` checks that, and that every non-Python file under `star/` is
packaged.

## STAR offline checks (`tests.yml`)
- `changes` decides whether a change is documentation only (`scripts/ci_changed_scope.py`). Only
  Markdown at the repository root or under `docs/` (not `docs/lessons/`) that no test, script or
  source file names counts. Anything else, or any doubt, runs everything.
- `Offline Python checks` and `React UI compile and tests` are skipped for documentation-only changes
  (a skipped job satisfies a required check).

## Conventions
- Actions are pinned to full commit SHAs with the version in a comment
  (`tests/test_workflow_action_pins.py`). To update one, resolve the new tag to its commit and change
  both.
- pip caches are keyed on every requirements file a job installs; npm caches on
  `frontend/package.json` (the repository has no lockfile).
