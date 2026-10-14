# Cloud PR review, 2026-10-13/14 (Claude)

Scope: every open PR targeting `star/next`, snapshot at 2026-10-14 ~05:00Z (#68 to #355; PRs opened after that,
from #356 on, are not reviewed here). No PR was merged: `gh release list` shows no v1.0 release yet (latest v0.9.0), so this was review
and repair only. Each PR got one comment that starts with "Cloud PR review (Claude, 2026-10-14): VERDICT".

Excluded on the lead's instruction (no comment, left for the owner): #270, #271, #274, #275, #278.
One exception: before that instruction arrived, a reviewer had already pushed two commits to #270 (3b44bef: cancel
extra candidates when the main answer fails, with a test; aabd2da: merge of star/next). They were not undone.

## Method

- Every PR was merged locally onto star/next 64c1982 (`git merge-tree` first, then a real merge in a scratch worktree).
  Then pytest ran on the PR's test files plus every test that imports a changed `star/` module (serial, temporary
  APPDATA). Frontend PRs also ran `tsc -b`, `vitest run` and `vite build` with Node 24.
- Full serial suites were run on several combinations, all with only load-related timing failures that also fail on
  plain star/next on this PC: the stack head #292 and the #289/#297 PRs (reviewer A), #283 and #266 (reviewer B), and
  star/next merged with 14 in-scope PRs from reviewer D's set (6514 passed, 255 skipped, 2 failed).
- Baseline on star/next on this PC: 6338 passed, 243 skipped, 2 failed (timing:
  `test_studio_transport_repair::test_permanent_validated_empty_is_bounded_across_requests_and_sleeps`,
  `test_voice_filecall::test_scripted_call_runs_turns_and_a_barge_in_and_saves_everything`).
- Environment notes: Node 26 (on PATH) defines its own `localStorage` and breaks about 39 vitest cases. Use the Node 24
  runtime from CLAUDE.md. `pytest -n` (xdist) adds timing failures and should not be used. A venv without `keyring` fails
  `test_desktop_genesis`.

## Totals

65 MERGE-READY, 26 NEEDS-OWNER, 7 CLOSE-DUPLICATE, 5 excluded (+ #356 not reviewed).

## Fixes pushed to PR branches

| PR | Commit(s) | What |
|---|---|---|
| #233 | 9e1f175 | merge star/next; resolved tool catalogue, intelligence ALL_TOOLS, skill-pack tests |
| #249 | c6cea13 | merge star/next; resolved chat_history_snapshot (opt-in reuse + with_sent_times) |
| #342 | 4a83b947 | CI fix: wiring test also reads SettingsPage.tsx (ProviderPanel moved there) |
| #355 | e02426d6 | test fix: default pack roblox-secure-remotes also matches the prompt |
| #268/#277/#292 | 57d1c46, 9863807 / 492962c, 9e54114 / 6a64fc2 | stack refreshed; failed first leg now wrapped to goal; settle wait no longer leaves Studio in Play on error |
| #289 | 29cdfdba | run_bpy filter escapes (random._os, typing.sys, from-imports) |
| #287 | 4ce7215 | owner DMs no longer answered "Lab reports are disabled" when Lab is off |
| #301 | 13fcc0b | focus colour no longer equal to the resting border |
| #240 | c76f21a, ddd6d8f | merge star/next; unknown node key no longer reported twice |
| #259 | a20cb88, 5225f9f | merge star/next; restore CRLF->LF normalization |
| #273 | efc50f8 | expired bundle rows no longer count toward the 500 cap |
| #280 | 6c0fb37 | exit-0 analyzer warnings no longer treated as malformed |
| #300 | 55709bf | only generic for-in loops excluded (all `for` loops were dropped) |
| #244/#252 | 3697397 / 6991adf | merge star/next |
| #269 | 321fc5f, a0b6cd7 | run lock out of world-writable /run/lock; merge star/next |
| #272 | 1decde1 | creator-docs licence string accepted (all main-corpus pairs were dropped) |
| #217 | 95f06917 | merge star/next (was 264 behind) |
| #308 | 153d006c | a locked settings.json is no longer moved aside |
| #314 | e7207bed, a5548c35 | untrusted-tool list union with the author's concurrent change |

## CLOSE-DUPLICATE (recommend closing)

- #68 (replaced by #233), #105 (by merged #192), #109 (by merged #196), #147 (by #185), #173 (by #181),
  #276 (same test as #310, they conflict), #353 (rules already in #330).

## NEEDS-OWNER (what decides each)

- Hold until after v1.0 / own gate: #233 (Settings switch), #249 (split instrumentation), #181 (real Luau VM run),
  #148 (night run with kept examples), #185 (competes with star/next's code_answer_completion; re-port only the
  malformed-tool retry), #254 (release vehicle, release lead), #317 (stacked on #254, adds package-lock.json).
- Protected eval content: #244, #245, #252 (fail the protected-closure guard), #338, #345, #348 (new evals/ suites).
- Product/safety decisions: #344 + #345 (reverse-engineering capability), #331 (licence of a bundled API dump),
  #283 (desktop supervises the Discord bot), #294 (new default voice, push-to-talk, no real-microphone test),
  #266 (touches protected eval_runner.py; UI may block up to 2 s per poll), #289 (Blender on brain 2),
  #269 (host details in README), #217 (installer not compiled here; no real upgrade run), #296 (stale snapshot),
  #321 (audit doc), #332 (overlaps #286 and #288), #327 and #351 (drafts still being worked on).

## Merge order (when v1.0 is out)

- Studio Lab stack: #292 alone contains #268 and #277 (or #268, #277, #292 in order).
- Preflight trio: #279, then #280, then #293. Lint: #291 before #300. #304 has a trivial import conflict with #280.
- Discord: #283, then #287, then #281 (all keep-both conflicts).
- Desktop.tsx: #283 and #340 before #342; #320 after #340. #336 vs #317 (siteHooks.ts). #337 vs #294 (test file).
- Python: #312 and #326 before #333. #286 before #332. #319 before #295 (build_windows.ps1). #327 vs #329 and
  #284/#355 (skill-pack lists: keep both).
- Small, independent and green, good first group: #272, #285, #299, #302, #305, #306, #308, #309, #310, #311,
  #313, #315, #316, #318, #322, #323, #324, #325, #328, #330, #334, #335, #339, #341, #343, #346, #349, #350.

## Incidents

- `git stash` is shared by all worktrees: reviewer B's stash pop in one worktree applied another session's WIP
  (24 star/*.py files). It was put back as stash@{0} "WIP (restored after accidental pop by cloud-pr-review-B; not
  mine)" and posted to all (msg #254). Owner of that WIP should check it.
- #181: another session had already merged star/next (f0fcfcf4); my identical resolution was not pushed.

Notes per reviewer: docs/agents/cloud-pr-review-A.md .. -D.md in the workspace folder (not in this repo).
