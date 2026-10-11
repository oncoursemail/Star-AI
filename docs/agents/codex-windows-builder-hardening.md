# Local Windows builder hardening

Owner: Codex, claim 41. Branch: `star/windows-builder-hardening-20261011`.
Base: frozen PR51, `4cad59efd43302f6402705f4f8772b92d5919681`.

Scope: `scripts/build_windows.ps1`, `scripts/stamp_build_info.py`,
`star/build_info.py`, `tests/test_build_info.py`, `tests/test_windows_build.py`,
`docs/WINDOWS_BUILD.md`, `.gitignore` (explicit generated build paths), and this progress note. This is separate from broad
item 7, which retains real installed-upgrade and interactive acceptance work.

## Change

The local builder now checks venv/pip/npm/compiler/packager command failures,
uses fresh ignored profile directories for all children, restores process
environment/location in `finally`, and runs three hidden packaged EXE doctors.
It verifies a clean exact Git checkout before dependencies, immediately
before stamping/packaging, and after PyInstaller before doctors/archives.
Generated paths have narrow ignores; npm does not create a package lock.
Unknown source or tracked changes refuse attribution.
Local metadata has an exact SHA and `local_build` event with no claimed CI run.
Metadata/keyring inclusion matches the validated CI packaging requirements;
checksums cover only packages produced in the current successful run.

Offline fixtures exercise the actual copied PowerShell branches with process
adapters substituted, not real build tools. Python fixtures use fake Git to
prove dirty/wrong-root/changed-SHA refusals and preservation of an older stamp.
No dependencies were installed, no EXE or installer was built or invoked, and
no installed app, real profile, service, Studio, provider or account was used.

## Evidence and remaining acceptance

PR51 already has green Linux/Windows CI and actual packaged EXE doctors plus
Setup construction and checksums. CI Qt screenshot previews are legacy-widget
renders; `--ui-doctor` validates React assets/imports, not real default-window
interaction. The upgrade over v0.8.1, owner-data preservation and interactive
default React acceptance remain open. Claude's wave6 owns settings/integration
and real-window retesting; this task does not modify those files or gates.

Focused checks: 49 passed in 27.54 seconds using the existing audit interpreter,
isolated profiles and offline stand-ins. Actual PowerShell parsing, Python
compilation and `git diff --check` passed. The tests caught and fixed absent-env
restoration on Windows/.NET (explicit removal instead of leaving an empty entry).
Root and a separate reviewer inspected the frozen eight-file change and found no
blocker. Root full suite: 1596 passed / 11 optional skips in 109.81 seconds with
Graphify available and OS keyring deliberately unavailable in isolated profiles.
The frontend Git tree equals the independently validated policy branch exactly
(`63c8bafd516cecead35818bc4654f9107dbb7f5e`): 146 tests, TypeScript and Vite passed
once for those identical sources. Compile/diff checks passed. Ready for exact-path
CLI commit and draft PR; CI and installed acceptance are not yet established for
this candidate. No actual local builder dependency/build/installer execution.
