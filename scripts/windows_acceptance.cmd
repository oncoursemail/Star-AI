@echo off
rem Runs scripts\windows_acceptance.py without PowerShell (script execution may be disabled).
rem Usage:  scripts\windows_acceptance.cmd snapshot before-upgrade
rem         scripts\windows_acceptance.cmd --help
rem Needs Python 3.9 or newer (python.org installer, or the "py" launcher). Standard library only.
rem Note: no parenthesised blocks here, so %errorlevel% is the real exit code of the Python run.
setlocal
set "HERE=%~dp0"

py -3 -c "import sys" >nul 2>nul
if errorlevel 1 goto trypython
py -3 "%HERE%windows_acceptance.py" %*
exit /b %errorlevel%

:trypython
rem The Microsoft Store "python" stub exists on many PCs but cannot run code, so test it first.
python -c "import sys" >nul 2>nul
if errorlevel 1 goto nopython
python "%HERE%windows_acceptance.py" %*
exit /b %errorlevel%

:nopython
echo Python 3.9 or newer was not found.
echo Install it from https://www.python.org/downloads/windows/ (tick "Add python.exe to PATH"),
echo or follow the "No Python" fallback commands in docs\STAR_WINDOWS_ACCEPTANCE.md.
exit /b 9009
