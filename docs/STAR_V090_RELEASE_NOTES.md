# STAR Intelligence v0.9.0 — Release notes and source evidence

**Publication (verified October 12, 2026):** v0.9.0 was published October 11, 2026 with Windows Setup, portable ZIP and SHA-256 manifest. [Published release](https://github.com/oncoursemail/Star-AI/releases/tag/v0.9.0) is authoritative for the shipped build. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40) and subsequent `star/next` changes describe source history, **not** automatically what was in the released installer.

## What is new

**Chat and interface.** Separate saved conversations, redesigned React chat, Fast/Auto/Agent modes, Retry for failed turns, and a reduced-motion policy. Long attachments can be read and searched without silently cutting off their beginning. [Acceptance](STAR_V090_RELEASE_ACCEPTANCE.md#L14-L23); [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

**STAR Server brain on your network.** Connect a private OpenAI-compatible LAN server, test the connection, and select its available models for different tasks. Keys use the operating system's credential store; the on-PC model remains an option. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

**Roblox knowledge.** Search Roblox documentation and look up API symbols with sources attached to answers. A static Luau check catches some code problems; it does not run your game. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40); [Evaluations](evals.md#L199-L214).

**Studio and Open Cloud.** Connect your own private test experience using a scoped Open Cloud key or Studio's MCP connector. Reads are available; publication and Luau testing require approval, and Studio changes are guarded by place/session checks. [Roblox access](ROBLOX_ACCESS.md#L1-L83).

**Skills and evaluation gate.** The **October 11, 2026 published release notes report** 18 skill packs and five defaults for v0.9.0; that release inventory has not been independently extracted from the installer in this audit. The **October 12, 2026 `star/next` source** has 26 `star/skill_packs/` directories and five entries in `DEFAULT_ENABLED` (`star/skill_packs/__init__.py`); newer source packs must not be represented as shipped in v0.9.0. Six game-type packs are off by default in that source. Automated suites measure specific tasks, not game quality. [Evaluations](evals.md).

**Learning.** Project-specific corrections and preferences can be reviewed, recalled and exported. Inferred lessons need approval; the model is not retrained. [Learning](STAR_LEARNING.md#L1-L6).

**Voice.** A file-tested call backend supports spoken replies, interruption and voice styles. There is no finished in-app call screen. [Voice](STAR_VOICE_CALLS.md#L1-L15).

**Images.** Local ComfyUI image creation, edits and masks; attached-picture understanding; sampled video frames/transcripts; and pinned visual references. Setup depends on hardware and models. [Media](STAR_MEDIA.md#L1-L24).

**Documents.** Readers for text, PDF, Office files, CSV/TSV and JSON retain source locations for later retrieval. No OCR or spreadsheet recalculation. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

## Upgrading from v0.8

Back up `%APPDATA%\STAR` first. The **October 11, 2026 published release notes** report one v0.8.0-to-v0.9.0 Windows 11 upgrade, with a matching installer checksum, byte-identical personal files and preserved chat database contents. This is a reported test on **one PC**, not evidence that every upgrade path (including v0.8.1), Windows profile or device was tested. Configure your server or local brain, Roblox credentials/test place, and optional voice and image dependencies separately. [Acceptance](STAR_V090_RELEASE_ACCEPTANCE.md).

## What is verified and how

The **published v0.9.0 release notes (October 11, 2026)** report **2,723 Python tests and 215 interface tests passing** for the released source, plus a packaged build/smoke test and a **65-step** real Windows app acceptance run. These counts are **reported by the release**, not newly executed or independently measured in this documentation audit. Earlier [PR #40](https://github.com/oncoursemail/Star-AI/pull/40) reports **2,058 Python tests (15 skipped) and 172 frontend tests** for an earlier branch; those are **not** the release's final test totals. Neither set proves every Roblox workflow, GPU or Windows profile works.

## What is NOT verified yet or needs your setup

A v0.8.0 upgrade on **one** Windows 11 machine is reported in the published release; upgrades on your profile, GPU/provider performance, live microphone/speaker calls, and your own Roblox/ComfyUI configuration still need separate checks. **Public GitHub Pages deployment was not independently verified in this audit**: a website build or Pages workflow cannot establish the site's live state. [Acceptance](STAR_V090_RELEASE_ACCEPTANCE.md#real-windows-acceptance--mandatory-follow-up); [Voice](STAR_VOICE_CALLS.md).

## Known limits

**Dated automated scripting results, not game-quality scores:** `python -m star.evals run` with `star-fast`, Auto mode, temperature 0 and packs off, followed by `star.evals rescore`, produced **18/34** Roblox v2 and **11/23** creation-v1 on **October 11, 2026** (**29/57** across those two suites for that run). A separate released-v0.9.0 scripting run on **October 12, 2026** passed **13/34**; another earlier run recorded **16/34** (its exact run date is not established by the October 12 handoff). Thus the documented v2 outcomes range **13–18/34**; the earlier **11/23** creation figure has not been reproduced on the release. Individually tested default packs gave **19/34** and **15/23** on October 11, **not** a measured combined-packs run. Another **16** Studio-dependent v2 tasks require manual/engine evaluation. See [methods and stored runs](evals.md#measured-results-2026-10-11-star-server-star-fast-mode-auto-temperature-0-knowledge-on-one-request-at-a-time) and the [October 12 release handoff](WEBSITE_RELEASE_CHECKLIST.md).
