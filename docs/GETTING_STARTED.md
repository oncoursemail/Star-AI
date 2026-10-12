# Getting started with STAR v0.9.0

STAR v0.9.0 is a **source release candidate**, not a confirmed public Windows installer. Use [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest) to find the latest published installer. At the time of the release acceptance document, the public installer was v0.8.1. Some features below need a separate setup or real Windows test.

## 1. Install or upgrade from v0.8

1. Download the Windows Setup from [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest). Do not treat a branch build or pull request as a published installer.
2. Before upgrading, close STAR and copy `%APPDATA%\STAR` somewhere safe.
3. When a v0.9.0 Setup has actually been released, install it over the older version. Do not delete your data folder.
4. Open STAR and check old conversations, references, projects, settings and downloaded models.

The installer is designed to preserve `%APPDATA%\STAR`, including conversations, references, model files and settings. Migration of single-stream chat history into threads is designed to keep old user messages. A real v0.8-to-v0.9.0 upgrade on the user's Windows profile is **not confirmed**. The old desktop interface can be launched with `STAR.exe --legacy-ui` where that executable is installed.

### Administrator rights on Windows

Setup defaults to installing STAR **just for your Windows account (per-user)**, with **no administrator rights required** for installation or upgrades. You may instead choose **all users** in the installer dialog; this needs administrator approval. If STAR was already installed for all users, a newer Setup upgrades that shared installation in the same mode, and Windows asks for administrator approval **on every upgrade**. That prompt is expected. Do not disable Windows UAC to avoid it.

To tell which kind of installation you have, open **Windows PowerShell** (no administrator rights needed) and run this **read-only** check:

```powershell
$scopes = @(
  @{ Scope = 'Per-user'; Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' },
  @{ Scope = 'All-users'; Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' },
  @{ Scope = 'All-users'; Path = 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' }
)
foreach ($scope in $scopes) {
  Get-ItemProperty -Path $scope.Path -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -eq 'STAR Intelligence' } |
    ForEach-Object { [pscustomobject]@{ 'Install type' = $scope.Scope; 'Install folder' = $_.InstallLocation } }
}
```

**Per-user** means the uninstall entry belongs to your Windows account (`HKEY_CURRENT_USER`); **all-users** means it is registered for the machine (`HKEY_LOCAL_MACHINE`). If both appear, more than one install may be registered: confirm which copy you intend to upgrade. If neither appears, you may be running the portable ZIP or STAR may be installed under a different Windows account.
## 2. Choose a brain: STAR Server or this PC

Open **Settings → Model & provider**.

- **STAR Server (LAN):** Your own server runs the model. Enter **Server address** (a private network IP ending in `/v1`), **Server model ID**, and **Server key**. Select **Save key**, then **Test server**. The test checks the address, credential, model list and a real reply. No model download is needed on this PC. Ordinary HTTP is not encrypted; only use a network you trust.
- **Local STAR Brain:** The model runs on this PC. Open **Model & connection** and use **Download and start** or **Start local model**. The local download needs several gigabytes of space. You can test it with **Test actual response** in Settings. Local operation does not require a hosted AI key.

These are choices, not automatic failovers. STAR must not silently send a local prompt to a hosted provider. The **Optional: on-device backup brain** panel appears when STAR Server is selected, but automatic failover to it is **not confirmed**. Remote hosted providers are separate, opt-in choices under **Model & provider**.

## 3. Fast, Auto and Agent

Choose a mode in the **Chat** composer.

- **Fast:** A quick response. It can read and calculate attached files; it is not the full tool-using agent.
- **Auto:** STAR chooses a route based on the request. This is the initial chat mode.
- **Agent:** STAR plans steps, uses permitted tools and checks the result. It may take longer. Permissions still apply.

The chat **+** menu also offers **Use a team**: four read-only reasoning stages, with text-only input, on your own hardware. It does not give Studio write access.

## 4. Ask Roblox questions

