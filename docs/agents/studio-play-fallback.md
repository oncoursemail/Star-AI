# Studio stuck in Play: display Stop fallback (board #161)

Problem (live 2026-10-16 07:58Z, Studio machine): after a playtest the connector's stop answered "Game Stopped" and
Studio stayed in Play. Only a click on Studio's Stop button on the server display fixed it. Until then the daily
playtest run (05:15Z) and the Studio Lab nightly (03:30Z) find no Edit place and fail.

## What changed
- `star/studio_play_fallback.py`: `PlayGuard.ensure_edit()` reads the state call (`get_studio_state`). Edit: done.
  Playing: (optionally send the connector stop,) wait `WAIT_SECONDS` (8 s) polling for Edit, then press Stop on the
  display (`display_stop`: `xdotool search --onlyvisible --name ' - Roblox Studio$'`, `windowactivate`, `key
  --clearmodifiers shift+F5`, DISPLAY from `STAR_STUDIO_DISPLAY`, default `:1`), wait again. Still Play: `edit=False`,
  log line `STUCK IN PLAY ... skipping the run`. Unknown state (no answer, odd text) never sends a key.
- `studio_lab_parallel.open_instance` (used by the playtest loop and the Studio Lab nightly) runs it first, with the
  connector stop: a Studio that stays in Play is not opened (`facts.problem` = "Studio is stuck in Play mode ...:
  skipped"), so the run ends at once instead of failing later. It also sets `guarded.play_guard`.
- `GameRun.playtest` (playtest learning) and `Lab.playtest` (Studio Lab): after their stop they call
  `play_guard.ensure_edit()`; if Studio is still in Play, `stopped` is False, which the existing code already treats as
  a Studio problem (new session; the next open skips). `playtest_learning.leave_edit_mode` uses the same guard.
- Timing data: both playtests log `play start: Studio confirmed in Xs, robot/probe up after Ys` and keep `start_s`
  and `robot_start_s` (`probe_start_s` in the lab) in the step/report JSON; `suite.json` per-iteration rows carry
  `start_s`. Slow starts (CPU shared with the night-school worker?) can now be read from the evidence.
- Shell scripts are unchanged (the check lives in Python, so both nightlies get it).

## Checks
- `tests/test_studio_play_fallback.py` (fakes only): Edit untouched; late connector stop needs no key; display
  press fixes it; still stuck is reported; unknown state sends nothing; xdotool command sequence; GameRun reports a
  stuck stop and logs the start time; `open_instance` skips a Studio that stays in Play; `leave_edit_mode`.
