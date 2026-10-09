# ✦ STAR Intelligence — React Genesis v0.7.0

**STAR is now transitioning to a shared React + TypeScript interface for its public website and Windows desktop.** The backend remains Python, local-first AI inference, memory, Roblox MCP, and checked updater. Source is public. The public website is a product site and interactive demo, not an online connection to your private AI.

- **Website (after Pages deployment):** https://oncoursemail.github.io/Star-AI/
- **Latest Windows installer:** https://github.com/oncoursemail/Star-AI/releases/latest
- **Preview:** visit the website with `?demo=1`. The demo does not invent AI responses or telemetry.
- **React interface + desktop installation:** [docs/STAR_REACT_DESKTOP_SETUP.md](docs/STAR_REACT_DESKTOP_SETUP.md)
- **Research, accessibility and implementation decisions:** [docs/STAR_REACT_DESIGN_RESEARCH.md](docs/STAR_REACT_DESIGN_RESEARCH.md)

The GitHub CI must first build and test STAR v0.7.0 before a Release download exists. Do not treat this README as proof of a running Windows package or deployed website.

## Development layout

| Path | Purpose |
|---|---|
| `frontend/` | React 19, TypeScript, Motion, SVG icons, Vite build and responsive website |
| `star/react_desktop.py` | Bounded Python / Qt WebChannel bridge |
| `star/desktop_core.py` | Local inference, conversation storage and project context |
| `star/analytics.py` | Real SQLite activity, not fabricated graphics |
| `star/brain_setup.py` | Local engine/model installation |
| `.github/workflows/website-pages.yml` | Build/deploy React site on GitHub Pages |
| `.github/workflows/windows-desktop.yml` | Compile React, package QtWebEngine Windows installer, test and release |

### Fundamental safety distinction

React renders information and invokes a **fixed native command allowlist**; it does not acquire unrestricted operating-system access. Uploaded media is selected through native dialogs and remains on disk. Model credentials and local project files are not exposed through website code.

---

# ✦ STAR Intelligence — Genesis v0.6.1

A **local-first Windows AI workspace** built around Roblox development and creative production. Native OLED-style interface, real project analytics, compact chat, image inputs, optional voice/video tools, and a model you can download directly inside STAR. **No paid model API key and no LM Studio are required for the default setup.**


## v0.6.1 — Click to update, restart, retain your work

**Updated October 9, 2026:** `oncoursemail/Star-AI` is currently **public** and contains both source and built Releases. The binary-only `Star-Intelligence-Downloads` repo is **not created** yet. While the source repo stays public, STAR v0.6.1 checks its Releases anonymously and downloads its versioned Setup directly; no GitHub CLI or login is needed. If the source repo becomes private, anonymous downloads stop and STAR falls back to the browser. After creating the separate public download repository, that channel takes priority and the source repository can return to private.

From STAR Brain → **Check for updates → Install update**, STAR verifies the GitHub asset SHA-256 and download size, asks whether to install, closes, lets Inno Setup replace the installed runtime and restart STAR, and removes only obsolete staged installer downloads on a subsequent start. The installer cleans the old `{app}\_internal` dependency tree to avoid stale modules and overwrites `STAR.exe`. It **never deletes `%APPDATA%\STAR`** (conversations, checkpoints, stored models and references). A first upgrade from a v0.6.0 installation may still require manually downloading the v0.6.1 Setup because the older updater didn't recognize publicly accessible source Releases. This feature requires real Windows installation/restart validation; only unit tests and CI packaging are automated.

