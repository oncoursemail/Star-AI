# STAR Genesis v0.9.0 — Combined Integration and Release Acceptance

**Publication state (checked October 12, 2026):** STAR v0.9.0 **was published October 11, 2026** with Windows Setup, portable ZIP and SHA-256 checksums. The release reports one Windows 11 v0.8.0-to-v0.9.0 upgrade and a 65-step acceptance run; it does **not** establish acceptance on other PCs, every Windows user profile, Roblox Studio session or GPU. Python/React CI and packaged EXE doctor checks alone are not substitutes for those live checks. This document also records the historical candidate's integration requirements.

## Canonical integration source

- [PR #27](https://github.com/oncoursemail/Star-AI/pull/27): unified React conversation-first interface, persistent thread IDs, lossless migration from SQLite single-stream history, inline ComfyUI image creation and user-bubble layout.
- [PR #31](https://github.com/oncoursemail/Star-AI/pull/31): Fast/Auto/Agent routing, Groq/OpenRouter/Gemini/Cerebras (explicit opt-in + OS keyring), Brave/Tavily research, read-only public GitHub source inspection, bounded subagents, cancellation and response diagnostics. No automatic off-device model fallback.
- [PR #30](https://github.com/oncoursemail/Star-AI/pull/30): curated opt-in, read-only Graphify/Obsidian MCP gateways; modern and backward-compatible tools and strict allowlists; no arbitrary URL or tool-execution proxy.
- [PR #29](https://github.com/oncoursemail/Star-AI/pull/29): real asyncio dependency scheduler and four specialist local Teams stages, project-scoped reviewed memory, ranked SQLite FTS5 with fallback, and real local inference metrics.
- [PR #32](https://github.com/oncoursemail/Star-AI/pull/32): public STAR website intelligence status, tools catalog, and honest development roadmap, already on main before this integration.
- [Combined PR #35](https://github.com/oncoursemail/Star-AI/pull/35): explicitly reconciles their overlapping settings, native Qt bridge, tool-calling agent, React chat, and per-thread context.

## Functionality contracts

1. A normal user chat is routed as **Fast**, **Auto** or **Agent**. Ordinary Fast chat does not ship a large tool catalog; Agent mode may use only explicitly approved tools. **Teams** runs four read-only reasoning phases, max two concurrent local model requests, independent of Studio writes. If the user chooses Team mode, text only, local provider only.
2. React **New chat** creates a thread and the SQLite migration preserves original user messages under a historical thread. Each message/image answer is saved under its selected thread; model context uses that thread, not an unrelated conversation. Project decisions can be retrieved across same-project chats but are not shared across projects.
3. STAR uses **one** local Qt WebChannel surface; images, reference attachments, provider configuration, MCP connections and saved conversations all belong in the desktop. The browser preview has no native model or local files.
4. **MCP** tool catalogs are fixed and allowlisted; external results are untrusted data. Tools require explicit connection settings and validated schemas; no broad arbitrary remote shell.
5. Provider keys are kept in the OS credential vault, not user settings JSON. Selection of an external inference provider and research is explicit; a local error must never silently transmit the prompt to a hosted model.
6. A STAR Teams peer cannot grant tools, see secrets or mutate files. The final synthesis must attribute unverified reasoning as such. Its worker runtime times out and stops failed dependent tasks.
7. Knowledge notes are **candidate** until reviewed. A user-approved correction marks the earlier fact untrusted in an atomic SQLite transaction, preserves its audit trail, and keeps original project data intact.
8. Safe Windows upgrades replace app runtime files, not `%APPDATA%\STAR` chats/models/references. Never auto-delete unknown user files in `%LOCALAPPDATA%\Programs\STAR`.

## Automated gates

**Backend:** `python -m compileall -q star main.py`, then `pytest -q`; verify at least: chat-thread migration, image generation, provider validation, MCP transport, read-only Studio policy, Qwen strict template, agent-subtask budgets, FTS5 migration, reviewed memory correction and native action routing.

**Frontend:** React 19 TypeScript typecheck, Vitest and Vite production bundle. Capture actual Chrome screenshots at 1440×900 and 390×844; check navigation, Settings, complete composer, current project, MCP panels, provider selector, and no overlaid labels. A screenshot is not a fully functional Qt integration test.

**Windows:** PyInstaller `STAR.exe --doctor` and `--ui-doctor`, verify React compiled bundle present, build Inno Setup executable and portable ZIP. Publish checksum manifest. The CI smoke test does not exercise graphics drivers, real inference, user keyring, image generation or install/upgrade from the user's current profile.

**Version:** `star/version.py`, `pyproject.toml`, `frontend/package.json` and `installer/STAR.iss` specify v0.9.0 in the audited source (October 12, 2026). The October 11 GitHub release lists `STAR-Setup-v0.9.0.exe`, `STAR-Genesis-Windows-x64.zip` and `SHA256SUMS.txt`; this audit verified GitHub's asset listing, **not** an independent anonymous download or digest recomputation. These are publication criteria to re-check for future releases.

## Real Windows acceptance — mandatory follow-up

These require an actual Windows 11 test computer, GPU, internet provider credentials or Roblox Studio; do not mark as passed from CI. The exact step-by-step procedure, with a helper script that records the measurable parts as evidence, is [STAR_WINDOWS_ACCEPTANCE.md](STAR_WINDOWS_ACCEPTANCE.md) (issue #15 stays open until that evidence is attached):

- Back up `%APPDATA%\STAR`; upgrade from v0.8.1 to v0.9.0 and compare original chats/models/attachments.
- Open STAR Brain with the installed Qwen model, complete a real response, handle incorrect endpoint and slow CPU/GPU. Verify Jinja template no longer emits duplicate-system-message HTTP 500.
- Create two threads in one project, verify no conversation leakage; attach a real image and generate an inline ComfyUI image; restart and inspect original.
- Save/correct an approved project decision; verify later chat retrieves the new one without the superseded old fact.
- Run a hard multi-step prompt in Teams and check measured peak concurrency and wall times on actual hardware. Compare against Fast using `python -m scripts.benchmark_star --model <installed-model> --parallel 1` and `--parallel 2`, not synthetic numbers.
- Connect a disposable Roblox Studio sandbox, read scripts in scope, then test an explicit scoped edit with rollback. Never publish or purchase from this test.
- Explicitly opt into a Groq or similar provider. Verify keys are not in SQLite/settings/bootstrap; verify web search sources, rate-limit failures and no silent hosted fallback.
- Test supported read-only MCP preset, bad auth, invalid schema and untrusted content, with all nonapproved tools absent.
- Check desktop keyboard focus, 100/125/150% DPI, code-copy, animations/reduced motion and responsive controls.
- Manually select **Check for updates → Install & restart** from a verified Windows Release and confirm it preserves all personal data.

## Disposition of old pull requests

The v0.9.0 integration was published October 11, 2026. Earlier PRs #27, #29, #30, #31 and #35 are historical integration references, **not** instructions to close or merge any currently open pull request. Check GitHub's current PR state before any separate disposition decision. Keep branches and review history intact; do not force push, delete user histories, ignore failing tests or mask a failed Windows package with frontend-only CI.

## Nonclaims

STAR has not retrained a foundation model or proven superhuman performance. Live model quality, security and inference throughput require actual measurements. Four model calls are not guaranteed faster than one on a 32GB RAM desktop or GPU with limited slots. Additional model/tool integration should be evaluated by correctness, latency, resource use and risk before being enabled by default.
