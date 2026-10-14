# Get STAR running on Windows 11

You should not need to understand model APIs, install Python, or open another AI application for the ordinary STAR experience.

1. Download `STAR-Setup-vX.Y.Z.exe` from the STAR Release page and install it. Newer versions replace previous installed versions while your `%APPDATA%\STAR` data remains separate.
2. Launch STAR and choose where answers come from. Open **More → Model** in the left sidebar (the page is titled **Model & connection**). If you use a STAR server, enter its connection under **Settings**, then click **Test connection**. To run a model on this PC instead, use the **Model on this PC** card and click **Download and start**. The download is a few gigabytes and may take a while; if it fails, click the button again, because verified parts are reused.
3. Open **Chat** and type what you need. Use the **+** button in the message box → **Add photos and files** to attach a Roblox screenshot (or **Look at my screen**, which asks first). Pick **Fast**, or another mode, with the mode button next to it.
4. Open **More → Analytics** to view real local task events and chart history. Empty charts are normal on a fresh install; no fake tasks are shown.
5. Open **Tools** only when you are ready for Roblox Studio. Use an unpublished sandbox place. In Studio, open **Assistant → Manage MCP Servers** and switch Studio on, keep your place open, then click **Test & discover Studio** and choose the open place. Leave **Allow edits in the selected Studio** off until inspection succeeds. STAR only edits its own test place; see [docs/ROBLOX_ACCESS.md](docs/ROBLOX_ACCESS.md).

**Keyboard shortcuts:** Enter sends your message; Shift+Enter adds a new line. In **Settings → Interface & performance**, turn on **Reduced motion** if animations feel distracting.

## STAR updates without GitHub login

STAR checks the official public [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest) of `oncoursemail/Star-AI`, which is the single update channel, and downloads a newer Setup anonymously with exact URL, size and SHA-256 checks. No GitHub login or GitHub CLI is required. If the release cannot be checked, STAR offers the Releases page in your browser instead.

## When something fails

Attach a screenshot of the exact error, not your tokens, password, key, or private `.env`. Useful logs and conversations live under `%APPDATA%\STAR`, and the version appears in STAR's sidebar.

More detail: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

STAR Genesis is evolving. The automated Windows build and offscreen GUI previews are useful checks, but real Windows graphics-driver inference and live Roblox game editing still require end-to-end tests on your PC.
