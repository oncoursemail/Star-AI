# Discord: create the settings file the docs promise
docs/STAR_DISCORD_SETUP.md says %USERPROFILE%\.star\discord-settings.env is 'created for you', but SETTINGS_TEMPLATE in star/discord_bot/local_config.py is never written. Make `scripts\star_discord.cmd doctor` (and the bot's first start) write the template if the file is missing (never overwrite an existing file; never write the token there). Align the doc's defaults table with the code (DM chat, images and lesson candidates default OFF in code). Tests with a temp HOME. Acceptance: pytest green; doc and code agree.
claimed by lane A at 2026-10-14T03:11:23Z
PR: https://github.com/oncoursemail/Star-AI/pull/334
Result: ensure_settings_file() writes the template on doctor/smoke/start if missing; docs defaults aligned.
Tests: discord tests 66 passed; full pytest 6512 passed.
