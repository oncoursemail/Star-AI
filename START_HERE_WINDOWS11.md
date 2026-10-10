# Get STAR running on Windows 11

You should not need to understand model APIs, install Python, or open another AI application for the ordinary STAR experience.

1. Download `STAR-Setup-vX.Y.Z.exe` from the STAR Release page and install it. Newer versions replace previous installed versions while your `%APPDATA%\STAR` data remains separate.
2. Launch STAR → **STAR Brain** → click **Download & Launch STAR Brain**. Downloading the local AI may take a while. If the download fails, use **Try again**; verified parts are reused. The system currently selects a modest Qwen model sized for an RTX 3060 Ti 8 GB.
3. Open **Chat**, attach a Roblox screenshot, and tell STAR exactly what you need.
4. Open **Analytics** to view real local task events and chart history. Empty charts are normal on a fresh install; no fake tasks are shown.
5. Open **Roblox Studio** only when ready. Create an unpublished sandbox, enable Studio MCP in Assistant, and use STAR → Roblox Studio to discover that window. Keep editing off until inspection succeeds.

**Keyboard shortcut:** Ctrl+Enter sends your message. In Settings, turn on **Reduce motion** if animations feel distracting.

## STAR updates without GitHub login

STAR checks the official public [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest) of `oncoursemail/Star-AI`, which is the single update channel, and downloads a newer Setup anonymously with exact URL, size and SHA-256 checks. No GitHub login or GitHub CLI is required. If the release cannot be checked, STAR offers the Releases page in your browser instead.

## When something fails

Attach a screenshot of the exact error, not your tokens, password, key, or private `.env`. Useful logs and conversations live under `%APPDATA%\STAR`, and the version appears in STAR's sidebar.

STAR Genesis is evolving. The automated Windows build and offscreen GUI previews are useful checks, but real Windows graphics-driver inference and live Roblox game editing still require end-to-end tests on your PC.
