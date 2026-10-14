# STAR website and release handoff

**Verified snapshot: October 12, 2026.** STAR Genesis **v0.9.0** was published October 11, 2026. [Official release](https://github.com/oncoursemail/Star-AI/releases/tag/v0.9.0) includes `STAR-Setup-v0.9.0.exe`, `STAR-Genesis-Windows-x64.zip`, and `SHA256SUMS.txt`. Check [latest GitHub Releases](https://github.com/oncoursemail/Star-AI/releases/latest) before updating these statements. This checklist does not approve merging or site deployment.

## Source and published features

The website uses the published stable GitHub release to label capabilities, and it explains when source features are newer than the published installer. If release data cannot be checked, it links to GitHub rather than assuming availability. LAN and optional hosted model routing belong to published v0.9.0; unmerged features do not.

**Roblox evaluation, not game quality:** an automated scripting run on released v0.9.0 on **October 12, 2026** passed **13 / 34**; earlier runs passed **16 / 34** and **18 / 34**. The observed range is **13–18 / 34**, and single runs vary. An earlier **11 / 23 creation** result is not reproduced on the release, so no current combined score is claimed. Another **16 Roblox v2 tasks** need separate Studio/manual evaluation. This is not a game-quality score. None of these numbers proves live gameplay or visual quality.

**Mascot assets:** approved hero, faces and poses have been added through [PR #136](https://github.com/oncoursemail/Star-AI/pull/136) and [PR #151](https://github.com/oncoursemail/Star-AI/pull/151). Assets existing in the repository do not prove that a deployed site or the October 11 installer contains later changes. Review pending artwork replacements, mobile crops and performance before deployment.

## Remaining verification gates

1. **Review / integration:** inspect conflicts, security findings, and overlapping work; only the lead merges approved draft PRs.
2. **Website CI:** GitHub checks should execute `npm run typecheck --prefix frontend`, `npm run test --prefix frontend` and `npm run build --prefix frontend` on the exact candidate. Independently inspect keyboard behavior, reduced motion, links, and real mobile/desktop captures.
3. **Approved mascot assets:** verify actual built asset paths, eight distinct expressions, hero/stand/wave poses, mobile crop and image weight. Existing assets are not proof of live deployment.
4. **GitHub Pages:** verify Pages source configuration, successful deployment and anonymous access to https://oncoursemail.github.io/Star-AI/. A build artifact is not a deployed website.
5. **Windows release:** the published release reports a physical v0.8.0-to-v0.9.0 upgrade and a 65-step acceptance run on one Windows 11 machine. Continue broader GPU, Qt/WebChannel, permissions, microphone, Studio and updater-cycle acceptance using [Windows acceptance](STAR_WINDOWS_ACCEPTANCE.md) and [v0.9 acceptance](STAR_V090_RELEASE_ACCEPTANCE.md).
6. **Public package:** confirm the official published Windows Setup, portable ZIP and SHA-256 manifest are anonymously downloadable for each new release; never infer published installers from source branches or CI alone.

## Developer checks (instructions, not a claim of a local run)

```powershell
npm install --prefix frontend --no-audit --no-fund
npm run typecheck --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
py -3.11 -m pytest -q
```

Record the exact CI commit and check URLs when run. GitHub CI is not a substitute for physical Roblox Studio and Windows acceptance.
