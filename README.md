# ✦ STAR Intelligence

**A local-first AI workspace for creators and Roblox developers on Windows 11.** STAR brings conversation, project memory, local models, scoped Roblox Studio tooling and optional creative integrations into a React-powered desktop application. On-device inference requires no hosted AI API key.

[Latest published Windows release](https://github.com/oncoursemail/Star-AI/releases/latest) · [Getting started](docs/GETTING_STARTED.md) · [Integration status](https://github.com/oncoursemail/Star-AI/pull/40) · [Report an issue](https://github.com/oncoursemail/Star-AI/issues)

> **Release status (checked October 11, 2026):** **v0.8.1** is the latest published Windows binary; **v0.9.0 is a source candidate**, not an available v0.9 installer. PRs, CI artifacts and passing tests are not public releases. Always check [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest) for current downloads.

> **Experimental software:** STAR is not a proven autonomous game studio, frontier model, or automatic model-training system. Optional providers, media tools and servers may need credentials, models and separate installations. Real Windows hardware, GPU, microphone, Roblox Studio and upgrade acceptance are still required for v0.9.

## Download and start

1. Download the latest **published** Windows Setup from [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest). Portable ZIP and `SHA256SUMS.txt` assets are on the release; verify downloads before running the unsigned installer.
2. Before upgrading, back up `%APPDATA%\STAR`. The installer is designed to preserve chat threads, reference files, settings and downloaded models there. A real v0.8-to-v0.9 upgrade remains to be validated on a Windows machine.
3. Select a brain. The **Local STAR Brain** runs llama.cpp on this PC after downloading a model. The v0.9 source candidate also supports an **owner-operated STAR Server** on a private LAN or a separately opted-in hosted provider. STAR never silently sends failed local requests to a cloud service.
4. In Chat, choose **Fast**, **Auto** or **Agent**, as supported by your installed release. If using Roblox, start with read-only Studio inspection in a disposable test place; editing and Open Cloud actions have separate approval boundaries.

For configuration, backups and troubleshooting, see the full [Getting started guide](docs/GETTING_STARTED.md). A public site or source-branch screenshot is not evidence that the same feature is present in the released installer.

## Capabilities of the v0.9.0 source candidate

**These are implemented or prototyped in the development source, not guaranteed in the currently downloadable v0.8.1 binary.**

| Area | What STAR does, and what it does not |
| --- | --- |
| **Workspace** | React 19, TypeScript and Qt WebChannel; persistent conversation threads, saved project context, streaming replies, Retry, task progress and measured local analytics. |
| **Model options** | Managed on-device llama.cpp / Qwen; an explicitly configured STAR Server (LAN); or opt-in Groq, OpenRouter, Gemini and Cerebras. No automatic hosted fallback. |
| **Roblox Studio** | Official MCP connection and scoped inspection. Edits require explicit permission, a verified safe test place, a change journal and human review. |
| **Roblox Open Cloud** | Separately approved version saves and Luau testing on an owner-selected private test experience. Not unrestricted publishing to live experiences. |
| **Research and skills** | Source-cited Roblox/Luau documentation, static Luau checks, twelve topic skill packs (five enabled by default), reviewed local knowledge and a regression evaluation gate. Static checks are not playtests. |
| **Teams and tool connections** | Bounded specialist reasoning stages; separately configured read-only MCP services and owner-approved tools. Self-written skills are candidates for review, not self-authorized deployments. |
| **Images and video** | Optional local ComfyUI image generation/editing; image understanding and a bounded set of sampled video frames, optionally paired with partial audio transcription. No full video playback analysis. |
| **Files and data** | Limited source-linked reading/search of PDF, DOCX, PPTX, XLSX, CSV and text attachments; exact table calculations. Input macros and documents are not executed. |
| **Voice** | Optional local speech recognition and Kokoro speech are prototyped; additional voice models/packages and end-to-end microphone/call-screen acceptance are incomplete. |

Provider credentials belong in the OS credential store, not the repository. File edits, Studio tool use and Open Cloud requests are controlled independently; instructions in retrieved pages, tool results or documents cannot grant themselves permissions. Read [Security and autonomy](docs/SECURITY_AND_AUTONOMY.md) and [Roblox access](docs/ROBLOX_ACCESS.md).

### Actual evaluation evidence

The stored **automated** v0.9 candidate baselines, recorded on October 11, 2026, are:

| Suite | Passed | Rate |
| --- | ---: | ---: |
| Roblox v2: 34 automated cases from 50 | **18 / 34** | **52.9%** |
| Creation v1: 23 automated cases | **11 / 23** | **47.8%** |
| Both baseline sets counted together | **29 / 57** | **50.9%** |

The other **16 Roblox v2 tasks** require Studio/manual evaluation and were not scored. The combined figure counts baseline tasks, **not** a combined production run with all skill packs. These are **not a game-quality score**, not visual or gameplay acceptance, and not a frontier-model benchmark. The measurements, prompt variability, task definitions and regression gate are documented in [Evaluation methodology](docs/evals.md).

## Public releases and the website

- **Official distribution:** [GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest), with actual Setup, portable ZIP and SHA-256 checksum assets. Do not construct download URLs from the unreleased source version.
- **Source integration:** development and reviews are tracked in [PR #40](https://github.com/oncoursemail/Star-AI/pull/40) and related drafts. A draft PR or a passing Windows packaging job is not a new public release.
- **Public React website:** built from `frontend/`, intended for [GitHub Pages](https://oncoursemail.github.io/Star-AI/), and deployed by [website-pages.yml](.github/workflows/website-pages.yml) after eligible pushes to `main`. Source commits alone do not deploy the website. The live Pages setting/domain must be checked independently.
- **Safe preview:** `npm run dev --prefix frontend` starts the website locally; `?preview=1` is an illustrative, read-only desktop preview. A normal browser does not receive STAR's native bridge, user files or model.

The site checks GitHub's public release API and shows the latest published stable build, with release-page fallbacks when data is unavailable. Its project progress board draws from public GitHub data—not tracking, user counts, fabricated benchmarks or an implicit claim of general availability.

[Website and release handoff checklist](docs/WEBSITE_RELEASE_CHECKLIST.md) records what remains blocked or unverified.

## Develop from source

Development baseline: **Windows 11 x64**, **Python 3.11**, **Node.js 22+**. Other platforms and real GPU behavior have not been comprehensively accepted.

```powershell
git clone https://github.com/oncoursemail/Star-AI.git
cd Star-AI
# Until v0.9 integration is reviewed into main:
git switch star/claude-integration-20261010

npm install --prefix frontend --no-audit --no-fund
npm run typecheck --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe star_desktop.py
```

Windows packaging uses `scripts/build_windows.ps1`. Packaged `STAR.exe --doctor` checks backend invariants but does not prove a real GPU model response, Qt bridge, installer upgrade or Roblox session works. The legacy interface is available as `STAR.exe --legacy-ui` on applicable builds.

### Repository map

| Directory or file | Responsibility |
| --- | --- |
| `frontend/` | Shared React desktop/public site, CSS, Vite and Vitest tests |
| `star/react_shell.py` | Restricted native Qt WebEngine / WebChannel host |
| `star/agent.py`, `star/desktop_core.py` | Agent loop, routing and task limits |
| `star/memory.py`, `star/knowledge.py`, `star/analytics.py` | Local conversations, knowledge and measured metrics |
| `star/studio.py`, `star/policy.py` | Official Studio adapter and executable permission checks |
| `star/roblox_cloud.py`, `star/roblox_pipeline.py` | Owner-approved private test-place Cloud actions |
| `evals/`, `star/eval_gate.py` | Held-out regressions and evaluation runner |
| `server/` | Optional owner-operated server and knowledge service |
| `tests/`, `frontend/src/*.test.tsx` | Offline backend and frontend tests |
| `.github/workflows/` | CI, Windows release packaging, Pages |

More detail: [Repository guide](docs/REPOSITORY_GUIDE.md), [Architecture](docs/ARCHITECTURE.md), [v0.9 acceptance](docs/STAR_V090_RELEASE_ACCEPTANCE.md).

## Review, licensing and release gates

Make small, testable PRs; no force-pushes, hidden merges or unreviewed autonomous tool changes. Do not commit model weights, access keys, user chats, projects or reference media. The repository is **publicly viewable**, but **no licence file has been published yet**; do not assume permission to redistribute or commercially reuse the source.

Before declaring v0.9 released, complete actual Windows 11 GPU/model checks, data-preserving upgrade, Studio/Cloud permissions and optional integration testing, verify public Setup/ZIP/checksum downloads, and confirm the live Pages domain. The [Windows acceptance plan](docs/STAR_WINDOWS_ACCEPTANCE.md), [v0.9 release acceptance](docs/STAR_V090_RELEASE_ACCEPTANCE.md) and [website handoff](docs/WEBSITE_RELEASE_CHECKLIST.md) are the authoritative review checklists.
