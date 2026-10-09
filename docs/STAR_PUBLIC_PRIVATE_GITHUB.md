# STAR's dual GitHub architecture — private development, public distribution

## Why two repositories?

**Private:** `oncoursemail/Star-AI` — source code, CI definitions, internal reports and GitHub App development branches. Keep Private.

**Public:** `oncoursemail/Star-Intelligence-Downloads` — compiled Windows Setup, portable ZIP, SHA256SUMS, release notes and website. Never push your private repository's source history.

A desktop user can fetch anonymous public release assets, verify the advertised SHA-256 and launch the normal STAR installer. No GitHub login or GitHub CLI is needed to update once public publication is configured.

## One-time steps (repository owner)

1. Open https://github.com/new and create **Star-Intelligence-Downloads**, **Public**, **with a README**. Do not change the existing private `Star-AI` visibility.
2. Create an **expiring fine-grained personal access token**, owner `oncoursemail`, **Only selected repository: Star-Intelligence-Downloads**, permission **Contents: Read and write**. Do not grant access to the private source repository. Prefer a GitHub App token for permanent publishing later. Do not put token in code, chat, or the public repository.
3. In the **private Star-AI** repository → Settings → Secrets and variables → Actions → **Secrets**, add `STAR_PUBLIC_RELEASE_TOKEN` with the token. Under **Variables**, add `STAR_PUBLIC_REPO=oncoursemail/Star-Intelligence-Downloads`.
4. In private STAR Actions, select **STAR Desktop — Build, Test & Release** → **Run workflow**. The optional `publish-public` job follows the successful private build and source-only release, and uses the secret to publish only approved compiled assets and website files.
5. Public repository Settings → Pages → deploy from `main` branch `/ (root)`. Then public site is https://oncoursemail.github.io/Star-Intelligence-Downloads/ . Public downloads are accessible to everyone.
6. Remove the token from the secret or revoke it any time to stop automated publication. Rotate before expiry.

The token is for the **trusted GitHub Actions publisher** only. STAR's local model/agents do not receive it. Writing new source code to private branches is separate from publishing reviewed, compiled public Releases.

## Separation rules enforced by workflow

- Private build runs unit tests, Windows PyInstaller packaging and `STAR.exe --doctor` before uploading binary artifacts.
- Only `STAR-Setup-vX.Y.Z.exe`, `STAR-Genesis-Windows-x64.zip`, and `SHA256SUMS.txt` enter the public release.
- Website publisher copies only seven allowlisted static website files; it refuses symlinked/oversized files and unknown destination repositories.
- Never publish `.env`, `keys`, SQLite databases, model weights, unreviewed code or project data.
- The public release job does not run for PRs and cannot alter private-source branches.
- Absent variable/secret means publication is skipped. No public repository currently means the app uses its browser-based private Release fallback.

## STAR's own GitHub App

Separate permissions for software development (Contents write, PR write on private Star-AI) from distribution (Contents write only on public download repo). For an App-based cross-repository publisher, generate a scoped installation token only inside trusted CI, never feed it to STAR's language model or external tool outputs.

## Reference documentation

- https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
- https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication
- https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- https://cli.github.com/manual/gh_release_create
