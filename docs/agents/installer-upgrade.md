# Installer upgrade follow-up: #120 / #121

Codex, 2026-10-16. Board item #163. Work started from origin/star/next 9e8c80e3.
Worktrees: worktrees/wt-chatgpt-installer-120 and worktrees/wt-chatgpt-installer-121;
branches star/chatgpt-installer-120-20261016 and star/chatgpt-installer-121-20261016.

Earlier work (#217 rollback, #218 scope notice, #175 privilege docs/tests) is already
in staging. Both issues remain open; no matching open PR exists (public API checked).

In progress: #120 preserve interrupted-upgrade recovery copies, check loaded files
before moving the runtime, and report rollback failure honestly. #121 investigate
ambiguous install registrations and preserve the running copy's known scope.

Environment: gh returned HTTP 401; no sign-in or credential access attempted.
Anonymous public GitHub API works via Python; anonymous git fetch works with
per-command OpenSSL. No installer/compiler found in the usual installed location.
No Setup, real STAR or owner profile test performed. The required startup `star status`
itself attempted its built-in server lock probes and reported SSH failures; no direct
SSH, brain request or service operation was run by this task.
Usage percentages are unavailable; no sub-agents launched.

## Proposed changes

- #120: preserve .star-previous after an interrupted Setup; refuse before moving
  anything instead of deleting the only recovery copy. Check the existing executable
  and runtime files with an exclusive, non-truncating open before moving either.
  Preserve rollback flags until restoration succeeds; report failed restoration.
  Existing Restart Manager consent and shutdown handling remain in place.
- #121: retain the least-privilege default and explicitly pin UsePreviousPrivileges=yes
  for manual Setup. The updater passes /CURRENTUSER or /ALLUSERS only when the running
  executable folder matches an uninstall registration. Unknown scope stays with Setup.
  UAC on all-users updates is required; there is no automatic migration or registry edit.
  References: https://jrsoftware.org/ishelp/topic_setup_usepreviousprivileges.htm and
  https://jrsoftware.org/ishelp/topic_setup_privilegesrequiredoverridesallowed.htm.

## Validation completed

- #120 focused tests: 50 passed (rollback source checks, public release updates,
  close-on-request and updater harness).
- #121 focused tests: 45 passed (scope, privilege defaults, public release updates,
  updater harness). Installer scope launch cases mock the subprocess; no Setup ran.
- TypeScript: passed in both branches.
- First full pytest attempts stopped: inherited pytest temp directory inaccessible.
- Full Python run #120: 9,314 passed, 305 skipped, 33 failed, 15 setup errors.
  Full Python run #121: 9,321 passed, 305 skipped, 33 failed, 15 setup errors.
  The identical failures were caused by test temp paths inside the repository
  (GitHub fixture key guard and a git-not-a-repository test) or excessively long
  Windows Graphify cache paths. No changed test failed.
- Re-ran ALL FIVE affected files with a fresh short temp path outside the repository:
  test_github_write_scope.py, test_selfbuild_flow.py, test_shared_brain_build.py,
  test_shared_brain_variants.py, test_star_research.py. Result: **194 passed in each
  worktree**. This clears every failed/error case from the full runs. It is not a
  claim that a single uninterrupted full run was green.
- Frontend in each worktree: tsc -b passed; vitest 63 files / 562 tests passed;
  vite build passed (existing large-chunk warning). Default config bundling failed
  traversing a denied ancestor; used --configLoader native, and vitest additionally
  --maxWorkers 2 --minWorkers 1. No frontend source changes.
- Logs: each worktree's .local/pytest-full.log, pytest-environment-recheck.log,
  tsc.log, vitest.log and vite.log (ignored, not committed).
- Graphify code-only extraction/query ran. It reported partial extraction for 38
  files and two unrelated Luau permission errors; installer Pascal reviewed directly.

## Acceptance still required

Real disposable Windows install: graceful close with an active reply, elevated STAR
refusal, cancellation rollback, interrupted Setup backup preservation, helper-held
runtime file refusal, successful upgrade/relaunch. All-users UAC acceptance and
side-by-side/same-folder registration selection also need real Windows validation.
The checked-in manual W04c steps describe these; they are NOT a recorded pass.

## Review handoff

Each worktree has its own .local/pr-body.md with Fixes #120 or Fixes #121 and the
unverified native acceptance clearly stated. Public open-PR list checked twice;
neither issue already has a matching open PR. Commit/push outcome pending below.
