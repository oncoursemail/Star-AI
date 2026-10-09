$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11 x64.' }
py -3.11 -m venv .venv
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-desktop.txt -r requirements-dev.txt 'pyinstaller>=6.10,<7'
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; aborting build.' }
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name STAR --icon assets/star.ico --hidden-import mcp.client.session --hidden-import mcp.client.stdio --hidden-import mcp.types --collect-all faster_whisper --collect-all ctranslate2 --collect-all av --collect-submodules pyttsx3 --collect-submodules jwt --collect-submodules cryptography star_desktop.py
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
