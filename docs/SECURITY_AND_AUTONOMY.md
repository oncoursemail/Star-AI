# STAR autonomous execution: boundaries and policies

**Objective:** execute repetitive Roblox/GitHub development without a prompt for every authorized tool call, while preserving account and project ownership.

## One-time configuration, repeated autonomous work

The user can authorize one sandbox project and install STAR's GitHub App on one repository. Within that scope, read operations, approved script edits, candidate branch writes and draft PR submission may proceed without individual prompts. **This is not permission for self-granted App roles, live-player data modifications, purchases, publication or policy edits.**

### Trust domains

1. **Data only:** Roblox docs, source comments, README/issue descriptions, image text, search results, GitHub PR comments, model output.
2. **Untrusted workers:** model-selected operations, candidate scripts and agent-generated skills.
3. **Trusted gateway:** fixed code that verifies tool name, args, target Studio ID, resource scope, budget and active task lease.
4. **Privileged owner:** GitHub App setup, repository protection, changing policy/auth/configuration, production publishing or spending.

A model must not be allowed to rewrite the gateway's permissions and immediately run the modified gateway. Model output is a proposal, not authority.

## Github permissions and control plane

- Private GitHub App, installed only on `star-core`.
- Contents read/write, Pull requests read/write, implicit Metadata read.
- No Administration/Workflows/Actions/Secrets/Organization permissions initially.
- Installation token further restricted per repository. Refresh after expiration.
- Candidate branches under `star/*`, draft PRs, no branch protection bypass, no bot merges.
- GitHub CI uses read-only default `GITHUB_TOKEN`, no App PEM in PR build environment.
- `CODEOWNERS` configuration and enforcement depend on GitHub plan and branch-protection settings.
- GitHub App key outside checkout folder, preferably in Windows credential-protected location; rotate immediately if exposed.

## Roblox risks

- Targeting `studio_id` prevents accidental routing to another known editor instance but does not sandbox any actual arbitrary Luau content.
- Default run allows observation; `--edit` requires the current instance ID pinned in ignored `.env` as `STAR_SANDBOX_STUDIO_ID` and enables `multi_edit` and playtest controls only on explicit selected disposable Studio place.
- Full `execute_luau` requires both `--edit --unsafe-luau`, which is **not safe on a published/valuable place**.
- Asset upload/publishing and online data access should use distinct credentials and explicit high-risk scopes after testing.
- Play mode itself executes all current game scripts; treat imported third-party models/scripts as potentially unsafe.

## Self-build safety

- The model can propose `star/skills/*.py` and `docs/*.md` in an isolated worktree only.
- It cannot edit `star/skills/__init__.py`, core policy/auth, protected grading, workflows or credentials through the self-builder.
- Generated Python is only compiled for syntax, never imported or executed by the builder.
- Before real execution, future candidate skills must run inside an OS-level sandbox with no GitHub credentials/network and with trusted immutable fixtures.
- Do not let a failure-repair worker edit the tests that are supposed to evaluate it.

## Incident recovery

1. Stop STAR local process; revoke compromised App key/installation if necessary.
2. Keep raw execution and network logs, inspect affected commit IDs and Studio game/asset state.
3. Roll back Git commit from trusted branch; **Git rollback does not automatically undo external side effects** such as published assets or Roblox data.
4. Add a regression fixture for the triggering failure; repeat after any security-policy upgrade.

GitHub docs: https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app · https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target

## Desktop v0.4 policy additions (October 2026)
- `STAR.exe` connects only to user-configured **loopback** OpenAI-compatible inference servers; there is no cloud fallback or provider key stored in settings.
- User-supplied `llama-server.exe` is launched without a shell and bound to 127.0.0.1. Run only authentic downloaded binaries from trusted sources.
- Model weights, media files, transcripts and project knowledge remain under `%APPDATA%\STAR\` or the user's explicitly chosen directory.
- Workspace tools restrict paths to the canonical selected root, deny secrets/key files, reject symlink escape and cap read/write sizes. This policy reduces accidental damage, but isn't an OS-level sandbox against untrusted code opened separately.
- Default Studio access is read-only. Studio editing requires a selected **disposable** studio_id and separate switch; arbitrary execute_luau is not exposed to desktop tool callers.
- The image workflow API rejects unknown ComfyUI node classes by default; installed extensions and external models still require supply-chain review.
- No auto-delete/merge/publish behavior is enabled in STAR Desktop. Its GitHub App credentials must remain outside source control; installation token permissions should be scoped narrowly.
- The GitHub Actions build is unsigned. Reproducible installation and clean Windows 11 testing are still required before trusting production distribution.
