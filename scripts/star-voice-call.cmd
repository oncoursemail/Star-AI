@echo off
rem STAR voice call demo with a real microphone. Double-click to start, Ctrl+C to hang up.
rem First start creates .venv-voice next to this repository and downloads about 0.9 GB of models.
rem Extra arguments are passed on, for example:  star-voice-call.cmd --voice blend-heart-nicole --output speakers
setlocal
cd /d "%~dp0.."

rem --- Python environment (override with STAR_VOICE_PYTHON to reuse an existing one) ---
if not defined STAR_VOICE_PYTHON set "STAR_VOICE_PYTHON=%CD%\.venv-voice\Scripts\python.exe"
if not exist "%STAR_VOICE_PYTHON%" (
  echo Setting up the voice environment. This happens once and takes a few minutes...
  py -3.12 -m venv .venv-voice 2>nul || py -3 -m venv .venv-voice 2>nul || python -m venv .venv-voice
  if errorlevel 1 goto :nopython
  ".venv-voice\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv-voice\Scripts\python.exe" -m pip install --quiet -r requirements.txt -r requirements-voice.txt
  if errorlevel 1 goto :failed
)

rem --- Server address and key (the key is read into a variable and never shown) ---
if not defined STAR_SERVER_URL if exist "%USERPROFILE%\.star\server_url" set /p STAR_SERVER_URL=<"%USERPROFILE%\.star\server_url"
if not defined STAR_SERVER_URL set /p STAR_SERVER_URL=STAR Server address (for example http://10.17.0.146:8080/v1):
if not defined STAR_SERVER_API_KEY if exist "%USERPROFILE%\.star\server_api_key" set /p STAR_SERVER_API_KEY=<"%USERPROFILE%\.star\server_api_key"
if not defined STAR_SERVER_API_KEY (
  echo No server key found. Put it in %USERPROFILE%\.star\server_api_key or set STAR_SERVER_API_KEY.
  goto :failed
)

rem --- Voice model files (checked by size and SHA-256) ---
"%STAR_VOICE_PYTHON%" -m star.voice setup
if errorlevel 1 goto :failed

"%STAR_VOICE_PYTHON%" -m star.voice call %*
goto :end

:nopython
echo Python 3.11 or newer was not found. Install it from python.org, then run this file again.
:failed
echo.
echo The voice call could not start. See the message above.
:end
echo.
pause
endlocal
