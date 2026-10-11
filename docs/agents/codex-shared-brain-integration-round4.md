# Shared-brain integration round 4

Claim: 51. Owner: Codex. Branch: `star/shared-brain-integration-20261011`.
Worktree: `worktrees/wt-codex-shared-brain-integration`.

## Scope and merge

Base is exact Claude integration `480ded03ced2f9dfb2bcdeabdc951f0ad47f5afc`.
A normal `--no-ff --no-commit` merge of reviewed PR47 head
`1c08247f5d82863e0bbe39f6b50ecc9f62642986` is prepared. No commit or
push was performed by this worker. The staged merge is authorized; root owns
the final safe CLI commit and publication.

Only `star/intelligence.py` conflicted: two import/constructor sections.
Resolution retains `RobloxCloud`, cloud injection and tools, workspace/home,
and `SkillLibrary(..., bundled=PACKS_DIR)`, together with shared runtime
registration, per-call Graphify boundary checks, close/revocation, and honest
legacy fallback restrictions. `for_settings` retains both the cloud factory
and exact owner-selected workspace registration callback. No permission,
activation, provider or cloud-approval behavior was changed.

New `tests/test_shared_brain_integration.py` exercises actual synthetic
prepared stores plus injected cloud objects: source-backed shared queries,
bundled skill availability, pending cloud requests, unregistered-root refusal,
and settings/workspace revocation while a fresh hub retains cloud independently.
It performs no account, provider or network operation.

## Development source validation

V5 audits all twelve expected-source pins against exact integration 480.
Only `star/evals.py` adds new content since V4: fifteen CLI-dispatch lines
from `f16ebdfd1e2436c98a515a74a91df48f460c2654`. Its grounded declarations
and bodies remain unchanged at lines 19 and 42. The dispatcher was not run.

The prior four changed-source records are preserved verbatim, including their
`77f7e4e7e118a82f72ded480a5ed5b7519731ec7` provenance. Their bytes still
match integration 480. The remaining seven historical source pins are unchanged.
Tests distinguish current and preserved per-record revisions and refuse further
source drift. A fifth development-only benchmark refusal control now covers
the evaluation-catalog source before any query, store construction or timing.

V5 semantic SHA256:
`799522b3c19cd10faafa64bf2ce1a8f6b1c882891f75e832dd9b5406ca07d158`.
Historical fixture raw SHA256 remains
`516cce6357a4d0796c805d7b03dd53df3a965bb5a70cba1c7f388b5485135696`.
Original fixture, result JSON and benchmark script have no Git diff against
PR47. Historical source hashes, queries, grading, split, disclosed holdout and
measurements are unchanged. No new retrieval-performance claim is made.

## Validation and environment

The named guarded runner `shared-round4-focused` uses fresh APPDATA,
LOCALAPPDATA, XDG_DATA_HOME and USERPROFILE; keyring is process-disabled,
provider/Studio overrides are removed, and `STAR_SKIP_LIVE=1`.
Graphify is available only for disposable synthetic/test-copy exports.

First run: 236 passed, 7 skipped, 4 failed and 15 setup errors in 34.96 s.
All failures were Graphify cache tempfile paths exceeding the Windows path
limit under the long runner basetemp, with no source/assertion failure.
The identical focused slice with explicit short owned `cwd/work/s4` basetemp
passed: **255 passed, 7 skipped in 53.10 s**. All four new combined wiring
controls passed. No source behavior changed to bypass that environment issue.

Changed Python files compile. Working and staged `git diff --check` pass,
and there are no unresolved merge paths. Functional source/tests are frozen
for root's independent full suite and source review. Full Python/frontend
checks belong to root; this worker has not claimed their result.

## Frozen working hashes

| Path | SHA256 |
| --- | --- |
| `star/intelligence.py` | `434F9D9D62335352FCF8C60D4A52F304E44306E957EEDE64E7DD82320A33AA86` |
| `tests/test_shared_brain_integration.py` | `4A727155D61934D29066536E52168E31267AEF64081E74C4903FB5ED5B66550A` |
| `tests/test_shared_brain_variants.py` | `D5F21B803DEC775F10F80BFD495F1E7D08E9ABDCDFEF3368F5CC1178AC1DD94F` |
| `tests/fixtures/shared_brain_runtime_source_validation.json` (raw) | `E3CD99235302E15F0BC4B9FF9BB758E03A7E4FB969DE79281B720A9762EAA6B2` |
| `docs/SHARED_BRAIN_SOURCE_VALIDATION.md` | `68C8829D3C89CF2AFF53DB866920B3188BBE7A2D4F6816F5ADCC2E31C0292BBB` |

Private scratch source-audit receipt and exact evals CLI diff are under the
Codex chat's `work/shared-round4-source-audit.json` and
`work/shared-round4-evals-cli.diff`. Root-generated untracked
`frontend/tsconfig.tsbuildinfo` was left untouched and unstaged.

## Root final review and validation, 14:13Z

Root independently reviewed all twelve historical/current pins, all nineteen declaration locations/excerpts, the exact fifteen-line eval dispatcher addition, the merged cloud/shared-runtime wiring and refusal control. The independent reviewer found no scoped blocker. Original frozen fixture/results/archive/holdout bytes are unchanged. Root's isolated full Python suite passed **2256 passed, 22 optional skips in 145.30 s** with Graphify available and keyring deliberately unavailable. The frontend passed **172 tests**, TypeScript and Vite; its tree is unchanged from integration 480. Compile, working/staged diff checks and unresolved-path checks passed. Root removed only its own generated untracked frontend tsbuildinfo after the frontend commands completed. Frozen functional hashes above were reverified before the exact-path safe CLI merge commit. This source handoff preserves evidence boundaries: no new model, retrieval-performance, native Studio, visual, lesson approval or weights claim. Exact-head CI is a separate pending publication check; integration and release remain Claude's responsibility.

