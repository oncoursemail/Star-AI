# ✦ STAR Intelligence — Genesis v0.9.0

**A local-first AI for creators on Windows 11 — now with a React-powered desktop experience.**

STAR brings local model inference, a real chat workspace, image/video/audio references, persistent project memory, Roblox Studio MCP tools, and measured analytics into one app. It uses **no mandatory hosted model API key**. Starting with v0.7, the desktop interface and the public website share a React + TypeScript + Vite visual system, while all existing Python AI and storage modules stay intact.

> **Combined intelligence integration:** v0.9.0 unifies saved conversation threads, fast local chat, optional cloud providers, source-grounded web research, in-chat ComfyUI images, the read-only MCP Hub, four-stage STAR Teams and human-approved project memory. The local model is the default. Cloud/web APIs require your explicit configuration and credentials. Development details and release checks: [v0.9.0 integration acceptance](docs/STAR_V090_RELEASE_ACCEPTANCE.md).

> **Product status:** STAR is an evolving prototype. A successful GitHub build is not a benchmark proving frontier-model intelligence or fault-free Roblox gameplay. Local model weights must still be downloaded separately on your PC. The legacy UI remains available as `STAR.exe --legacy-ui`.

> **Shipping status (verified October 12, 2026):** STAR Genesis **v0.9.0** was published October 11, 2026 with [Windows Setup](https://github.com/oncoursemail/Star-AI/releases/download/v0.9.0/STAR-Setup-v0.9.0.exe), [portable ZIP](https://github.com/oncoursemail/Star-AI/releases/download/v0.9.0/STAR-Genesis-Windows-x64.zip), and [SHA-256 checksums](https://github.com/oncoursemail/Star-AI/releases/download/v0.9.0/SHA256SUMS.txt). The [latest published Windows release](https://github.com/oncoursemail/Star-AI/releases/latest) is authoritative, not source changes or PR builds. Unmerged PR features are not in the published installer. Release publication does not verify every possible GPU, Windows profile, or Roblox workflow; see [release acceptance](docs/STAR_V090_RELEASE_ACCEPTANCE.md).

### Public release transparency and website handoff

[Latest published Windows release](https://github.com/oncoursemail/Star-AI/releases/latest) is the authoritative download for **v0.9.0**, published **October 11, 2026**. **PRs, CI artifacts and passing tests** do not establish that later source features ship in that installer or that GitHub Pages was deployed.

The public repository currently has **no licence file**; a public source tree does not itself grant an open-source licence. Automated Roblox scripting evaluations varied across dated runs: **13 / 34 on October 12, 2026**, versus **16 / 34 and 18 / 34 in earlier runs** (range **13–18 / 34**). A single run varies; do not interpret the highest result as a reproducible score. The earlier **11 / 23 creation** result has not been reproduced on the released code and is not a current release baseline. **16 Roblox v2 tasks** separately need Studio/manual assessment. These are **not a game-quality score** or proof that a game was completed.

See the [Website and release handoff checklist](docs/WEBSITE_RELEASE_CHECKLIST.md) for the published release and outstanding deployment/acceptance checks.

## Download / Updates

**[⬇ STAR Windows Setup — latest release](https://github.com/oncoursemail/Star-AI/releases/latest)** · [All releases](https://github.com/oncoursemail/Star-AI/releases) · [Report a problem](https://github.com/oncoursemail/Star-AI/issues)

The `oncoursemail/Star-AI` repository is intentionally **PUBLIC**. GitHub Releases here are the single official download/update channel; no separate public-downloads repository, GitHub account, GitHub CLI, or mirrored publisher is needed. GitHub Actions builds the frontend, runs tests, bundles it into PyInstaller, tests the packaged EXE, and only then publishes `STAR-Setup-vX.Y.Z.exe` and a portable ZIP. Install a newer Setup on top of the old version; `%APPDATA%\STAR` (conversations, references, downloaded models, settings) is **preserved**. The verified in-app updater now includes a React **Settings → Stay up to date** panel (in the React desktop), with a check/install/restart flow and progress, and must pass real Windows upgrade QA before general availability.

**Administrator prompts on Windows:** Setup defaults to a **per-user** installation (just your account), which does **not require administrator rights**. You can choose an **all-users** installation, which requires administrator approval. If your existing copy was installed for all users, **every upgrade** also needs the Windows administrator prompt; this is expected and must not be bypassed. To identify your install type, check STAR's Windows uninstall entry: `HKEY_CURRENT_USER` means per-user and `HKEY_LOCAL_MACHINE` means all-users. The [Getting Started guide](docs/GETTING_STARTED.md#administrator-rights-on-windows) shows a read-only check.

### STAR v0.9 AI and UI improvements

- **Qwen/llama.cpp 500 repair:** one first system message per request, including memory compaction; a real completion-based model health test.
- **Streaming local chat:** progressively renders text for basic conversations; complete protocol responses remain for authorized tool calls.
- **React website v2:** editorial OLED design, interactive illustrative workflow, real React UI preview, keyboard-accessible tour and reduced-motion support.
- **Desktop chat v2:** message search/copy, retry, meaningful task progress and a verified in-app updater. Chats and models stay outside the installation tree.

- **Unified intelligence tools:** Read-only MCP Hub, optional hosted inference and web research, four-stage specialist Teams, source-ranked reviewed knowledge and explicit memory corrections. Prior chats and models remain outside the upgrade directory.

Source-level unit/build checks cannot replace live Windows GPU, installer-upgrade and Roblox Studio acceptance testing.

### Getting started with v0.9.0

For setup, upgrades, connection choices, chat modes, Roblox Studio and Open Cloud, voice, images, skills, lessons, data backup and troubleshooting, read the [v0.9.0 Getting Started guide](docs/GETTING_STARTED.md).

1. Install the latest **published** Windows Setup from [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest). Back up `%APPDATA%\\STAR` before upgrading. v0.9.0 is published; its [October 11, 2026 GitHub release notes](https://github.com/oncoursemail/Star-AI/releases/tag/v0.9.0) report one tested upgrade from v0.8.0 on Windows 11, not exhaustive device coverage.
2. In **Settings → Model & provider**, choose **Local STAR Brain** or **STAR Server (LAN)** on your own network. Use **Model & connection → Download and start** for a local model, or set the server address, model and credential then choose **Test server**. No local model download is needed when using STAR Server.
3. In **Chat**, choose **Fast**, **Auto** or **Agent**. Open **Tools** to connect Roblox Studio on this PC, starting with read-only access. **Settings → Roblox** controls the separate Open Cloud key and private test experience.

STAR does not silently fall back to a hosted model. Studio writes require scoped permission and a verified safe place. Voice calls have a backend prototype, but the complete React call screen is **not confirmed**. Read the full guide before enabling editing or remote tools.

### Website

The public-facing React website builds from `frontend/` and is intended for **https://oncoursemail.github.io/Star-AI/**. Pages deployment requires one-time GitHub setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**. A passing website-build artifact does not by itself prove the live Pages domain has been enabled or deployed.

### Experimental building and Blender kit (source checkout only, off by default)

STAR also provides a distinct, **read-only architecture planning prototype** (`star_architecture_preview` and `star_architecture_compare_styles`) and a bounded Blender exterior generator described in the [architecture research and QA guide](docs/STAR_ARCHITECTURE_BLENDER_RESEARCH.md). Eight starter grammars support plans, editable source `.blend` and `.glb` exports, geometry audits and candidate collision hints. This does **not** prove production-quality environments, Roblox Studio import, validated collisions, device FPS, or inclusion in the published installer.

**Explicit opt-in:** architecture chat tools are offered only when `STAR_ARCHITECTURE_TOOLS=1` is set and the prompt matches a Roblox building/Blender request. The `roblox-architecture-blender` skill pack stays off by default until an independent evaluation passes. Blender export is a separate owner-run command line **from a STAR source checkout**; the installed app does not include this specific exporter script. The kit is distinct from the optional Blender MCP integration described below.

From a source checkout, with Blender installed locally:

```powershell
python -m star.architecture_pipeline examples/architecture/storybook_shop.json --out out/storybook-v1 --blender "C:\Path\To\blender.exe" --preview
```

Omit `--blender` and `--preview` for a plan-only run. The [Blender smoke workflow](.github/workflows/architecture-blender-smoke.yml) checks headless export, not screenshot quality or Roblox Studio acceptance.

## STAR's new interface

- **React 19 + TypeScript + Vite** shipped offline inside Qt WebEngine as part of the Windows application; not a website wrapping a remote service.
- Restrained **OLED-black + warm gold** surfaces, real Lucide SVG icons, Motion page and message transitions, readable rich Markdown responses, copy actions, reference chips, keyboard-friendly composer, reduced-motion behavior.
- True on-device **Analytics** using existing `star/analytics.py` SQLite records, displayed with Recharts. Empty state when no real task data exists.
- **Projects**, **STAR Brain**, **Tools**, **Library**, **Settings** share a consistent spacing/typography system. The previous native advanced tools remain accessible via `STAR.exe --legacy-ui` during migration.
- **A restricted Qt WebChannel** connects the local React UI to existing Python services. External websites cannot invoke the bridge; internal Qt navigation is limited to the bundled UI. GitHub or other tokens are not accessible to the model/UI.

Read the [repository map and agent coordination guide](docs/REPOSITORY_GUIDE.md) and [implementation, research sources and QA plan](docs/STAR_REACT_REDESIGN.md).

### Blender for STAR Brain 2 (experimental first-party MCP)

STAR's optional **local Blender MCP** lets Brain 2 create actual editable .blend scenes and Roblox-compatible .glb assets using a small, constrained scene recipe. It has no unrestricted model-authored Python, no third-party Blender addon and no public listener. Scene creation writes **new private per-project outputs only**, and is disabled by default.

Install Blender yourself from [Blender.org](https://www.blender.org/download/), then open **Tools → Blender for Brain 2**. Enable the connector, save settings, and run **Test local Blender**. Only then, if you wish, enable **Allow Blender scene creation** and save. You may specify the trusted Blender executable path if automatic local discovery fails.

The same first-party server is available to an explicitly configured source MCP client with \`python -m star.blender_mcp --settings <local-STAR-settings.json>\`. Optional owner-run smoke recipes live in \`examples/blender/\`. The connector does not install Blender or import/publish assets into Roblox automatically; Studio import, visual quality and live Blender performance still require device testing.

See [Brain 2 Blender MCP setup, architecture, examples and QA](docs/STAR_BLENDER_BRAIN2_MCP.md).

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

### Reference-guided Roblox environment craft (experimental)

The source tree contains an **experimental, offline environment art toolkit** for Roblox lighting and reference analysis (not part of the installed STAR.exe; run it from a source checkout with Python). It does **not** automatically reconstruct 3D assets or edit the current Studio place. Image metrics describe color/composition only and are not proof of visually identical scenes.

~~~powershell
python -m star.environment_craft inspect path\to\reference.png
python -m star.environment_craft compare path\to\reference.png path\to\render.png
python -m star.environment_craft lighting winter-shrine
python -m star.environment_craft foliage --quality medium
python -m star.environment_craft vfx falling-snow
~~~

Lighting, foliage and ambient VFX commands print **Luau review templates**, not executed changes. The foliage template requires separately authored, skinned tree bones. The bundled `roblox-environment-art` skill is **opt-in only** until it passes the evaluation gate. Read the [research, official technical sources, reference breakdowns and limitations](docs/STAR_ENVIRONMENT_CRAFT_20261011.md).

## Research and product policy

- [React redesign and implementation decisions](docs/STAR_REACT_REDESIGN.md)
- [Official Roblox MCP](https://create.roblox.com/docs/studio/mcp)
- [Hugging Face model selection](docs/HUGGING_FACE_MODEL_GUIDE.md)
- [Desktop UX research](docs/STAR_DESKTOP_UX_RESEARCH.md)
- [Security and tool boundaries](docs/SECURITY_AND_AUTONOMY.md)
- [Feedback / issues](https://github.com/oncoursemail/Star-AI/issues)

The goal is to make STAR measurably better at **specific, verified Roblox workflows**, with proper tooling, memory, and testing. That is different from claiming it is already more generally intelligent than the strongest hosted models.


## Genesis v0.9.0 integration (released; later work remains in development)

The combined release integrates saved conversation threads, a quiet React chat, Fast/Auto/Agent routing, optional hosted providers and web research, safe MCP tools, local image generation, four-stage read-only Teams, and explicitly approved project memory. The release notes report Windows upgrade and acceptance testing on one device; other hardware, Studio workflows, and a live updater cycle still require separate acceptance. [Combined integration and testing](docs/STAR_V090_RELEASE_ACCEPTANCE.md).
