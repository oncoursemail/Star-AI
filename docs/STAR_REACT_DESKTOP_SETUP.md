# STAR React Desktop v0.7 — Windows setup, hosting and recovery

This release is a **local AI desktop app with a React interface**, not a chatbot hosted on the public website. AI inference still requires installing STAR Brain via its in-app flow.

## For Windows users

1. Open [STAR Releases](https://github.com/oncoursemail/Star-AI/releases/latest) and download the newest `STAR-Setup-vX.Y.Z.exe` after its Windows build has passed.
2. Close the old STAR before installing. The setup uses the same Inno Setup AppId, replaces previous application dependencies and preserves `%APPDATA%\STAR` conversations, task history, model downloads and project settings.
3. Launch **STAR Intelligence**. The React interface shows Chat, Projects, STAR Brain, Analytics, Developer Tools and Settings.
4. Click **STAR Brain → Download & launch STAR Brain** to get a supported local model. The install is multi-gigabyte and requires an initial internet connection; no separate LM Studio application is required.
5. Choose a test Roblox place, enable Studio MCP, then use **Tools → Find Studio instances**. Do not enable editing for a valuable published place before verifying the scope.

If the app cannot find its bundled React files, a source checkout can still run the previous Qt UI. The packaged build fails `--doctor` when React files are missing, so verified releases should ship the React UI.

## For developers

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt -r requirements-dev.txt
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe star_desktop.py
```

The native host uses `PySide6.QtWebEngineWidgets.QWebEngineView` with `QWebChannel`. The website and app shell share the same React build. The public preview is available using `?demo=1` and refuses to fake backend operations.

## GitHub Pages

- The public website is React/Vite built on GitHub Actions via `.github/workflows/website-pages.yml`.
- Owner must enable **GitHub Settings → Pages → Build and deployment → GitHub Actions** once if not already selected.
- Live site should be `https://oncoursemail.github.io/Star-AI/` after a successful deploy; verify before advertising it.
- The versioned installer still lives in GitHub Releases, separate from web hosting.

## Support and trust

No AI conversation data is uploaded to GitHub by the website. STAR's desktop version communicates only with its local Python core over Qt WebChannel. GitHub download and documentation links are regular public URLs. The bundle is currently unsigned; verify official Release source and its SHA-256 checksum.
