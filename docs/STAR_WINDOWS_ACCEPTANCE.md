# STAR real Windows 11 acceptance run (issue #15)

**Status of the evidence:** none yet. CI builds the installer and runs `STAR.exe --doctor` and `--ui-doctor`, and the Python and React test suites pass offline, but none of that touches a graphics driver, a real model, the Windows credential vault, a real user profile or Roblox Studio. [Issue #15](https://github.com/oncoursemail/Star-AI/issues/15) stays **open** until a person attaches the evidence this run produces. Nobody should close it from the automated suite.

This document is the exact procedure. `scripts/windows_acceptance.cmd` automates the parts a computer can measure honestly (marked **[script]**) and writes them to one evidence folder. Everything marked **[manual]** needs a human to look at the screen and write down what happened. The companion release checklist is [STAR_V090_RELEASE_ACCEPTANCE.md](STAR_V090_RELEASE_ACCEPTANCE.md).

## What you need

- A physical Windows 11 x64 PC (the target is an RTX 3060 Ti, 8 GB; any Vulkan GPU also exercises the engine). Prefer a **disposable Windows account** or a PC whose `%APPDATA%\STAR` you are happy to restore from backup.
- The installers to test: the previous public Setup (for example `STAR-Setup-v0.8.1.exe`) and the candidate Setup, plus `SHA256SUMS.txt` from the same release. A candidate from a pull request comes from its GitHub Actions run artifact, which has no release page; use the SHA-256 printed in the PR description.
- Python 3.9 or newer for the helper script, from python.org or the `py` launcher. PowerShell script execution is **not** needed: use Command Prompt or Git Bash. A no-Python fallback is at the end.
- About 8 GB of free disk for the model and engine, and for backups.
- The helper script. Get it from a checkout: `git clone --depth 1 --branch star/fixes-20261010 https://github.com/oncoursemail/Star-AI STAR-src` (use `main` once this is merged). Run every command below from `STAR-src`.

All commands are for **Command Prompt** (`cmd.exe`) unless stated. Evidence goes to `%USERPROFILE%\STAR-acceptance` by default; use `scripts\windows_acceptance.cmd --evidence D:\my-folder <command>` to change it. The script never writes or deletes anything under `%APPDATA%\STAR`, never stores chat text, and only talks to `127.0.0.1` (plus `api.github.com` if you pass `--tag`).

Result codes in the evidence file: **PASS**, **FAIL**, **INFO** (a measured fact for you to read). Anything not run is listed as **NOT RUN** by `report`.

---

## Part A - Prepare

### W01 Back up `%APPDATA%\STAR` [manual, 1 command]

Close STAR first (tray icon, then Task Manager if needed: `taskkill /IM STAR.exe` and `taskkill /IM llama-server.exe`).

```bat
robocopy "%APPDATA%\STAR" "%USERPROFILE%\STAR-backup-pre-acceptance" /E /COPY:DAT /R:1 /W:1 /NFL /NDL
```

Expect: a final summary with `Failed : 0`. If that backup folder already exists from an earlier run, choose a new folder name instead of reusing it. If `%APPDATA%\STAR` does not exist you are on a clean PC; note it, and skip the preservation checks (W08) for the first install.

### W02 Baseline snapshot [script]

Run this on the OLD version, before installing anything.

```bat
scripts\windows_acceptance.cmd snapshot before-upgrade
```

Expect: `[INFO] snapshot:before-upgrade Snapshot written` with your data file count, the installed version (from the Windows uninstall registry), and the GPU name and driver if `nvidia-smi` exists. The JSON holds file names, sizes, SHA-256 hashes and table row counts, never message text.

### W03 Verify the installer you are about to run [script]

```bat
scripts\windows_acceptance.cmd verify-release "%USERPROFILE%\Downloads\STAR-Setup-v0.8.1.exe" --sums "%USERPROFILE%\Downloads\SHA256SUMS.txt" --tag v0.8.1
```

Expect `[PASS] W03b Matches SHA256SUMS.txt` and `[PASS] W03c Matches the digest GitHub records`. Do not run an installer that fails W03. (`W03a` simply prints the hash.) For a CI candidate there is no tag: omit `--sums` and `--tag` and compare W03a with the hash in the PR description.

---

## Part B - Install, upgrade and launch

### W04 Install over the old version [manual]

1. With the OLD version installed and having at least two saved chats, a downloaded model and one image, note the version in the sidebar.
2. Run the new `STAR-Setup-vX.Y.Z.exe`. The installer is per-user (no administrator) and installs to `%LOCALAPPDATA%\Programs\STAR`. Windows SmartScreen will warn because the build is unsigned; record that you saw it.
3. Tick **Launch STAR Intelligence** at the end.

Expect: the wizard reuses the previous folder; it replaces `_internal` only. It must not touch `%APPDATA%\STAR`.

### W05 STAR launches and the old runtime is gone [manual]

Expect: the window title reads `STAR Intelligence — vX.Y.Z` with the new version, the sidebar shows your old chats, and no error dialog appears. Record the exact version shown. (`W07` and `W08` below prove replacement and preservation by measurement.)

### W06 The packaged doctors [script]

```bat
scripts\windows_acceptance.cmd doctor
```

Expect `[PASS] W06a STAR.exe --doctor`, `W06b --ui-doctor` and `W06c --build-doctor`. `STAR.exe` is a windowed program, so its printed text may be empty; the exit code is the result. For an exact pull request build also pass the PR head commit: `scripts\windows_acceptance.cmd doctor --expect-sha <40-hex-commit>`; a mismatch fails W06c. Builds older than the source-stamping change (v0.8.x) carry no provenance, so W06c is **expected to fail** on them and is only meaningful for the candidate build.

### W07 Post-install snapshot [script]

Close STAR, then:

```bat
scripts\windows_acceptance.cmd snapshot after-upgrade
```

### W08 Personal data survived; runtime was replaced [script]

```bat
scripts\windows_acceptance.cmd compare "%USERPROFILE%\STAR-acceptance\snapshot-before-upgrade.json" "%USERPROFILE%\STAR-acceptance\snapshot-after-upgrade.json"
```

Expect `[PASS] preserve-files`: every non-volatile file is still there and every model, engine, image and media file has an identical SHA-256; `[PASS] preserve-db:conversations.sqlite3`: no table lost rows or columns (new columns are allowed: the migration is additive); `[PASS] runtime-replaced`. Any `FAIL` line names the file or table. A FAIL here is a data-loss bug: stop, restore from the W01 backup, and report it.

### W09 It is the React interface, loaded once [manual]

1. The window shows the sidebar with **New chat**, a centred composer reading "Message STAR...", and no Qt-style tabs.
2. Confirm STAR was not started with the legacy flag:
   ```bat
   powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='STAR.exe'\" | Select-Object -ExpandProperty CommandLine"
   ```
   This is an inline command, not a script file, so the execution policy does not block it. Expect no `--legacy-ui` in any line. (Task Manager > Details > right-click a column header > Select columns > Command line shows the same.)
3. There is no browser console in the packaged app, so check the symptom of a double-loaded channel instead: send one message and confirm the answer appears once and nothing in the history is doubled (W10 measures this).

### W10 The current prompt is stored once [script]

Send exactly this message in a new chat: `ACCEPT-MARKER-0001`. Wait for the answer. Then:

```bat
scripts\windows_acceptance.cmd count-marker ACCEPT-MARKER-0001 --expect-user 1
```

Expect `[PASS] W10 Prompt stored exactly once`, with a detail line such as `{"assistant": 1, "user": 1}`. The only number that matters is `"user": 1` (the assistant count is higher if the model repeated your text). Restart STAR, reopen the chat and run it again: still exactly one user row, and the UI shows the message once.

---

## Part C - The local AI

### W11 Install and start STAR Brain from the app [manual]

STAR Brain tab > **Download and start**. Record the time it took and watch the progress text.

Expect, from the code: the pinned llama.cpp Vulkan build (`engines\<tag>`) and `Qwen3.5-4B-Q4_K_M.gguf` plus the vision projector are downloaded, hash-checked, and STAR runs a real test completion before it shows **Ready**. A failed start is rolled back and the engine is stopped. Verify the files:

```bat
certutil -hashfile "%APPDATA%\STAR\models\qwen3.5-4b-q4\Qwen3.5-4B-Q4_K_M.gguf" SHA256
certutil -hashfile "%APPDATA%\STAR\models\qwen3.5-4b-q4\mmproj-Qwen3.5-4B-BF16.gguf" SHA256
```

Expect `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c` and `ae08d9d7eceb8f2d0672d61b5e6aa78b611f2942b55ed71d21414980cc454b91` (the values pinned in `star/brain_setup.py`; if the code was updated, trust the code).

### W12 "Test actual AI response" [manual + script]

[manual] STAR Brain > Model and connection details > **Test actual AI response**. Expect a short real sentence from the model, not just "connected". Screenshot it.

[script] With the Brain running:

```bat
scripts\windows_acceptance.cmd brain-check
scripts\windows_acceptance.cmd scan-logs
```

Expect `[PASS] W12a Model server lists a model`, `[PASS] W12b Single-system chat completion returns text` (this is the request shape STAR sends: one system message, then the user turn), and `[PASS] W12c Logs contain no known failure strings`. A `System message must be at the beginning` HTTP 500 is the regression this build must not show.

### W13 Real token streaming [script]

Produced by the same `brain-check` run: `[PASS] W13 Real token streaming (several separate deltas)` with the time to the first token and the number of content deltas. A single delta means the server returned the answer all at once, so token streaming did not actually happen. Record the printed numbers; they are the only latency figures this run produces. Also watch the UI: while the answer is generated the text must appear gradually, then be replaced by exactly one final message.

### W14 Why only one system message [script, optional]

```bat
scripts\windows_acceptance.cmd brain-check --negative-template
```

Prints `[INFO] W14`: whether this model's chat template rejects a second system message. It documents why STAR must never send one; it is not a pass/fail gate.

### W15 Missing or corrupted model file [manual]

Do this only after W01. Stop STAR and `llama-server.exe` first.

1. Missing: `ren "%APPDATA%\STAR\models\qwen3.5-4b-q4\Qwen3.5-4B-Q4_K_M.gguf" Qwen3.5-4B-Q4_K_M.gguf.hidden`, start STAR, STAR Brain > **Start model**. Expect an actionable message and **no** "Ready" badge. Record the exact text. Restore with `ren ... Qwen3.5-4B-Q4_K_M.gguf`.
2. Corrupted: append two bytes to the real model file with `cmd /c "echo.>>%APPDATA%\STAR\models\qwen3.5-4b-q4\Qwen3.5-4B-Q4_K_M.gguf"`, start the Brain, and record what STAR does: re-verifies and re-downloads, refuses, or reports ready. Re-run the `certutil` line from W11 to see whether the file is repaired. If it is not, copy the original back from the W01 backup folder (`models\qwen3.5-4b-q4\`).

The pass criterion is honesty: STAR must not tell you the Brain is ready with a bad file. Record what it does.

### W16 Offline after install [manual]

Turn on Airplane mode (or disable the network adapter), start STAR Brain, and chat. Expect normal local answers, no hosted-provider request, no error about missing internet except for features that need it (web research, updates). Re-enable the network afterwards.

### W17 Long context [script + manual]

```bat
scripts\windows_acceptance.cmd make-long-prompt
```

Open `%USERPROFILE%\STAR-acceptance\long-prompt.txt`, paste all of it into a new chat, send, wait for the answer, then:

```bat
scripts\windows_acceptance.cmd check-answer PELICAN-4821
```

Expect `[PASS] W17a` if the model found the code word buried in the middle. A FAIL with a working Brain means the context budget or model could not hold it: record the context size shown in Settings. Also note whether the app stayed responsive and whether the input/answer behaved with a prompt of that size.

### W18 Vision reference [manual]

Attach a PNG that contains short, distinctive text or colours you know (for example a screenshot with a visible word), ask "What text and colours do you see?". Expect an answer that matches the image. Record the file and the answer. Also attach a screenshot larger than 5 MB and note that STAR handles it (shrinks or refuses clearly).

### W19 Audio transcription [manual]

Use the composer's **+** menu > **Transcribe audio** with a short WAV you recorded, whose words you know. Expect the transcript in the composer. If the optional voice dependency is missing, STAR should say so clearly instead of failing silently; record which happened.

### W20 No hosted API key is required [manual + script]

Confirm no provider key was ever entered. The snapshot records any Windows credentials whose name contains "star":

```bat
scripts\windows_acceptance.cmd snapshot credentials-check
```

Expect `credentials_named_star` to be `null` in `snapshot-credentials-check.json`, with chat from W12 still working. This shows chat does not depend on a hosted key.

---

## Part D - Interface inspection [manual, with helper]

Take screenshots with `Win+Shift+S` and save them to `%USERPROFILE%\STAR-acceptance\shots` with the check ID in the file name, for example `W21-1050x680-chat.png`.

### W21 Window sizes

```bat
scripts\windows_acceptance.cmd window-size 1050 680
scripts\windows_acceptance.cmd window-size 1440 900
```

The helper sets STAR's client area exactly. At each size check the chat, Settings, STAR Brain and Projects pages: no clipped or overlapping text, the composer fully visible, the sidebar usable, no horizontal scrollbar.

### W22 Windows scaling

Settings > System > Display > Scale: repeat W21 at **100%**, **125%** and **150%** (sign out and in if STAR does not redraw). Record any blurry text, clipped controls or broken layout.

### W23 Keyboard and focus

- `Ctrl+K` focuses the composer from any page.
- `Esc` closes menus and dismisses notices.
- `Enter` sends; `Shift+Enter` adds a newline.
- `Tab` moves a visible focus ring through every control in order, never into a hidden element. Nothing traps focus.
- `Ctrl+,` opens Settings.

### W24 Content, retry, motion and contrast

- A reply containing a fenced code block shows a **Copy code** button; paste it elsewhere and compare exactly.
- Ask for a table and a bulleted list; both render with readable alignment.
- Send, then press **Stop** while it streams: the stop notice appears (see W41).
- Stop STAR Brain (`taskkill /IM llama-server.exe /F`), send a message: a clear failure notice and a **Retry** button appear. Start the Brain and click **Retry**: the same text is sent once.
- Settings: turn on **Reduce motion**: transitions stop. Check body text, placeholder and disabled-control contrast with Windows contrast themes off and on (`Alt+Left Shift+PrtScn`).

---

## Part E - Roblox Studio (disposable, unpublished place only)

### W30 Read-only discovery [manual]

1. In Roblox Studio create a new **unpublished** baseplate. Never use a published experience.
2. Enable the Studio MCP in the Studio Assistant settings as described in `docs/STAR_REACT_DESKTOP_SETUP.md`.
3. STAR > Roblox Studio > discover. Expect your window listed, with edit access still **off**.
4. Ask STAR to list the scripts and describe the place. Expect an accurate read-only answer and no change in Studio.

### W31 Scoped edit, undo and screenshot [manual]

1. Only after W30 passes, select the instance and enable scoped writes.
2. Ask for one small edit (for example, add a Part named `STAR_ACCEPT_TEST` to Workspace). Expect exactly that and nothing else.
3. Undo it in Studio with `Ctrl+Z` and confirm the place is back to its original state. Record any edit STAR made beyond what you asked.
4. Capture a screenshot from Studio showing the result and one showing the undo.

---

## Part F - Updates and failure handling

### W40 In-app update [manual]

1. Install an older official release (for example v0.8.1), run W02, then STAR > Settings > **Stay up to date** > **Check for updates**.
2. Expect it to name the newer official release. **Install & restart** downloads only the exact official `STAR-Setup-vX.Y.Z.exe` URL with size and SHA-256 checks, then restarts STAR.
3. Run W07 and W08 again: your data must be intact.
4. Disable the network and check again: expect the browser fallback message ("Open GitHub Releases in your browser"), not a crash and not a false "up to date".

### W41 Failures and Stop are truthful and survive a restart [manual + script]

This verifies the persisted failure records (a failed or stopped turn leaves an `event` row linked to its question).

1. Stop the Brain (`taskkill /IM llama-server.exe /F`), send `FAIL-TEST-1`. Expect a plain failure notice such as "Cannot reach STAR Brain".
2. Start the Brain, send a long request (for example "write 800 words about stars"), and press **Stop** after the first words appear. Expect a notice that the request stopped and that the draft was not saved as a completed answer.
3. Quit STAR completely, start it again, open the same chat. Expect both questions to still be there, each followed by its failure or stop notice (the page does not need a retry variable to show this).
4. Run:
   ```bat
   scripts\windows_acceptance.cmd db-check
   ```
   Expect `[PASS] W41a` (the `messages` table has `chat_id`, `status` and `reply_to`), `[INFO] W41b` showing at least one `failed` and one `cancelled` in the status counts, and `[INFO] W41c` with the number of questions that have no answer or failure record (questions from before this fix, or one running right now, are expected).

---

## Part G - File the evidence

```bat
scripts\windows_acceptance.cmd report
```

This writes `%USERPROFILE%\STAR-acceptance\ACCEPTANCE_REPORT.md` with every automated result and a table of manual checks marked **NOT RUN**. Fill in that table by hand (result, notes, screenshot file). Optionally export STAR's own bundle: Settings > Diagnostics and Review > **Export review bundle** (aggregate metrics only; the screenshot is opt-in).

Attach to issue #15, with the Windows build number (`winver`), GPU and driver, and the exact STAR version and commit from `STAR.exe --build-doctor`:

- `ACCEPTANCE_REPORT.md`, `results.jsonl`, `snapshot-*.json`, and your screenshots.
- Compress with `tar -a -c -f STAR-acceptance.zip -C "%USERPROFILE%" STAR-acceptance` (built into Windows 10 and 11).

**Do not** attach anything from `%APPDATA%\STAR` itself (chats, memory and settings are private) or the backup folder.

## What a fully passing run does and does not prove

It shows that on this PC, with this GPU and these files, the upgrade kept personal data, the packaged app and UI start, the pinned engine and model run, tokens stream, failures are reported truthfully, and the update path works. It does not prove model quality, performance on other hardware, Roblox gameplay correctness, provider quotas, or security. Record limitations next to results rather than rounding up.

## No Python? Minimum equivalents

```bat
robocopy "%APPDATA%\STAR" "%USERPROFILE%\STAR-backup" /E /COPY:DAT /R:1 /W:1 /NFL /NDL
certutil -hashfile "%USERPROFILE%\Downloads\STAR-Setup-vX.Y.Z.exe" SHA256
"%LOCALAPPDATA%\Programs\STAR\STAR.exe" --doctor
"%LOCALAPPDATA%\Programs\STAR\STAR.exe" --ui-doctor
curl.exe -s http://127.0.0.1:8080/v1/models
curl.exe -N -s http://127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"MODEL-ID-FROM-ABOVE\",\"stream\":true,\"max_tokens\":80,\"messages\":[{\"role\":\"system\",\"content\":\"You are concise.\"},{\"role\":\"user\",\"content\":\"Count from 1 to 12.\"}]}"
dir /s /b "%APPDATA%\STAR\models" "%APPDATA%\STAR\engines"
```

The `curl` stream should print many separate `data: {...}` lines, not one. Compare the file listings before and after upgrading by redirecting each `dir` to a text file and using `fc before.txt after.txt`.
