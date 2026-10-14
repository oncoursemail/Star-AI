@echo off
rem STAR Discord bot launcher for Windows (no PowerShell needed).
rem Settings: %USERPROFILE%\.star\discord.env  (DISCORD_BOT_TOKEN=..., written by you, never committed)
rem           %USERPROFILE%\.star\discord-settings.env  (your Discord IDs and opt-in switches)
rem   scripts\star_discord.cmd          run the bot (stop with Ctrl+C)
rem   scripts\star_discord.cmd doctor   offline readiness check (no network)
rem   scripts\star_discord.cmd smoke    live read-only login check (sends no messages)
rem Python: %STAR_DISCORD_PYTHON% if set, else .venv in this checkout, else the py launcher (3.12/3.11).
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
if defined STAR_DISCORD_PYTHON (
  "%STAR_DISCORD_PYTHON%" -m star.discord_bot %*
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m star.discord_bot %*
) else (
  py -3.12 -m star.discord_bot %* || py -3.11 -m star.discord_bot %*
)
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
