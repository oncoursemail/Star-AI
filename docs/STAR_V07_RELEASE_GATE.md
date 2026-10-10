# STAR Genesis v0.7 — release and acceptance checklist

This is a deployment handoff for the existing public repository. Do **not** treat passing builds, marketing screenshots, or this document as proof that STAR's local model or Roblox tools were tested on a real user's Windows machine.

## Status observed October 9, 2026

- Source: `v0.7.0` (React 19 / TypeScript / Vite with Qt WebChannel).
- Latest public GitHub Release at time of audit: `v0.6.1`.
- Windows CI previously built, packaged, and passed `STAR.exe --doctor` + `STAR.exe --ui-doctor` for v0.7. The publish job failed with HTTP 403 when creating a release.
- React website CI passed TypeScript, tests, Vite build and headless screenshots. Deployment failed HTTP 404 with `Ensure GitHub Pages has been enabled`.
- Feature PR: https://github.com/oncoursemail/Star-AI/pull/16

## Owner/reviewer actions needed to publish

1. Review and merge PR #16 after passing **both** its Python and React CI checks. This updates the verified in-app upgrader and guardrails in the Windows release workflow.
2. In the public repository **Settings → Pages**, enable Pages with **Build and deployment → Source: GitHub Actions**. The Pages deployment action cannot initialize an unconfigured Pages site with a normal `GITHUB_TOKEN`.
3. Verify the repository **Settings → Actions → General** policies permit the release publishing workflow. The previous release job already received `contents: write` but GitHub returned `403 Resource not accessible by integration`; if this repeats with a current-main build, an owner/admin must inspect the repository's automation and release/tag policies. Do not leak tokens or disable protection to force success.
4. Re-run `STAR Desktop — Build, Test & Release` on up-to-date `main`, and verify its publish-release job succeeds. Never overwrite existing tagged binaries silently.
5. Verify the anonymous `https://github.com/oncoursemail/Star-AI/releases/latest` link contains `STAR-Setup-v0.7.0.exe`, `STAR-Genesis-Windows-x64.zip`, and `SHA256SUMS.txt`. Check their digests before announcing v0.7 as released.
6. Verify the site is accessible at `https://oncoursemail.github.io/Star-AI/`. If Actions build succeeds but Pages remains 404, it is not deployed.

## App upgrade contract

- Settings → Stay up to date → Check for updates checks approved public GitHub Releases (no GitHub CLI or account required).
- Install & restart is user-initiated and operates only on a checksum-verified official Setup asset. It displays actual downloaded bytes and runs Inno Setup with `/SILENT /CLOSEAPPLICATIONS /NORESTART`.
- Inno Setup replaces application runtime files under `%LOCALAPPDATA%\Programs\STAR`; persistent conversations, projects, references, downloaded models and settings remain under `%APPDATA%\STAR`.
- No installer should recursively delete `%APPDATA%\STAR` or any user-chosen workspace.

## Live Windows acceptance tests still required

- Launch the real v0.7 Setup on Windows 11. Check 100%, 125%, 150% DPI, 1050×680 and 1440×900 layouts, keyboard focus, Markdown code copy, external links, reduced motion, and attaching references.
- Install STAR Brain on a disposable Windows test profile; verify download SHA-256, model start, actual response, wrong-network/GPU failure states and clean errors.
- Create messages, a separate project, memory/reference files and a downloaded model; upgrade from v0.6.1 to v0.7.0. Confirm that old runtime files are removed, app restarts, and **all personal data remains intact**.
- With real Roblox Studio MCP and an unpublished disposable test place, verify read-only discovery first, then explicitly scoped edit mode and undo/recovery. Do not assume passing unit tests proves gameplay quality.
- Confirm desktop preview and public website cannot access the native Qt bridge or local profile files.

## Scope notes

STAR is an evolving local-first AI development application, not a newly trained frontier foundation model. Larger model abilities, token-level streaming, automated multiagent builds, and production game creation require separate measured work; avoid claiming those are complete without benchmarks and live tests.
