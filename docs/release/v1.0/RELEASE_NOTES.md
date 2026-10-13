# STAR Intelligence v1.0.0: release notes

Previous release: v0.9.0 (October 11, 2026). Source: `star/next` merged into `main` through pull request #152.
These notes say what changed, what is switched off until you turn it on, what was measured, and what nobody has
tested yet. If something is not listed as tested here, assume it was not.

## Before you upgrade

- Back up `%APPDATA%\STAR` (your chats, settings, lessons and downloaded models) before installing. Setup keeps this
  folder, and the v0.8.0 -> v0.9.0 upgrade preserved it on the one PC where it was tested, but keep a copy anyway.
- If your current copy was installed **for all users**, Windows asks for administrator approval on every upgrade. STAR
  now says so before Setup starts (issue 121). A per-user install (the default) needs no administrator rights.
- The installer is not code-signed, so Windows may show a publisher warning. Compare the file with `SHA256SUMS.txt`.

## What is new since v0.9.0

Chat and app
- Redesigned chat: rename or delete a chat with Undo, quieter layout, answers keep streaming when you leave the page
  and come back, and a retry can no longer land in another chat.
- **Look at my screen** in the composer's "+" menu: STAR asks first, every time, then takes one screenshot that is
  added to your message as an attachment you can remove before sending. STAR never captures on its own.
- **Create image** and picture requests typed in ordinary chat (on by default, with an off switch in Settings).
- The Star mascot can be shown in the app ("Show Star"; off until you turn it on), with reduced-motion support.
- Read-only Brain overview; lesson hygiene report (proposals only); Studio error explanations as references.
- Two STAR clients on one server no longer share a model slot by default (issue 118); background helper calls carry
  no slot number.
- Updater: a ZIP update refuses symbolic links and existing files; Setup's administrator prompt is explained first.

Roblox and code quality (each one is opt-in unless stated)
- Offline checks: Full API dump name checker, StyLua parsing/formatting, official Luau analyzer second opinion,
  busy-loop / touch-reward / connection-lifetime checks, server/client trust checks (SEC-).
- Standalone compilers and planners (command line or library; nothing in chat calls them by default): remote compiler
  with Luau specs, UI compiler (JSON to Luau), VFX compiler, player-data schema compiler, template build planner,
  incremental Rojo project builder, Roblox XML model/place attachments (read-only).
- Skill packs: six game-design packs, DataStore / remotes / TweenService packs, a game-math pack, Godot 4 packs
  (all opt-in).
- Live Roblox documentation tools (create.roblox.com only, cached) and design/map-plan tools (offline, read-only).
- Checked worked examples retrieved before answering; continuation of cut-off code answers; instant answers on this
  PC; specialists for research and coding; Asset Forge (Poly Haven metadata).

Learning (what "self-learning" means in this release)
- Night school runs on STAR Server while the brain is idle: STAR practises Roblox tasks, checks its own answers with
  the same scorer as the evaluation, and proposes lessons. A paired statistical gate (W1) decides whether a lesson is
  kept; it never promotes on an inconclusive result.
- The app can import lessons learned on the server, but only as **candidates you review**; nothing is accepted
  automatically. The bundled lesson file in this release is empty.
- STAR does not retrain its model. Lessons are text you can read, change and remove.

Other
- Discord bot for the owner only (a separate program, not in the installer): DM chat, /ask /image /screen /status
  /digest. Screenshots over Discord are off by default and need a button press each time.
- Blender tools (two switches, both off), research watch of official pages (automatic check off), Brain 2 practice
  runner and MCP smoke probe (command line), shared-brain store (dormant unless an operator prepares it), workbench
  connector (server side), failure ledger for stored evaluation results (command line).
- Release provenance: the published Setup and ZIP are attested by GitHub (`attest-release`) and verified before the
  release is created.

## Off by default (you turn these on)

Settings switches, all off in a new profile: Asset Forge, Blender tools and Blender editing, Tailscale / CGNAT
addresses, instant answers, importing bundled practice lessons, worked examples, research auto-check, Studio Luau
execution, live Roblox docs. Environment opt-ins: `STAR_COMPLETE_CODE_ANSWERS=on` (continue cut-off code answers),
`STAR_LUAU_ANALYZE`, `STAR_ROBLOX_DOCS_LIVE=1`. Discord bot: separate program; screen capture there needs
`STAR_DISCORD_SCREEN_CAPTURE=1`. Picture requests in chat (`media_chat_auto`) and the specialists switch are **on** by
default, as in v0.9.0's design; the mascot is off until "Show Star".

Not in this release (held for later): run-and-repair Luau before answering (#181), architecture intelligence (#68),
training-data generator (#148), evaluation-driven code generation fixes (#147).

## Measured results (STAR Server, model star-fast, mode auto, skill packs off, knowledge on, temperature 0)

EVALUATION_RESULTS_PENDING

## Not tested on real hardware or against real services

EVIDENCE_PENDING