Official download: [STAR Releases](https://github.com/oncoursemail/Star-AI/releases/latest). The executable is currently unsigned; verify its origin and don't treat a release digest as a code-signing certificate.

## Start in three steps

1. From **[STAR Releases](https://github.com/oncoursemail/Star-AI/releases/latest)**, download the latest `STAR-Setup-vX.Y.Z.exe` while public releases are being set up. Install normally; existing installations upgrade in place and keep data in `%APPDATA%\STAR`.
2. Open STAR → **STAR Brain** → **Download & Launch**. It downloads a chosen Qwen vision model and a compatible llama.cpp inference engine into your local user data folder. Downloads are multiple gigabytes; an NVIDIA driver and sufficient storage are needed. Model launch still requires a real Windows/GPU check.
3. Open **Chat**, type a request or attach an image. **Analytics** shows your *actual local* task runs and history. You can connect a disposable Roblox Studio MCP project later.

Your local RTX 3060 Ti 8 GB + 32 GB system RAM is supported as a **starting target**, not a guarantee that small open models match today's largest cloud models.

## New: STAR OLED Command Center

- Almost-black, calm design with a **single warm-gold accent**, real SVG icons and quieter navigation.
- Readable Chat workspace with copyable responses, compact composer, keyboard shortcut **Ctrl+Enter**, short message fades and **Reduce motion** in Settings.
- **Analytics** panel with custom Qt graphs showing real runs per day, messages, successful/failed tasks, tool actions and task timing. No fake sample counts.
- Project-scoped history/knowledge, restricted workspace tools and Roblox MCP discovery.
- Native Windows GUI screenshots captured by CI at multiple window sizes (as an artifact).

Design rationale and quality checklist: [Desktop UX Research](docs/STAR_DESKTOP_UX_RESEARCH.md) and [Design Tokens](docs/STAR_DESIGN_SYSTEM.md).

## Two GitHub repositories: public downloads + private code

**Private development:** [`oncoursemail/Star-AI`](https://github.com/oncoursemail/Star-AI) (this repository) stays Private.

**Planned public distribution:** [`oncoursemail/Star-Intelligence-Downloads`](https://github.com/oncoursemail/Star-Intelligence-Downloads) will contain **only** compiled Setup/portable installers, SHA-256 checksums, release notes and the public website. The separate public repository **must be created by its owner before it can be used**. It does not exist until GitHub confirms it.

After one-time configuration of an expiring token scoped to the public repository **only**, private GitHub Actions will publish signed-by-GitHub-upload Release assets from *passing Windows builds* and copy only seven allowlisted website files. The public channel enables **anonymous in-app update downloads**, without GitHub CLI or browser sign-in. Until it exists, STAR offers a private-Releases browser download and user-selected Setup fallback.

[Owner setup for both repositories](docs/STAR_PUBLIC_PRIVATE_GITHUB.md). **Never change the private source repo to Public.** STAR's own GitHub App for self-development should work on review branches with separately scoped permissions; private credentials do not flow into the AI model.

## Version and trust

The installer automatically upgrades earlier STAR versions under the same Windows App ID. Private source files, model weights, memories, tokens and conversations never belong in the public releases.

STAR is an active prototype; verified Python test cases are not a substitute for **GPU inference, real gameplay, visual QA, or signed production distribution**. Windowed PyInstaller `--doctor` and the Windows screenshot step are included in the build workflow; check the current GitHub Actions job and Release page for actual results before claiming v0.6.1 shipped successfully.

## Repository architecture

| Area | Location |
|---|---|
| Desktop UI | `star/desktop.py`, `star/design_system.py`, `star/visuals.py` |
| Real analytics and chart | `star/analytics.py`, `star/analytics_ui.py` |
| Conversational model + memory | `star/desktop_core.py`, `star/agent.py`, `star/knowledge.py` |
| Optional local engine/model download | `star/brain_setup.py`, `star/local_runtime.py` |
| User-authorized updates | `star/updates.py`, `star/version.py` |
| Roblox Studio MCP | `star/studio.py`, `star/policy.py` |
| Versioned Windows installer | `installer/STAR.iss`, `.github/workflows/windows-desktop.yml` |
| Public binary-and-site publisher | `scripts/publish_public_site.py`, `docs/STAR_PUBLIC_PRIVATE_GITHUB.md` |
| Public landing page | `site/index.html`, `site/styles.css`, `site/site.js` |
| CI-native UI screenshots | `scripts/capture_desktop_ui.py` |
| Developer/research tools | `star/github_app.py`, `star/orchestration.py`, `star/frontier_lab.py` |

## Developer setup

Windows 11 and Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe star_desktop.py
```

Build the local portable binary and Setup installer with `scripts/build_windows.ps1`, or use [GitHub Actions](https://github.com/oncoursemail/Star-AI/actions/workflows/windows-desktop.yml). Production releases should be code-signed before wide distribution.

## Other references

[Official Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp) · [Hugging Face model research](docs/HUGGING_FACE_MODEL_GUIDE.md) · [Security/Autonomy](docs/SECURITY_AND_AUTONOMY.md) · [Desktop research](docs/STAR_DESKTOP_UX_RESEARCH.md) · [Issue tracker](https://github.com/oncoursemail/Star-AI/issues)
