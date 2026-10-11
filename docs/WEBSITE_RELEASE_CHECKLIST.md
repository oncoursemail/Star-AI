# STAR website and release handoff

**Snapshot: October 11, 2026.** This documents a development candidate and does not approve merging, deploying, publishing, or claiming a Windows installer exists. Always re-check the [latest GitHub Release](https://github.com/oncoursemail/Star-AI/releases/latest) and PR/CI state before publishing.

## Source-ready work

The React site reads the latest stable release from GitHub when available, uses an explicitly dated snapshot/official release-page fallback, and does not turn unreleased source versions into download links. The website and README distinguish opt-in LAN and hosted models, read-only Studio inspection versus separately approved private Open Cloud actions, optional media and voice dependencies, and candidate-only features.

The reported v0.9 automated baseline is **18 / 34** Roblox, **11 / 23** creation and **29 / 57** across the two baseline sets. Sixteen further Roblox v2 cases require Studio/manual evaluation. These are not visual quality or real-world game completion scores.

The website's Star mascot frames have fallbacks, but the approved hero/faces/poses art under `frontend/public/assets/mascot/` is **not present** in this source snapshot. Placeholder graphics do not constitute reviewed final character art.

## Remaining verification gates

1. **Review / integration:** review conflicts, security findings, tests and overlapping draft pull requests (including [integration PR #40](https://github.com/oncoursemail/Star-AI/pull/40)) before any merge. Never force-push or auto-merge unreviewed work.
2. **Website CI:** run `npm run typecheck --prefix frontend`, `npm run test --prefix frontend` and `npm run build --prefix frontend` on the exact candidate. Inspect `frontend/dist/index.html`, functional links, accessibility and keyboard/reduced-motion behavior, and real mobile/desktop captures.
3. **Approved mascot assets:** only when the owner supplies/reviews the actual artwork should it be added under `frontend/public/assets/mascot/`. Check eight distinct expressions, hero and stand/wave poses, transparent borders, performance and mobile crop. Do not claim missing art has shipped.
4. **GitHub Pages:** site deployment occurs from `.github/workflows/website-pages.yml` for eligible `main` pushes. Confirm **Settings → Pages → Build and deployment → Source: GitHub Actions**, the successful deploy job and anonymous access to `https://oncoursemail.github.io/Star-AI/`. A compiled website artifact is not a deployed website.
5. **Windows release:** use [real Windows acceptance](STAR_WINDOWS_ACCEPTANCE.md) and [v0.9 combined acceptance](STAR_V090_RELEASE_ACCEPTANCE.md) to verify a physical user-profile upgrade, Qwen/GPU, Qt/WebChannel, microphone/ComfyUI where enabled, and Studio and Open Cloud permissions. Unit tests and fake Studio adapters are insufficient.
6. **Public package:** only after explicit approval and real acceptance, verify a published, anonymously downloadable Windows Setup, portable ZIP and SHA-256 checksum manifest. Update the dated README release status when it changes. Do not call unreleased source a public installer.

## Developer checks

```powershell
npm install --prefix frontend --no-audit --no-fund
npm run typecheck --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
py -3.11 -m pytest -q
```

Record the commit, job run URL and hardware evidence in the review PR. No green test run by itself establishes a deployed website, a live Roblox integration or a supported Windows upgrade.
