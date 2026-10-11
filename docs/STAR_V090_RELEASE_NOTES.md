# STAR Intelligence v0.9.0 — Draft release notes

**Status:** Release candidate in [PR #40](https://github.com/oncoursemail/Star-AI/pull/40), not a published Windows update.

## What is new

**Chat and interface.** Separate saved conversations, redesigned React chat, Fast/Auto/Agent modes, Retry for failed turns, and a reduced-motion policy. Long attachments can be read and searched without silently cutting off their beginning. [Acceptance](STAR_V090_RELEASE_ACCEPTANCE.md#L14-L23); [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

**STAR Server brain on your network.** Connect a private OpenAI-compatible LAN server, test the connection, and select its available models for different tasks. Keys use the operating system's credential store; the on-PC model remains an option. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

**Roblox knowledge.** Search Roblox documentation and look up API symbols with sources attached to answers. A static Luau check catches some code problems; it does not run your game. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40); [Evaluations](evals.md#L199-L214).

**Studio and Open Cloud.** Connect your own private test experience using a scoped Open Cloud key or Studio's MCP connector. Reads are available; publication and Luau testing require approval, and Studio changes are guarded by place/session checks. [Roblox access](ROBLOX_ACCESS.md#L1-L83).

**Skills and evaluation gate.** Eighteen topic packs ship; five are enabled by default (the six game-type packs are opt-in until the gate has measured them). Automated Roblox suites and a gate help compare changes, not certify game quality. [Evaluations](evals.md#L113-L123).

**Learning.** Project-specific corrections and preferences can be reviewed, recalled and exported. Inferred lessons need approval; the model is not retrained. [Learning](STAR_LEARNING.md#L1-L6).

**Voice.** A file-tested call backend supports spoken replies, interruption and voice styles. There is no finished in-app call screen. [Voice](STAR_VOICE_CALLS.md#L1-L15).

**Images.** Local ComfyUI image creation, edits and masks; attached-picture understanding; sampled video frames/transcripts; and pinned visual references. Setup depends on hardware and models. [Media](STAR_MEDIA.md#L1-L24).

**Documents.** Readers for text, PDF, Office files, CSV/TSV and JSON retain source locations for later retrieval. No OCR or spreadsheet recalculation. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

## Upgrading from v0.8

Back up `%APPDATA%\STAR` first. The upgrade is designed to preserve chats, models and references; an upgrade from an existing Windows profile still needs verification. Configure your server or local brain, Roblox credentials/test place, and optional voice and image dependencies separately. [Acceptance](STAR_V090_RELEASE_ACCEPTANCE.md#L23-L48).

## What is verified and how

PR #40 reports 2,058 Python tests passing (15 skipped), 172 frontend tests passing, compilation/build checks, offline Studio safety probes and a read-only live Studio check. These are branch-reported results, not proof of a completed release installation. [PR #40](https://github.com/oncoursemail/Star-AI/pull/40).

## What is NOT verified yet or needs your setup

A v0.8-to-v0.9 Windows upgrade on your profile, GPU/provider performance, live microphone/speaker calls, and your own Roblox/ComfyUI configuration require separate checks. The website is not deployed. [Acceptance](STAR_V090_RELEASE_ACCEPTANCE.md#L35-L48); [Voice](STAR_VOICE_CALLS.md#L343-L359).

## Known limits

Without packs: **18/34 = 52.9%** on Roblox v2; **11/23 = 47.8%** on creation-v1; combined **29/57 = 50.9%**. Individually tested default packs gave 19/34 and 15/23, **not** a measured combined-packs run. Sixteen Studio-dependent v2 tasks were not run; scores are noisy and do not measure visuals or gameplay. [Evaluations](evals.md#L123-L146); [limits](evals.md#L180-L214).
