# ✦ STAR Intelligence — Genesis v0.9.0

**A local-first AI for creators on Windows 11 — now with a React-powered desktop experience.**

STAR brings local model inference, a real chat workspace, image/video/audio references, persistent project memory, Roblox Studio MCP tools, and measured analytics into one app. It uses **no mandatory hosted model API key**. Starting with v0.7, the desktop interface and the public website share a React + TypeScript + Vite visual system, while all existing Python AI and storage modules stay intact.

> **Combined intelligence integration:** v0.9.0 unifies saved conversation threads, fast local chat, optional cloud providers, source-grounded web research, in-chat ComfyUI images, the read-only MCP Hub, four-stage STAR Teams and human-approved project memory. The local model is the default. Cloud/web APIs require your explicit configuration and credentials. Development details and release checks: [v0.9.0 integration acceptance](docs/STAR_V090_RELEASE_ACCEPTANCE.md).

> **Product status:** STAR is an evolving prototype. A successful GitHub build is not a benchmark proving frontier-model intelligence or fault-free Roblox gameplay. Local model weights must still be downloaded separately on your PC. The legacy UI remains available as `STAR.exe --legacy-ui`.

> **Shipping status:** The source version is v0.9.0, but the latest public binary is currently **STAR Genesis v0.8.1** on the [GitHub Releases page](https://github.com/oncoursemail/Star-AI/releases/latest), with Windows Setup, a portable ZIP, and SHA-256 checksums. The latest GitHub Release is the only authoritative public binary: a source commit, an unmerged pull request, or a passing PR build is not evidence that a new installer has been released, and work in unmerged pull requests is **not** included in the public installer. A published Release is also not proof of hands-on Windows/GPU/Roblox acceptance. Native Windows model/GPU, credentials, Roblox Studio, and upgrade acceptance still require device testing; see [release acceptance](docs/STAR_V090_RELEASE_ACCEPTANCE.md) and the [Windows QA gate](docs/STAR_V08_RELEASE_GATE.md).

## Download / Updates

**[⬇ STAR Windows Setup — latest release](https://github.com/oncoursemail/Star-AI/releases/latest)** · [All releases](https://github.com/oncoursemail/Star-AI/releases) · [Report a problem](https://github.com/oncoursemail/Star-AI/issues)

The `oncoursemail/Star-AI` repository is intentionally **PUBLIC**. GitHub Releases here are the single official download/update channel; no separate public-downloads repository, GitHub account, GitHub CLI, or mirrored publisher is needed. GitHub Actions builds the frontend, runs tests, bundles it into PyInstaller, tests the packaged EXE, and only then publishes `STAR-Setup-vX.Y.Z.exe` and a portable ZIP. Install a newer Setup on top of the old version; `%APPDATA%\STAR` (conversations, references, downloaded models, settings) is **preserved**. The verified in-app updater now includes a React **Settings → Stay up to date** panel (in the React desktop), with a check/install/restart flow and progress, and must pass real Windows upgrade QA before general availability.

### STAR v0.9 AI and UI improvements

- **Qwen/llama.cpp 500 repair:** one first system message per request, including memory compaction; a real completion-based model health test.
- **Streaming local chat:** progressively renders text for basic conversations; complete protocol responses remain for authorized tool calls.
- **React website v2:** editorial OLED design, interactive illustrative workflow, real React UI preview, keyboard-accessible tour and reduced-motion support.
- **Desktop chat v2:** message search/copy, retry, meaningful task progress and a verified in-app updater. Chats and models stay outside the installation tree.

- **Unified intelligence tools:** Read-only MCP Hub, optional hosted inference and web research, four-stage specialist Teams, source-ranked reviewed knowledge and explicit memory corrections. Prior chats and models remain outside the upgrade directory.

Source-level unit/build checks cannot replace live Windows GPU, installer-upgrade and Roblox Studio acceptance testing.

### Getting started with v0.9.0

For setup, upgrades, connection choices, chat modes, Roblox Studio and Open Cloud, voice, images, skills, lessons, data backup and troubleshooting, read the [v0.9.0 Getting Started guide](docs/GETTING_STARTED.md).

1. Install the latest **published** Windows Setup from [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest). Back up `%APPDATA%\\STAR` before upgrading. v0.9.0 is still a source candidate until a public release is verified; installer upgrade testing on real Windows hardware is **not confirmed**.
2. In **Settings → Model & provider**, choose **Local STAR Brain** or **STAR Server (LAN)** on your own network. Use **Model & connection → Download and start** for a local model, or set the server address, model and credential then choose **Test server**. No local model download is needed when using STAR Server.
3. In **Chat**, choose **Fast**, **Auto** or **Agent**. Open **Tools** to connect Roblox Studio on this PC, starting with read-only access. **Settings → Roblox** controls the separate Open Cloud key and private test experience.

STAR does not silently fall back to a hosted model. Studio writes require scoped permission and a verified safe place. Voice calls have a backend prototype, but the complete React call screen is **not confirmed**. Read the full guide before enabling editing or remote tools.

### Website

The public-facing React website builds from `frontend/` and is intended for **https://oncoursemail.github.io/Star-AI/**. Pages deployment requires one-time GitHub setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**. A passing website-build artifact does not by itself prove the live Pages domain has been enabled or deployed.

## STAR's new interface

- **React 19 + TypeScript + Vite** shipped offline inside Qt WebEngine as part of the Windows application; not a website wrapping a remote service.
- Restrained **OLED-black + warm gold** surfaces, real Lucide SVG icons, Motion page and message transitions, readable rich Markdown responses, copy actions, reference chips, keyboard-friendly composer, reduced-motion behavior.
- True on-device **Analytics** using existing `star/analytics.py` SQLite records, displayed with Recharts. Empty state when no real task data exists.
- **Projects**, **STAR Brain**, **Tools**, **Library**, **Settings** share a consistent spacing/typography system. The previous native advanced tools remain accessible via `STAR.exe --legacy-ui` during migration.
- **A restricted Qt WebChannel** connects the local React UI to existing Python services. External websites cannot invoke the bridge; internal Qt navigation is limited to the bundled UI. GitHub or other tokens are not accessible to the model/UI.

Read the [repository map and agent coordination guide](docs/REPOSITORY_GUIDE.md) and [implementation, research sources and QA plan](docs/STAR_REACT_REDESIGN.md).

### Reference-guided Roblox environment craft (experimental)

STAR includes an **offline, opt-in environment art toolkit** for Roblox lighting and reference analysis, building on its existing Roblox Studio guards. It does **not** automatically reconstruct 3D assets or edit the current Studio place. Image metrics describe color/composition only and are not proof of visually identical scenes.

~~~powershell
python -m star.environment_craft inspect path\to\reference.png
python -m star.environment_craft compare path\to\reference.png path\to\render.png
python -m star.environment_craft lighting winter-shrine
python -m star.environment_craft foliage --quality medium
python -m star.environment_craft vfx falling-snow
~~~

Lighting, foliage and ambient VFX commands print **Luau review templates**, not executed changes. The foliage template requires separately authored, skinned tree bones. The bundled `roblox-environment-art` skill is **opt-in only** until it passes the evaluation gate. Read the [research, official technical sources, reference breakdowns and limitations](docs/STAR_ENVIRONMENT_CRAFT_20261011.md).

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


## Genesis v0.9.0 integration (candidate)

The combined release integrates saved conversation threads, a quiet React chat, Fast/Auto/Agent routing, optional hosted providers and web research, safe MCP tools, local image generation, four-stage read-only Teams, and explicitly approved project memory. Windows CI and offline tests verify packaging; real GPU, cloud credentials, Roblox Studio, and a live updater cycle require separate user-device acceptance. [Combined integration and testing](docs/STAR_V090_RELEASE_ACCEPTANCE.md).
