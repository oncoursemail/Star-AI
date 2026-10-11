# STAR Windows build and packaging

Target: Windows 11 x64, Python 3.11, PySide6, PyInstaller 6 and Inno Setup 6.

## CI release pipeline

The [Windows workflow](../.github/workflows/windows-desktop.yml) runs the offline suite and PyInstaller under GitHub's Windows runner. It checks the actual packaged `STAR.exe --doctor`, `--ui-doctor` and `--build-doctor` through `Start-Process -PassThru -Wait` (GUI-subsystem executables don't reliably populate `$LASTEXITCODE`). It packages the output with Inno Setup and provides `STAR-Genesis-Windows-x64.zip`, `STAR-Setup-vX.Y.Z.exe` and SHA-256 checksums.

These checks prove backend imports, packaged React assets/imports and stamped source attribution. `--ui-doctor` does not open and interact with the default React window. CI's `capture_desktop_ui.py` renders the legacy Qt widget preview in an empty offscreen profile. Neither check proves an installed upgrade, the default React window's interactive behavior, owner-profile preservation, GPU support or a live Studio build. Those gates remain in [the Windows acceptance checklist](STAR_WINDOWS_ACCEPTANCE.md).

Once that job succeeds on `main`, the release job (the *only* step with `contents:write`) creates version tag `vX.Y.Z` and publishes both binaries plus checksums. It does not overwrite releases if the same version already exists. Increase `star/version.py` to create a subsequent version.

## Local developer build

Install Python 3.11 x64 and Node.js 22+, then run `./scripts/build_windows.ps1` in PowerShell from a reviewed, clean Git checkout. Inno Setup 6 is optional: without it, the script produces and checksums only the portable ZIP. The script installs build dependencies into the checkout's `.venv`, builds/tests the frontend, runs offline Python tests and compilation, and packages the app. Each native command's exit code is checked; a failed stage stops later packaging stages.

Every child process uses fresh profile directories under the ignored `.local/windows-build-profiles/<unique-id>/`, a null keyring backend, disabled user-site imports and Qt's offscreen platform. The builder restores all changed process environment variables and the working directory on success or failure. Scratch profiles remain available for inspection. It never installs or launches the normal interactive app and does not read the owner's STAR profile.

`scripts/stamp_build_info.py` checks the exact Git root, full source SHA and clean tracked/untracked state before dependencies are changed, again immediately before packaging, and once more after PyInstaller before any EXE doctor/archive. Unknown source files or tracked changes refuse packaging until reviewed and committed. Local npm installation uses `--package-lock=false` to avoid generating a new lockfile. Generated build paths are explicitly ignored: `.venv`, frontend assets/`tsconfig.tsbuildinfo`, scratch profiles, `star/build-info.json`, root `build/`, `dist/`, `STAR.spec`, portable ZIP and preview checksum file. Tracked source changes remain dirty even if an ignore rule matches. The builder does not delete old outputs automatically and refuses an existing same-version Setup EXE rather than attributing it to a new run; move that old installer before rebuilding.

The local stamp uses `build_event: local_build`, the same exact SHA for `source_commit` and `head_commit`, and an empty `run_id`. The app reports no GitHub Actions URL for it. Build metadata is informational, not a cryptographic signature or proof that every source file remained unchanged during a concurrent build; keep the checkout exclusively owned throughout packaging.

PyInstaller includes that metadata and collects keyring submodules consistently with CI. Before creating archives, the actual packaged EXE must pass all three doctors in the isolated profile, with `STAR_EXPECTED_HEAD_SHA` matching the verified checkout. `STAR-PREVIEW-SHA256SUMS.txt` lists only the portable ZIP and, when built successfully in this run, the Setup EXE. These checks do not execute Setup or satisfy installation acceptance.

## How upgrading works

Use the **Setup** binary rather than the portable ZIP for the friendliest installation. Setup uses a stable Inno AppId, a per-user app directory and default Start Menu entry. It updates installed files in place while keeping model weights, images, projects and conversations under `%APPDATA%\\STAR`. Windows may show a publisher warning for unsigned builds. Check the GitHub source commit and release checksums before running any unsigned program.

The public distribution channel is this repository's GitHub Releases. The experimental update flow still needs installed locked-file and rollback acceptance on Windows.

See [research and known caveats](RELEASES_AND_MODELS.md).
