# ✦ STAR Intelligence — Genesis v0.7.0

**A local-first AI for creators on Windows 11 — now with a React-powered desktop experience.**

STAR brings local model inference, a real chat workspace, image/video/audio references, persistent project memory, Roblox Studio MCP tools, and measured analytics into one app. It uses **no mandatory hosted model API key**. Starting with v0.7, the desktop interface and the public website share a React + TypeScript + Vite visual system, while all existing Python AI and storage modules stay intact.

> **Product status:** STAR is an evolving prototype. A successful GitHub build is not a benchmark proving frontier-model intelligence or fault-free Roblox gameplay. Local model weights must still be downloaded separately on your PC. The legacy UI remains available as `STAR.exe --legacy-ui`.

## Download / Updates

**[⬇ STAR Windows Setup — latest release](https://github.com/oncoursemail/Star-AI/releases/latest)** · [All releases](https://github.com/oncoursemail/Star-AI/releases) · [Report a problem](https://github.com/oncoursemail/Star-AI/issues)

The `oncoursemail/Star-AI` repository is intentionally **PUBLIC**, so downloads work without a GitHub account, GitHub CLI or a special public mirror. GitHub Actions builds the frontend, runs tests, bundles it into PyInstaller, tests the packaged EXE, and only then publishes `STAR-Setup-vX.Y.Z.exe` and a portable ZIP. Install a newer Setup on top of the old version; `%APPDATA%\STAR` (conversations, references, downloaded models, settings) is **preserved**. The verified in-app updater can stage publicly available installers.

### Three-step start

1. Install the latest `STAR-Setup-vX.Y.Z.exe` from Releases. Existing installations are upgraded in place.
2. Open STAR → **STAR Brain** → **Download & launch STAR Brain** to download a checksum-verified small local model and inference engine from trusted providers. No LM Studio or hosted model API key is required. Plan for several gigabytes of disk space.
3. Open **Chat**, ask questions, attach references or connect an unpublished Roblox Studio test place under **Developer tools**. Start with read-only access.

### Website

The public-facing React website builds from `frontend/` and is intended for **https://oncoursemail.github.io/Star-AI/**. Pages deployment requires one-time GitHub setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**. A passing website-build artifact does not by itself prove the live Pages domain has been enabled or deployed.

## STAR's new interface

- **React 19 + TypeScript + Vite** shipped offline inside Qt WebEngine as part of the Windows application; not a website wrapping a remote service.
- Restrained **OLED-black + warm gold** surfaces, real Lucide SVG icons, Motion page and message transitions, readable rich Markdown responses, copy actions, reference chips, keyboard-friendly composer, reduced-motion behavior.
- True on-device **Analytics** using existing `star/analytics.py` SQLite records, displayed with Recharts. Empty state when no real task data exists.
- **Projects**, **STAR Brain**, **Tools**, **Library**, **Settings** share a consistent spacing/typography system. The previous native advanced tools remain accessible via `STAR.exe --legacy-ui` during migration.
- **A restricted Qt WebChannel** connects the local React UI to existing Python services. External websites cannot invoke the bridge; internal Qt navigation is limited to the bundled UI. GitHub or other tokens are not accessible to the model/UI.

Read the [implementation, research sources and QA plan](docs/STAR_REACT_REDESIGN.md).

## Architecture

| Component | Implementation |
|---|---|
| Desktop + public site UI | `frontend/` (React, TypeScript, Vite, Motion, Lucide, Recharts) |
| Windows host / permissions | `star/react_shell.py` — Qt WebEngine + Qt WebChannel allowlist |
| Legacy native interface | `star/desktop.py`, `star/visuals.py` |
| Local intelligence | `star/agent.py`, `star/desktop_core.py`, `star/local_runtime.py`, `star/brain_setup.py` |
| Memory and analytics | `star/memory.py`, `star/knowledge.py`, `star/analytics.py` |
| Roblox Studio | `star/studio.py`, `star/policy.py` |
| Installer and GitHub Releases | `installer/STAR.iss`, `.github/workflows/windows-desktop.yml` |
| Website and Pages | `.github/workflows/website-pages.yml` (builds `frontend/dist`) |

**Data never migrates into the frontend package.** The existing SQLite stores and models remain in `%APPDATA%\STAR`; a new installer replaces the app directory only. STAR doesn't silently train its weights, merge self-written code or publish Roblox games.

## Develop locally (Windows 11)

```powershell
# Node.js 22+ and Python 3.11 x64 are required only when developing/building from source.
cd frontend
npm install
npm run test
npm run build
cd ..
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe star_desktop.py
```

To preview the website: `cd frontend && npm run dev`, then open the URL shown by Vite. `?preview=1` displays an explicitly read-only interface preview and cannot access a local user's files. On a real STAR desktop, Qt WebChannel enables authenticated local operations through a restricted Python action registry.

Windows packaging runs `scripts/build_windows.ps1`. `STAR.exe --doctor` verifies the bundled Python backend; browser/QWebChannel and GPU use also require live Windows acceptance testing.

## Research and product policy

- [React redesign and implementation decisions](docs/STAR_REACT_REDESIGN.md)
- [Official Roblox MCP](https://create.roblox.com/docs/studio/mcp)
- [Hugging Face model selection](docs/HUGGING_FACE_MODEL_GUIDE.md)
- [Desktop UX research](docs/STAR_DESKTOP_UX_RESEARCH.md)
- [Security and tool boundaries](docs/SECURITY_AND_AUTONOMY.md)
- [Feedback / issues](https://github.com/oncoursemail/Star-AI/issues)

The goal is to make STAR measurably better at **specific, verified Roblox workflows**, with proper tooling, memory, and testing. That is different from claiming it is already more generally intelligent than the strongest hosted models.
