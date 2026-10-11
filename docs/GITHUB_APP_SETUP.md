# STAR GitHub App — scoped development on the public source repository

**Canonical public repository:** [`oncoursemail/Star-AI`](https://github.com/oncoursemail/Star-AI). STAR's optional development GitHub App may create source branches and draft pull requests **only within configured repository permissions**. The app does not have Administration, Secrets, Workflows, repository deletion, or release publishing privileges.

**Official Windows distribution:** [STAR Releases](https://github.com/oncoursemail/Star-AI/releases) in that same public repository. The trusted `.github/workflows/windows-desktop.yml` pipeline builds and validates binaries and publishes new tags with its job-scoped `GITHUB_TOKEN`. The abandoned separate public-downloads mirror and `STAR_PUBLIC_RELEASE_TOKEN` are not needed. No GitHub sign-in is required to download public releases.

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
STAR_GITHUB_BASE_BRANCH=star/YOUR-WORK-BRANCH
```

`STAR_GITHUB_BASE_BRANCH` is the existing `star/<name>` work branch that STAR cuts its own branches from and opens its draft pull requests against. It is required for publishing. `main` (the default branch, which publishes a release when something is merged into it) is refused, and so is any name that is not `star/<name>`. STAR's App can upload only `star/skills/*.py` (not the package `__init__.py`) and `docs/skills/*.md`; tests, evaluation files, build and dependency files, workflows and all other code are refused.

Never paste your key, token, or `.env` here. Public downloads are available at [STAR Releases](https://github.com/oncoursemail/Star-AI/releases/latest).

See the [repository map](REPOSITORY_GUIDE.md) and [GitHub App authentication docs](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).
