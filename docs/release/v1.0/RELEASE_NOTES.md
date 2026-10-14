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

Answers and web
- STAR knows the current date and time: every turn gives the model a "Now: ..." line with your local time.
- Questions that need fresh information can search the web automatically when a search provider is configured
  (Brave or Tavily key, or STAR Server's own search gateway); a new tool can read one web page (private network
  addresses are refused). Faster chat on STAR Server: a lighter template for the small model and the fine-tuned
  embedding model loaded on the server.

Other
- Discord bot for the owner only (a separate program, not in the installer): DM chat, /ask /image /screen /status
  /digest. Screenshots over Discord are off by default and need a button press each time.
- Blender tools (two switches, both off), research watch of official pages (automatic check off), Brain 2 practice
  runner and MCP smoke probe (command line), shared-brain store (dormant unless an operator prepares it), workbench
  connector (server side), failure ledger for stored evaluation results (command line).
- Release provenance: the published Setup and ZIP are attested by GitHub (`attest-release`) and verified before the
  release is created.

Security fixes (audit of October 13, 2026: `docs/security/AUDIT-20261013.md`)
- Workspace tools refuse Windows path spellings that could reach protected names (H-1).
- After a turn has read web content, full Luau execution is refused for the rest of that turn (M-1).
- Web fetch: no gateway access through redirects, clear frame markers around fetched text, charset fallback (L-1..L-3).
- Discord audio: FFmpeg reads only from standard input (L-4). More key formats are redacted from logs (L-5).
- `star ask` / `star self-build`: the "local model only" check accepted `http://localhost:1234@example.com` (prompts
  would have gone to example.com); it now requires a real loopback address.

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

In short: **about the same as v0.9.0 on the evaluations, plus the new features.** None of the differences below is
statistically meaningful (paired per-task comparison, one run per task and version: every suite is "inconclusive").

| Suite | v0.9.0 | v1.0.0 | 95% range for v1.0.0 |
|---|---|---|---|
| Golden tasks v2 (34) | 13/34 | 16/34 | 31-63% |
| Creation tasks (23) | 11/23 | 10/23 | 26-63% |
| Blind holdout (24) | 8/24 | 9/24 | 21-57% |

- Measured on the code at commit 72767e1. The release also contains three later changes that were **not** in the
  evaluated code: a "Now: ..." local-time line in the context of every turn, automatic web search for questions that need
  fresh information (news, latest versions, weather, prices) when a search provider is configured, and a web page
  fetch tool with a private-address guard.
- Four tasks hit server timeouts while the server was overloaded by other test traffic; each got one re-run on a quiet
  server and is scored by that re-run (creation ENG-03, holdout HO-UI-02, HO-UI-03, HO-ANI-01).
- Answer times are not comparable with v0.9.0's: v1.0.0's suites ran two at a time on a busy server.

## Not tested on real hardware or against real services

What was checked for this release (owner's Windows 11 PC, October 13, 2026), and what was not:

- Checked on the packaged app from this release's CI build (portable ZIP, disposable profile, real STAR Server):
  start, version 1.0.0 shown, a real answer with sources, the "+" menu, Create image mode, the Look at my screen
  consent dialog (cancelled: nothing captured, nothing attached), Settings, Test server, Check for updates, the
  server key never shown, clean exit. Packaged doctors pass with the exact build commit. Screens: `docs/release/v1.0/`.
- Found and fixed during that check: the Windows package (also v0.9.0's) did not contain the voice catalogue, so
  Settings could not list voices.
- **Not checked by an agent:** installing v1.0.0 **over an installed v0.9.0** with Setup (the test PC has an all-users
  install, so Setup needs the Windows administrator prompt, which only the owner may approve), the refused/cancelled
  upgrade path (W04c, pull request #217, still a draft), and taking a real screenshot with Look at my screen.
- Not run by anyone yet: picture generation with a real picture engine from the installed app, voice with sound,
  Roblox Studio editing from the installed app, the in-app "Install & restart" from v0.9.0 to v1.0.0, Blender tools in a whole chat turn, research watch against real pages, the Brain 2 practice runner,
  the mascot over a long session, other GPUs and Windows profiles. 28 Luau runtime tests of the VFX compiler skip on
  Windows. Night school's lessons have not changed the app's answers in this release (the bundled lesson file is
  empty; importing is opt-in and every lesson waits for review).
