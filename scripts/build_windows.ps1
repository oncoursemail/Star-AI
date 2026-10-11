$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11 x64.' }
py -3.11 -m venv .venv
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-desktop.txt -r requirements-dev.txt 'pyinstaller>=6.10,<7'
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js 22+ is needed for the React UI build.' }
Push-Location frontend
try {
  & npm install --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw 'React dependency install failed' }
  & npm run typecheck
  if ($LASTEXITCODE -ne 0) { throw 'TypeScript check failed' }
  & npm run test
  if ($LASTEXITCODE -ne 0) { throw 'React tests failed' }
  & npm run build
  if ($LASTEXITCODE -ne 0) { throw 'React build failed' }
} finally { Pop-Location }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; aborting build.' }
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name STAR --icon assets/star.ico --add-data "frontend/dist;frontend/dist" --add-data "star/skill_packs;star/skill_packs" --hidden-import PySide6.QtWebEngineWidgets --hidden-import PySide6.QtWebChannel --hidden-import mcp.client.session --hidden-import mcp.client.stdio --hidden-import mcp.types --collect-all faster_whisper --collect-all ctranslate2 --collect-all av --collect-submodules pyttsx3 --collect-submodules jwt --collect-submodules cryptography star_desktop.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$exe = (Resolve-Path '.\dist\STAR\STAR.exe').Path
$doctor = Start-Process -FilePath $exe -ArgumentList '--doctor' -Wait -PassThru
if ($null -eq $doctor.ExitCode -or $doctor.ExitCode -ne 0) { throw "Packaged STAR.exe doctor failed: $($doctor.ExitCode)" }
Compress-Archive -Path '.\dist\STAR\*' -DestinationPath '.\STAR-Genesis-Windows-x64.zip' -Force
$iscc = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
if (Test-Path $iscc) {
  $version = (& $python -c "from star.version import __version__;print(__version__)").Trim()
  & $iscc "/DStarVersion=$version" 'installer/STAR.iss'
  if ($LASTEXITCODE -ne 0) { throw 'Installer packaging failed' }
  Write-Host "STAR-Setup-v$version.exe is in dist/"
} else { Write-Host 'Inno Setup not installed; portable ZIP is ready.' }
