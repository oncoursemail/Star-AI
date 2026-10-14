# Offline general-foundation benchmark source

Claim 43; branch `star/general-foundations-benchmark-20261011`; base
`4cad59efd43302f6402705f4f8772b92d5919681` in
`worktrees/wt-codex-general-foundations-benchmark`. Six new paths only: standalone
stdlib checker, two public development fixtures, focused tests, user documentation
and this note. Codex root independently reviewed all ten oracles before source
implementation using math/datetime stdlib checks and manual reasoning for logical
and abstention cases. Broad board item 14 remains open for actual model comparison.

Implemented: inert no-command help and offline list/prepare/score/compare;
allowlisted public messages without oracle reads; strict bounded JSON and full
10-by-attempt coverage; exact current suite/oracle/grader/request/response hashes;
complete operator-declared source/adapter/backend/model/options identity; compare
regrades both raw runs and rejects saved grade/pass fields. Explicit model-axis
requires the exact expected model pair; otherwise all controls match. Score
reports preserve empty, wrong, invalid-format and transport-error outcomes. No
approval flag, provider import, app wiring, network, profile, training, native or
model execution capability was added. All supplied provenance is declared and
unauthenticated, even when hashes match. Fixtures are public development tasks.

Focused audit: **73 passed in 1.01 seconds** using audit Python, isolated
APPDATA/LOCALAPPDATA/XDG_DATA_HOME and temporary files; OS keyring unavailable.
Tests use authored fake replies only. Full suite, frontend checks, commit, push,
PR and integration are not performed by this worker; root reviews the exact
six-file freeze first. No actual brain/model comparison or gain was measured.

Final source/test py_compile and git diff --check passed. Current Git HEAD stays
the exact base above; all six owned files are new/untracked, nothing staged.

Frozen SHA256:

- Source: `47dd6fae13de0e056321ef398222112a39289e6853a5b920edff729340cdc042`.
- Public suite: `055a50182fdb123442f461002a53f407c521d22c4dd0b5ba49d95590a9ad14ed`.
- Oracle sidecar: `027769e15bab3839060c83fa4fe16eaa0d2ab6c4568c89b69922d49ddb03f660`.
- Focused tests: `223bc8a0b738392c710edd8b563579b1db95fa7b4c54eb95d54dc49182b17c38`.

Root owns broader checks and any CLI commit/push. Keep the frozen Claude
eval/holdout/training and active integration work untouched.

Root and an author-independent reviewer inspected the six-file freeze and found
no scoped blocker. Root full suite: **1624 passed / 11 optional skips in 92.35
seconds**, Graphify available, OS keyring deliberately unavailable and isolated
profiles. The frontend Git tree is unchanged and equals the independently
validated policy/build branches (`63c8bafd516cecead35818bc4654f9107dbb7f5e`):
146 tests, TypeScript and Vite passed once for these identical sources. Root
also verified all four frozen implementation/test/fixture hashes, compilation,
diff checks and the actual inert no-command invocation. These checks used no
actual model responses, provider, native Studio, account or service operation.
Ready for root exact-path CLI commit and draft PR; CI remains separate.