Ask a specific question using “Roblox”, “Luau”, or “Studio” and name the feature you need. For example: “In Roblox Studio, write a Luau ModuleScript for a server-side inventory, explain where to put it, and cite the official documentation.” When a documentation-backed answer is available, check the cited Roblox Creator Hub pages yourself. Official starting points: [Roblox Creator documentation](https://create.roblox.com/docs) and [Luau](https://luau.org/).

For answers with fenced Luau blocks, STAR can report a **Luau check**. The check covers compilation and type analysis; it does **not** mean STAR ran the code in Roblox Studio or verified game behavior. The evaluation harness also has separate mocked unit tests, which do not prove engine behavior. If the answer does not show a source or a check, do not assume one occurred.

## 5. Connect Roblox Studio on this PC

1. Open an unpublished, disposable test place in Roblox Studio.
2. In Studio, use **Assistant → Manage MCP Servers** and enable Studio as an MCP server. See the [official Studio MCP guide](https://create.roblox.com/docs/studio/mcp).
3. In STAR open **Tools → STAR local MCP · Roblox Studio**. Choose **This PC · your Studio** under **Studio connection**. Click **Test & discover Studio**.
4. Under **Open Studio instance**, choose the open place. Start with read access.
5. Only if needed, enable **Allow edits in the selected Studio**. Running Luau has a separate sandbox permission.

Read tools can inspect the game tree and scripts, console output and supported screenshots. Studio edits and playtests are limited to verified safe places: a suitable blank unsaved place or, with the separate own-account option enabled, a place belonging to STAR's configured Roblox account. Unknown, other people's, deny-listed, or unsafe places remain read-only. STAR rechecks the place before each write. Some connector operations, including asset insertion, mesh generation and uploads, are never offered. STAR cannot save or publish from Studio. Recorded edits carry an undo explanation; Studio's own Undo is the fallback after the turn. End-to-end behavior with a real Studio session is **not confirmed** by the branch's fake-connector tests.

## 6. Roblox Open Cloud key

Open **Settings → Roblox**. Create a narrowly scoped API key in the [Roblox Creator Dashboard](https://create.roblox.com/) for a private test experience owned by the account used for STAR. Use **Save key** and **Test**. The key is saved in the OS credential store. Do not paste keys into chat, source files or screenshots.

For the documented test pipeline, permissions include `universe-places` **Write** and `universe.place.luau-execution-session` **Read and Write**. Listing data store names is optional. In **Test experience**, supply the Universe ID and Start Place ID and select **Use this experience**. STAR checks ownership and private status before actions. Publish and test requests go into **Actions waiting for you** for explicit approval; they expire after 15 minutes. A publish request creates a **Saved** version, not a live publication. The Studio MCP connection and the Open Cloud key serve different purposes; one does not replace the other. See [Roblox access](ROBLOX_ACCESS.md).

## 7. Voice

In Chat, use **+ → Transcribe audio** for a transcript. The voice-call backend also supports microphone input, speech recognition, voice output and interruption, with command-line setup documented in [Voice calls](STAR_VOICE_CALLS.md). The full React call screen is **not confirmed**; the voice document says it is not built. Real microphone and speaker use was not verified there. Do not assume a working in-app live call from a tested audio-file pipeline. Voice model downloads and optional dependencies may be required.

## 8. Images

In Chat use **+ → Create image**. Choose a size and describe the result. Attach an image to request an edit; an optional second image can be a mask. To ask about a picture or local video, attach it to a normal message. For project references use **Projects → Visual references → Pin an image**.

Under **Settings → Where STAR generates**, choose where each supported media task runs. Local image creation uses ComfyUI and a separately installed model, with setup details in [Media](STAR_MEDIA.md). The document lists an NVIDIA GPU with 8 GB and about 12 GB of disk for its tested setup. Server-side image generation is documented as unavailable. An unavailable location is not silently replaced with another. Video understanding needs FFmpeg for frames; an optional voice recognizer supplies transcripts. Image and video workflows on other hardware remain **not confirmed**.

## 9. Skills and lessons

In **Settings → Advanced settings → Knowledge & expert tools**, turn **Enable Agent Skills** off to stop loading relevant local skill instructions. These are instructions, not code STAR silently executes. Roblox topic packs may also be controlled for developer/evaluation runs with `STAR_SKILL_PACKS=off`; see [Evaluation gate](evals.md). Turning off the general Agent Skills switch as a substitute for that separate pack override is **not confirmed**.

Under **Projects → What STAR has learned**, review **Waiting**, **Accepted** and **Set aside** lessons. Accepted notes can inform later answers in the same project. STAR does not retrain its model. You can edit, reject, delete, restore and export notes. Turn off **Accept my own corrections automatically** to review even your own short corrections. Turn off **Summarise raw notes in the background** to stop automatic summaries. This does not by itself remove previously accepted lessons; reject or delete those separately. See [Learning](STAR_LEARNING.md).

## 10. Data and backup

Open **Library → Open local STAR files** to see the data folder. On Windows, the documented main data location is `%APPDATA%\STAR`. It contains saved chats, references, settings, project knowledge and the existing model files identified by the release documents. SQLite stores include conversation and knowledge records. Some optional media or voice models may live elsewhere (for example voice models under `%LOCALAPPDATA%\STAR\voice-models`).

For a backup, close STAR, copy the whole `%APPDATA%\STAR` directory to another drive, and keep any separately configured ComfyUI, GGUF and voice model folders if you want to avoid downloading them again. Check that the copy is readable. A full restore on a clean Windows install is **not confirmed** by the release checks.

## 11. Troubleshooting: five first checks

1. **No reply / model offline:** Go to **Model & connection**. If local, **Start local model**, then **Settings → Test actual response**. If using a server, run **Test server** and inspect which check failed.
2. **STAR Server fails:** Check the private IP, `/v1` suffix, server process, model ID and saved key. The test needs a real model reply, not just an open port.
3. **Studio is missing or reads only:** Open a place, enable Studio MCP under **Assistant → Manage MCP Servers**, then **Tools → Test & discover Studio** and select its instance. Read-only mode is expected until safe-place checks and permissions pass.
4. **Roblox Open Cloud says missing permission or revoked:** In **Settings → Roblox**, use **Test**. Check the key's Creator Dashboard scopes, expiry and private test experience. Do not broaden permissions without a need.
5. **Image, voice or video does not work:** Check **Settings → Where STAR generates**, the installed local dependencies and available GPU memory. Media may need ComfyUI and FFmpeg. Live voice calls are still a prototype; a missing React call screen is not a model failure.

For exact supported behavior and acceptance limits, read [v0.9.0 release acceptance](STAR_V090_RELEASE_ACCEPTANCE.md), [Roblox access](ROBLOX_ACCESS.md), [Voice calls](STAR_VOICE_CALLS.md), [Media](STAR_MEDIA.md), [Learning](STAR_LEARNING.md), and [Evaluation gate](evals.md).
