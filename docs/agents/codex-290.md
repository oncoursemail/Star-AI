# Issue 290: native evidence and task-specific owner DMs

Worktree: `worktrees/wt-codex-290`; branch: `star/chatgpt-290-discord-evidence-20261016`.
Base: `origin/star/next` at `9e8c80e3`. Claim: #166.

Implemented locally; awaiting conductor review/push and native acceptance.
Read the issue through anonymous Python HTTPS after gh returned 401.
Read workspace rules, Discord migration and playtest-learning notes. Graphify's
installed launcher fails to canonicalize its script; using targeted source reads.
Usage percentages are unavailable; no additional agents launched.

Implemented: default-off native producer hooks, atomic local evidence staging, task
events delivered through the existing digest loop/ledger. Only fixed identifiers
and measured results leave native reports. No model lesson text, raw logs or
general desktop captures. Tests use fake native tools and fake Discord sends.

Studio maps/UI, playtest learning and the fixed first-party Blender recipe
worker now emit build-bound receipts. Studio captures are available before
playtesting; playtest-learning reports have no camera capture. Images are
normalized and stripped of metadata. Event delivery shares the existing
Night School timer, owner allowlist, cooldown and durable SQLite ledger.
Unknown sends never retry the same event. Independent review files can reject
an event or approve an exact image. Native results are clearly candidates,
not learned general skills or changed weights.

`/compare` can omit its result attachment to use the current native Lab image.
The existing pending-only correction flow retains full reference/capture/build
hashes, job/iteration/camera and exact owner constraints. Vision stays advisory.
Operator setup and limitations: `server/discord/native-evidence.md`.

Validation (2026-10-16, offline):
- Full audit-venv pytest: **9337 passed, 302 skipped, 29 failed, 15 errors** in
  428 seconds. Fresh APPDATA/HOME, no real owner configuration. The failures
  were caused by placing scratch directories inside the checkout (GitHub
  credential-path guards and git discovery) and Windows path length in
  Graphify caches. All four affected test files rerun with a fresh short
  external temporary directory: **179 passed**. No unrelated source fixes.
- Final broad affected set with the existing Discord-enabled venv: **502
  passed, 5 skipped** (platform-only symlink/Windows cases), 33 seconds. This
  includes all Discord, Studio Lab, playtest and Blender tests, plus offline
  producer-to-staging-to-delivery cases, concurrent publishers/reservations,
  stale/corrupt evidence, consent, image approval and ambiguous timeout tests.
- Ruff on changed areas: passed. `git diff --check`: passed.
- After the final native-delivery status display change: **45 passed, 2
  skipped** (native events, gateway fakes and learning digests); Ruff passed.
- Changed-file Pyright baseline: **16 known errors, no new errors**. The
  whole-repository run with installed library stubs reports unrelated baseline
  growth; CI uses a package-free interpreter. Baseline was not modified.
- Early attempts: one pytest command named a nonexistent test file (no tests
  ran); another used the shared system temp directory and hit permissions.
  Both were corrected. A new test fixture initially exceeded the report's
  attempts counter; corrected to a valid counter and rerun.

Logs remain locally under `.local/290/`; they are not committed. No frontend
files changed and no frontend checks were run. No push or PR created.

Remaining for Claude:
1. Review, push this branch from the primary clone and open a draft PR to
   `star/next`; check for an existing open PR first. Do not close issue #290
   as fully accepted yet.
2. Provision and verify same-host file permissions; native Studio/Blender and
   actual owner DM/restart/offline acceptance. No native run or deploy was
   attempted here. Another-host authenticated transfer remains operator work.
3. Broader issue phase 4: semantic verification of vision claims against native
   rig/VFX metadata and multiple timed/camera frames is not implemented. The
   new binding is conservative and cannot promote/reject lessons by itself.
4. Record wave end in root STATE.md; this worker kept edits in its own worktree
   and the claim points to this notes file.

Usage percentages remained unavailable; no weekly-limit reading above 80% was
received and no sub-agents were launched. Final commit identity is in the
conductor handoff message (the notes cannot embed their own commit hash).
