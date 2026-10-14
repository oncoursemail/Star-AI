# Updater verification (v0.9.0 and later)

Run `pytest -q tests/test_updater_harness.py tests/test_public_release_updates.py tests/test_browser_updates.py` with no network access. The fake HTTP transport provides the release feed and the installer bytes; the fake process launcher records the Setup invocation. The tests cover newer/equal/older releases, SHA-256 rejection, staging, the order of desktop cleanup and process launch, silent Inno Setup flags, and cancellation (no pending candidate).

## Manual Windows acceptance check — still required

On a Windows machine, build and install the current signed/released STAR Setup and publish a *test* newer official release with a SHA-256 digest and matching asset size. Back up user data. Open **Settings → Updates**, check for the release, then choose **Install & restart**. Confirm that the desktop actually closes, the single-instance lock is released, Setup runs with `/SILENT /CLOSEAPPLICATIONS /NORESTART`, and STAR restarts at the new version without losing conversation history, settings, or models. Also verify that exiting without selecting **Install & restart** starts no Setup process. Repeat with a deliberately mismatched digest in a controlled test release and confirm no Setup starts. Check the installer/desktop event logs if the restart fails.

**Not automated:** actual Qt event-loop teardown, OS file locks, Inno Setup elevation/UAC, installed file replacement, code-signing/SmartScreen, and the post-install relaunch. The Python harness cannot prove any of these native behaviors; perform this manual check before release.
