@echo off
rem Optional: start STAR's Discord bot automatically when you sign in to Windows (Task Scheduler), without
rem STAR Desktop. You run this yourself; nothing installs it for you. No PowerShell and no administrator needed.
rem   scripts\star_discord_autostart.cmd print     show the task (creates nothing)
rem   scripts\star_discord_autostart.cmd install   create the task "STAR Discord bot" for your account
rem   scripts\star_discord_autostart.cmd status, start, stop, remove
rem The bot runs with the Python this script finds: %STAR_DISCORD_PYTHON% if set, else .venv in this
rem checkout, else the py launcher (3.12, then 3.11). That Python needs requirements-discord.txt installed.
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "PY="
if defined STAR_DISCORD_PYTHON (
  set "PY=%STAR_DISCORD_PYTHON%"
) else if exist ".venv\Scripts\python.exe" (
  set "PY=%CD%\.venv\Scripts\python.exe"
) else (
  py -3.12 -c "" >nul 2>nul && set "PY=py -3.12"
)
if not defined PY py -3.11 -c "" >nul 2>nul && set "PY=py -3.11"
if not defined PY (
  echo No Python found. Set STAR_DISCORD_PYTHON to the python.exe that has the Discord library installed.
  popd
  exit /b 1
)
if "%PY:~0,3%"=="py " (
  %PY% scripts\discord_autostart_task.py %*
) else (
  "%PY%" scripts\discord_autostart_task.py %*
)
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
