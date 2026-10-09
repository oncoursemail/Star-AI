# STAR Windows build and packaging

Target: Windows 11 x64, Python 3.11, PySide6, PyInstaller 6 and Inno Setup 6.

## CI release pipeline

The [Windows workflow](../.github/workflows/windows-desktop.yml) runs the offline suite and PyInstaller under GitHub's Windows runner; it runs the packaged `STAR.exe --doctor` through `Start-Process -PassThru -Wait` (GUI-subsystem executables don't reliably populate `$LASTEXITCODE`). It then packages the output with Inno Setup and provides both `STAR-Genesis-Windows-x64.zip` and an upgradeable `STAR-Setup-vX.Y.Z.exe`.

Once that job succeeds on `main`, the release job (the *only* step with `contents:write`) creates version tag `vX.Y.Z` and publishes both binaries plus checksums. It does not overwrite releases if the same version already exists. Increase `star/version.py` to create a subsequent version.

## Local developer build

Install Python 3.11 and Inno Setup 6, clone the source and run `./scripts/build_windows.ps1` in PowerShell. Builds and tests happen before packaging. If Inno Setup is not installed, the script can still produce the portable ZIP.

## How upgrading works

Use the **Setup** binary rather than the portable ZIP for the friendliest installation. Setup uses a stable Inno AppId, a per-user app directory and default Start Menu entry. It updates installed files in place while keeping model weights, images, projects and conversations under `%APPDATA%\\STAR`. Windows may show a publisher warning for unsigned builds. Check the GitHub source commit and release checksums before running any unsigned program.

Automatic in-app update from a **private** GitHub repository requires GitHub CLI authentication. The self-update helper is a separate experimental flow and needs locked-file / rollback testing on Windows.

See [research and known caveats](RELEASES_AND_MODELS.md).
