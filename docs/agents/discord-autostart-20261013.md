# discord-autostart-20261013 (wave 2026-10-13)

Goal: STAR's Discord bot starts automatically and reliably instead of living in a terminal tab.
Branch: star/discord-autostart-20261013 (worktree worktrees/discord-autostart, from origin/star/next 64c1982).
Board item #91. Builds on PR #226 (merged): docs/agents/discord-finish-20261013.md, docs/STAR_DISCORD_SETUP.md.

## What was built (all in the branch)
- `star/discord_supervisor.py`: `DiscordSupervisor` (start/stop/tick/status/close, thread via `begin()`), backoff 5..300 s,
  stable run (120 s) resets the crash count, give up after 10 quick crashes, exit 2/3 never retried, exit 4 = another bot
  runs (wait, take over when it stops). Everything with side effects is injectable. `resolve_launch` picks the Python
  (STAR_DISCORD_PYTHON, this Python if discord.py is importable and not frozen, checkout .venv, appdata discord-venv).
  Bridge actions: `discordStatus`, `discordStart`, `discordStop`, `discordSetAutostart`; `start_if_opted_in` on launch.
  Status carries only state words, counters, a fixed problem text, a list of missing settings: no token, IDs or paths.
- `star/discord_bot/instance_lock.py`: lock file `~/.star/discord-bot.lock` (msvcrt/fcntl, released by the OS on crash).
  `star/discord_bot/runtime_status.py`: `~/.star/discord-status.json` (pid, state, updated_at, guilds, latency_ms),
  written on ready / disconnect / every 30 s by the bot (`create_bot(config, reporter=...)`).
  `star/discord_bot/__main__.py`: `--log-file` (RotatingFileHandler 1 MB x 3), single-instance lock (exit 4), exit codes
  documented, brain key fallback from `~/.star/server_api_key` when neither env nor keyring has it (in memory only),
  config errors also logged (windowless starts have no console).
  `star/server_key_file.py`: `read_key_file` (import_key_file reuses it).
- Desktop: `Settings.discord_autostart` (default False, validated bool), `react_shell.py` creates the supervisor, autostart 3 s
  after launch if opted in, `close()` stops the bot right after ComfyUI and before the forced-exit timer.
  UI: `frontend/src/DiscordSettings.tsx` under Settings (after Voice), polls `discordStatus` every 4 s.
- Task Scheduler: `scripts/discord_autostart_task.py` + `scripts/star_discord_autostart.cmd` (print|install|status|start|stop|remove).
  XML task: logon trigger +30 s, current user, InteractiveToken, LeastPrivilege, pythonw.exe, restart on failure x99/1 min,
  no time limit. NOT installed by me.
- Docs: new section 4b in docs/STAR_DISCORD_SETUP.md.

## What ran (seen) vs only written
- RAN: tests/test_discord_supervisor.py (30) + tests/test_discord_autostart_task.py (10) with fakes; tests/test_close_on_request.py
  updated (16 pass); all discord tests in work/discord-venv (with discord.py): 102 passed, 2 skipped.
- RAN: full Python suite (audit venv, temp APPDATA): 6379 passed, 244 skipped (after fixing two tests that list the bridge's
  action sets: tests/test_close_on_request.py and tests/test_rbx_chat_attachments.py).
- RAN: frontend `tsc -b` clean, `vitest` for the new `discord-settings.test.tsx` (9) and settings-ui (24) pass; `vite build` ok.
  The full vitest run has 39 failures in StarPet/star-pet-desktop/brain-navigation/worked-examples files ("localStorage.clear
  undefined", Node 26): they fail the same way on an untouched worktree (clock-web), not from this change.
- RAN once by hand (scratchpad, not committed): real child process start/stop (tree killed, pid gone), real crash -> backoff,
  `python -m star.discord_bot` with an empty config exits 2, two-process lock (held / second refused / freed after kill).
  `star_discord_autostart.cmd print` printed the task XML; `install` was NOT run (nothing created in Task Scheduler).
- NOT run: the desktop app itself (Qt) with the new page; a live Discord login; the live bot was not restarted or touched.

## Owner notes
- The bot running now in the terminal tab is old code without the lock. Restart it once on the new code before enabling the
  Settings switch or the scheduled task, or two bots would answer.
- After this PR merges, point `star-discord.cmd` / the task at a stable checkout, not a temporary worktree.
- Install of the scheduled task is the owner's step: `scripts\star_discord_autostart.cmd print`, then `install`.

## Next steps
1. Pushed and PR opened against star/next (see the PR).
2. Owner: restart the terminal bot on new code, try Settings > Discord, optionally `star_discord_autostart.cmd install`.
