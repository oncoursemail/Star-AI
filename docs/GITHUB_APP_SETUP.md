# STAR GitHub App — two separate responsibilities

**Private development repository:** `oncoursemail/Star-AI` — STAR can propose source changes on its own `star/...` branches and open Draft PRs, after you register its GitHub App and install it on that repository. The app has **Contents read/write** and **Pull requests read/write**; no Administration, Secrets, Workflows or repository deletion privileges.

**Public distribution repository:** `oncoursemail/Star-Intelligence-Downloads` — STAR's Windows CI publisher may upload **only compiled installer assets, checksums and website allowlist** after passing tests. Do not install the source-writing GitHub App on this public repository; it intentionally refuses to write there. The cross-repo publisher uses a separately scoped Actions secret (prefer eventually a short-lived GitHub App publisher token), never the AI model's own credentials.

## Register the source-development GitHub App

1. GitHub account → Settings → Developer settings → GitHub Apps → New GitHub App. Pick an available distinctive name such as `star-intelligence-build-bot`.
2. Webhook Active: off (this prototype polls). Where it can be installed: **Only on this account**.
3. Repository permissions: **Contents: Read and write**, **Pull requests: Read and write**, **Metadata: Read** (automatic). Do NOT enable administration, actions, secrets, workflows, or organization permissions.
4. Save the App ID, generate a private key to a folder **outside this repository**, and install the App on **Only selected repositories: `Star-AI`**.
5. The installation URL includes the installation ID. Store IDs and the path to the key in ignored local `.env`:

```dotenv
STAR_GITHUB_APP_ID=YOUR_NUMERIC_APP_ID
STAR_GITHUB_INSTALLATION_ID=YOUR_NUMERIC_INSTALL_ID
STAR_GITHUB_PRIVATE_KEY_FILE=C:\Users\YOU\Documents\star-keys\STAR.pem
STAR_GITHUB_REPO=oncoursemail/Star-AI
```

Never paste your key, token, or `.env` here. No GitHub sign-in is required for ordinary users to download STAR **after** the binary-only public release repository is set up.

See [Public/private distribution setup](STAR_PUBLIC_PRIVATE_GITHUB.md) and [GitHub App authentication docs](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).
