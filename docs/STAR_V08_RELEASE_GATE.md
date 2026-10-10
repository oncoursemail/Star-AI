# STAR Genesis v0.8.0 — release candidate gate

**Release status update:** v0.8.0 was published successfully to the public GitHub Releases channel (verified October 10, 2026): https://github.com/oncoursemail/Star-AI/releases/tag/v0.8.0 . The separate v0.8.1 maintenance candidate includes compatible dependencies and Node 24 GitHub Actions, and must pass another Windows build and release before it is described as shipped. Public release artifacts are distinct from temporary Actions build artifacts.

## Candidate contents

- Strict Qwen / llama.cpp chat template fix: exactly one first `system` role, including after context compaction.
- Actual inference readiness probe, user-friendly error messages, and explicit Jinja-compatible llama-server startup.
- Streaming for plain local conversations (not tool-calling turns); throttled desktop progress, better copyable Markdown code and retry.
- React website v2: non-fabricated interactive workflow illustration, readable typography, genuine UI preview tabs, reduced motion, responsive layout.
- Desktop v2: chat search/copy, status, real activity, model test, refined OLED composer, improved bridge initialization and verified update control from PR #16.
- Project chats and downloaded models stay in `%APPDATA%/STAR` and are outside the replaceable application install directory.

## Review / release steps

1. Inspect [PR #16](https://github.com/oncoursemail/Star-AI/pull/16); make sure Python CI and TypeScript/Vitest/Vite build pass on the final source commit. Confirm the screenshot artifact shows a correctly rendered website and desktop preview.
2. Run the Windows PR build for the candidate: PyInstaller `STAR.exe --doctor` and `--ui-doctor`, Inno Setup ZIP/installer and native GUI screenshot artifact must pass. Do not infer successful local inference from these checks.
3. Review and merge PR #16 when those checks pass. Core policy, workflows and release changes are intentionally not merged by STAR itself.
4. For public website deployment, in the GitHub repository open **Settings → Pages → Source → GitHub Actions**. Previous attempts failed 404 with `Ensure GitHub Pages has been enabled`. Retry the Pages workflow and verify the actual HTTP page.
5. For public Release publication, verify Actions job `publish-release` on the new `main` head. Earlier `gh release create` failed HTTP 403 `Resource not accessible by integration`, although the job token had `contents: write`. If that persists, an admin must review repository Actions/release/tag permissions rather than bypassing protection.
6. Do not advertise v0.8.0 as released until anonymous access verifies the `STAR-Setup-v0.8.0.exe`, portable ZIP and SHA256SUMS files.

## Native acceptance (Windows 11)

- Install the last public Setup in a disposable user account. Send a chat, create a project, store references/models/settings, and back up the test data.
- Install or upgrade to candidate v0.8.0. Confirm the chat data, project notes, model cache and files survive. Confirm old `_internal` runtime files were replaced and `STAR.exe` relaunches after the upgrade.
- On the selected Qwen3.5 GGUF, click **STAR Brain → Test actual AI response** and confirm a *real generated response*. Repeat with a second prompt. The strict system-role exception must not recur.
- Verify partial responses arrive progressively for plain chats. Tool-enabled Studio runs must not be broken by incomplete streamed tool-call JSON.
- Verify a workspace-only chat works offline after the initial model download, with no mandatory hosted key; test no GPU, little RAM, wrong endpoint, corrupted model, and disabled network failure paths.
- Enable a disposable Roblox Studio sandbox with read-only scope; verify discovery, then separately enable permitted edit mode. Confirm mutations, reversibility and human inspection with real Studio screenshots.
- Check the React desktop at 1050×680 and 1440×900 at 100%, 125%, and 150% Windows scaling. Check long Markdown, keyboard navigation, reduced motion, responsive sidebar, and no overlapping labels/icons.

## Operational constraints

- The public browser preview must never expose the Qt bridge, `getGitHubToken`, shell execution, local user files or actual chat data.
- Production tasks remain bounded by Studio/workspace allowlists. No auto-publication of Roblox games, autonomous credentials, paid purchases or broad filesystem cleanup.
- Preserve project/model/chat SQLite files under `%APPDATA%/STAR`. Only explicitly versioned obsolete update packages are candidates for safe pruning.
- STAR is a capable integration prototype, not a newly trained frontier model. Live GPU tests and gameplay quality must be measured independently.

Detailed research and implementation evidence: [STAR v0.8 React and AI research](STAR_V08_REACT_AI_RESEARCH.md).