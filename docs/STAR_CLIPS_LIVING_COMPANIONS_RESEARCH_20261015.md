# STAR Clips + Living AI Companions — source-grounded design and phased implementation

Status: **research + opt-in OBS replay pilot + pure companion state contract**. Not a Medal clone, not a native recorder, not a released Windows feature. Written 2026-10-15. Owner goal: "STAR, CLIP THAT SHIT!" and original animated multi-AI characters, including playful cat/dog transformations.

## Executive design decision

1. Implement *recording as a separate local service*, not through React/Qt canvas screenshots, Roblox process injection, or an always-on AI model.
2. First usable milestone: use the OBS Studio 28+ WebSocket v5 replay-buffer API, with OBS already running, owner-configured scene/replay/audio settings, explicit Connect/Start/Save/Stop desktop clicks. This pull request provides that pilot.
3. Long-term: optional first-party recorder (Windows Graphics Capture + WASAPI loopback + GPU hardware encoder), bounded compressed-segment rolling buffer, local clip library, event detectors, optional local phrase detection, clip editor, export/share with one-time permissions.
4. Companions are **visual projections of actual routed agent/tool/voice events**, not fake AI runs. Reuse the existing owner-approved Star identity; do not introduce placeholder fan-art copies.
5. Keep the recording service and companion animation service independent so gameplay FPS and model response latency are not compromised.

## Research: Medal's capability surface

The one-to-one requirements comparison must explicitly separate ordinary instant replay from game-specific event detection.

| Capability | Medal reference | STAR planned |
| --- | --- | --- |
| User-selectable rolling clip length | Several hotkey lengths and custom | User range + bounded memory; OBS pilot uses OBS's configured duration |
| One key instant replay | Hotkeys | Global hotkey when explicitly enabled (not implemented in pilot) |
| Voice clipping | "Medal, clip that!" | Local push-to-talk or local wake phrase, e.g. "STAR, clip that shit"; off by default |
| Automatic clips | Game-specific supported-event list | Per-game adapters with published evidence; never claim all games auto-detected |
| Full-session recording | On/off and bookmarks | Future service, with crash-safe segments and disk quotas |
| Library/editor | Clip thumbnails, trim/share/management | SQLite clip index, native timeline, waveform, trims, labels, favorite/search |
| Sharing | Cloud/community | Offline-first export; separate authenticated opt-in Discord/YouTube/TikTok connectors |
| Game detection | Many games | Signed process metadata + user-selection, no unsafe injection |

Official product and developer references:
- https://support.medal.tv/support/solutions/articles/48001271487-getting-to-know-medal-s-settings
- https://support.medal.tv/support/solutions/articles/48001167701-what-is-automatic-event-detection-auto-clipping-
- https://medal.tv/developer/auto-clipping
- https://support.medal.tv/support/solutions/articles/48000971430/

**Open-source comparative study:**
- https://github.com/lulzsun/RePlays — libobs-powered recorder/library/editor; a strong functionality reference. Audit its actual dependency licenses before borrowing code.
- https://github.com/thrtn70/WatchDog — native Windows tray, OBS-based replay, event adapters and Discord sharing; its claimed game-specific auto clips are not proof of compatibility on our test PC.
- https://github.com/FisiFla/better-outplayed — Rust/Windows Graphics Capture/WASAPI and compressed-segment replay design; pre-alpha, do not assume Windows reliability.
- https://github.com/abdelaziz-mahdy/rewind — libobs/Flutter alternative; documented Windows hardware validation gaps.
- https://github.com/splitshotz/Vice — Linux recording architecture for future expansion.
- OBS control: https://obsproject.com/kb/remote-control-guide
- Protocol: https://github.com/obsproject/obs-websocket
- Python binding: https://pypi.org/project/obsws-python/
- Windows capture: https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture
- Hardware encoding: https://obsproject.com/kb/hardware-encoding

### Pilot implemented in this PR

- `star/clips_obs.py`: safe allowlisted `clipConnect`, `clipStatus`, `clipStartBuffer`, `clipSaveReplay`, `clipStopBuffer`, `clipDisconnect`. OBS password exists only in process memory; fixed **127.0.0.1:4455**, no remote selected host, no STAR upload path. Third-party errors sanitized. A successful SaveReplayBuffer RPC is reported only as a **request**, never proof of a written video file.
- `star/react_shell.py`: Qt action dispatch on a worker (not model tool registry).
- `frontend/src/ClipPanel.tsx`: explicit actions on Tools page; label is "STAR Clips." No auto-connect, no automatic mic capture, no auto-record. The owner must configure OBS game scene, output, replay buffer, and audio.
- `tests/test_clips_obs.py`: fake OBS contract checks; these do **not** verify native GPU capture.
- Desktop adds `obsws-python` dependency only; **OBS Studio is not redistributed**.
- On disconnect or exiting STAR, any already-running OBS replay stays under OBS user's own control.

**Pilot limitations:** OBS required; no global hotkey; no voice clipping; no automatic detection; clip file not imported into STAR yet; no clip editor; no original recording encoder; no hardware benchmark. This is deliberate honest scoping.

### First-party native recorder design (next milestone)

Dedicated capture process, not Python/React render loop:
1. Windows Graphics Capture (window/monitor picker where applicable); WASAPI loopback + explicitly authorized microphone channels.
2. Hardware encode to H.264 (NVENC/AMF/QSV as available), provide CPU fallback only when performance allows. NVENC is a dedicated encoding unit, but color conversion, rendering and frame transfer can still affect FPS.
3. Ring buffer of *encoded* timestamped GOP/segments, bounded both by time and bytes. Keyframe-aware trim and two-phase atomic file finalize. Avoid raw frames in RAM. Crash recovery and disk free-space thresholds.
4. The UI sends a bounded save intent; service snapshots buffer plus configurable 0–5s post-roll; queue immediately, never delay input/game render for analysis.
5. Local clip database: capture version, event source, game identity (or Unknown), timestamps, elapsed duration, source audio flags, hash, local path, privacy flags. Clip files live outside source repository.
6. Dedicated low-priority process for transcoding/transcription/thumbnail/clip ranking *after* gameplay; do not run a vision model every game frame.
7. FPS/latency tests: paired game capture on/off at the same gameplay workload, 1% low/p95 frametimes, CPU, GPU encoder, VRAM, memory ceiling, disk, dropped frames, and clock drift. Performance thresholds are goals to measure, not proven results.

**Anti-cheat and privacy:** do not inject DLLs or read protected process memory. No default streaming or microphone access; capture indicators and exclusion lists; do not share chats, desktop notifications, DMs, or overlays accidentally. The game and OBS determine captured sources. No session-wide audio logging for wake-phrase research without explicit consent.

### Game events and Roblox strategy

Three evidence tiers:
- **Verified event:** owner-controlled game's documented API/plugin, exposed match replay data, opt-in Roblox experience remote/Studio test, or officially permitted event stream.
- **Inferred event:** low-rate HUD/video/audio classifier (optional, local) with displayed confidence and false-positive controls. Never assert that classifier inference is a verified kill or win.
- **Manual:** owner hotkey/phrase guaranteed when recorder and buffer are actually healthy, even for unrecognized games.

Roblox's client-side CaptureService records short in-experience captures up to 30 seconds; its official docs note muted voices. STAR's **desktop** recording is separate and can cover user-chosen OBS sound sources; it must not assume access to all Roblox games' event metrics.

Roblox docs: https://create.roblox.com/docs/reference/engine/classes/CaptureService ; https://en.help.roblox.com/hc/en-us/articles/203314190-How-do-I-take-a-video-in-an-experience

Automatic highlights must expose per-title adapter version, events actually detected on hardware, calibration datasets, precision/recall, missed-event rate, and owner Disable/undo. No fake '100% support.'

### Voice clipping plan

Input: owner-activated push-to-talk or opt-in local keyword spotting, distinctive configurable alias (e.g. "STAR, clip that shit!" / "STAR, clip that!"), cooldown and false-positive veto. Use local speech or keyword engines subject to independent benchmarks (sherpa-onnx, Vosk, openWakeWord); never silently send mic audio to providers. Clip commands must originate from an approved physical or voice capture session, **not** untrusted game text, voice chat, model-generated answers or web content. Overlay/playback can acknowledge success only after the recorder confirms the clip's path exists.

### Editing and publication plan

- Fast trim/crop/speed/captions and a vertical-format preview, no loss of source.
- FFmpeg for export with verified codec build license and filter availability.
- Word alignment via local speech models if voice access is enabled, with human-editable subtitles.
- Clip uniqueness/dedup based on hash and near-duplicate fingerprints; private-by-default library and retention quotas.
- Optional Discord sharing only with explicit target/channel selection and confirmation. Other publishing APIs need their own service authorization and terms review. Never silently upload gameplay/audio.

## NuclearPlayer research

Correct link: https://nuclearplayer.com/ — an open-source **music player, not a Medal replacement**, with plugin and MCP support. Implement a separate `star_music` optional MCP tool for search/play/queue with clear source/licensing requirements. Playback/streaming music could be copyrighted in recorded clips, so opt-in audio track separation and warnings are needed. AGPL-3.0 source license means do not copy Nuclear code into STAR without a distribution compliance review.

## Living multi-AI companion system

### Reference interpretation and identity

Owner's two TikTok screenshots depict an orange-haired, bespectacled "Opus 5.5" fan character and a galaxy-purple-haired, cat-eared "ASTRA 6" fan character joking/affectionate. They are style references, **not official Anthropic/OpenAI art or benchmark evidence**. Do not redistribute the screenshots or copy the characters verbatim. Commission/create a new original character pack with written rights. Model/provider/mascot branding should be descriptive and non-endorsing unless rights are secured.

Retain STAR's approved identity exactly (indigo-black bob, gold-fading low twin tails, gold star hair clip, amber eyes, black/gold dress, mitten hands; owner-approved sprite packs in `frontend/public/assets/mascot`). No auto-generated variant may silently replace STAR's approved base identity.

Suggested character packs for model families: warm copper scholarly, ivory/teal futuristic, navy/violet celestial, blue/silver technical, plum/gold whimsical. These are **visualization skins**. Users must be able to rename/recolor/reassign them independently from provider identity.

### Open-source renderer/animation findings

- **Existing STAR:** `frontend/src/StarPet.tsx` / `StarFace.tsx` already support accurate single-mascot activity, blink, breath, wave, sleep, drag and accessibility. Extend rather than replace.
- **Rive React:** https://github.com/rive-app/rive-react MIT-licensed runtime with reactive state machines. Strong React fit. The commercial editor/export plan is distinct from the open runtime; audit current pricing before distributing editable .riv content. https://www.rive.app/pricing
- **Inochi2D:** https://github.com/Inochi2D/inochi2d BSD-2 open character format/rigging alternative. It cannot read Live2D model files without rerigging. https://github.com/Inochi2D/inochi2d-docs
- **Live2D Cubism:** visually viable, but expandable AI/chat avatar applications may need a special publication license. https://www.live2d.com/en/sdk/license/expandable/
- **Shimeji desktop mascots:** study collision/walk/crawl idle behaviors as design inspirations; assess licensing before code reuse.

### Character rig/art contract

Each original model pack includes:
- Editable layered source, license attribution, thumbnail/alt text, transparent output, named pivot hierarchy; left/right hands with consistent anatomy, ears/tails as physically attached rig parts in animal forms.
- Full-body and face states (idle, think, read, type, speak, fail, celebrate, walk, run, jump, wave, puzzled, blush, sleep, cat, dog).
- Rigged mouth visemes with timestamped speech mapping; no fabricated lip sync during silent tools.
- Transitions authored by an animator (anticipation → action → settle), hair and ribbon follow-through, ground contact and no foot sliding.
- Per-character consistent proportion and palette; silhouette recognition at 64–128px. Fixable animation source, not flattened stills.
- Color-blind/low-motion accessibility; no compulsory movement near input caret/Send button.

### Agent-to-character evidence contract

`CompanionEvent {actorId, runId, sequence, at, phase}` emitted from the actual STAR orchestration/tool/voice runtime. Never infer success from model text. `phase` values: idle, thinking, tool, speaking, finished, failed. Monotonically increasing sequence number per actor prevents out-of-order UI celebration.

This PR adds *pure* `frontend/src/companionDirector.ts` + test: real state transitions, opt-in animal form, deterministic idle scene proposal, no idle play while tools work or reduced-motion is on, no kisses except when both affection and romance toggles are active. **This director is not wired to the UI; no extra characters are rendered in this PR.**

Future event bridge: STAR provider router/specialists → typed event collector → Qt bridge event stream → motion director → animation rig renderers. Do not manufacture parallel model runs simply to animate a chat. Rate limit events and render no more characters than a hardware-selected budget.

### Play interactions / choreography

- Naturally idle: walk/sit/read/listen, Star can point to an answer or hold a miniature letter.
- Group actions: greeting, wave, high-five, synchronized victory, play tag, hide-and-seek, little arguments resolved playfully.
- Optional affection: hug, cheek peck/kiss, blush, playful cuddling — all wholesome, user-toggle controlled. Characters are fictional UI art; actions must never imply model consent, consciousness or interpersonal relationships.
- Cat mode: tracked ears and tail, sleepy curl, paw waves, crouch/startled motions. Dog mode: puppy ears/tail, bounce and happy wag. Do not merely paste floating ears above a PNG.
- Autonomous play must pause on any live task, active text composition, low battery/performance mode or reduced-motion setting; cap simultaneous motion and avoid input occlusion.
- Companions never send messages on a person's behalf, start calls, read unrelated chats or perform hidden uploads.

### Visual acceptance / performance gates

1. Owner approves a *design sheet* with at least 6 original provider personas and fixed Star; assets have license chain and consistent hands, palette, costume, facial anatomy.
2. Art and rig review at 64px/128px/256px; pose samples in static and moving clips, not just generated contact sheets.
3. Multi-agent unit tests map exactly to emitted run events; no event when an agent isn't actually connected/running; stress repeated reconnect/abort, stale event, simultaneous tasks, and agent role swaps.
4. Native Qt test: 4–6 animated characters + model streaming + active game, measured frame times and memory; compare disabled/low/normal. Workload benchmarks on both brains. Native GPU/capture tests mandatory before performance claims.
5. A11y test: reduced motion override, keyboard and focus behavior, screen reader hidden decorative movements, no uncontrolled sound/voice, drag handle remains accessible.
6. Rendered UI acceptance screenshots/video at small and large windows. Preserve STAR's OLED-black/gold identity; do not obscure chat, force neon, or ship generic cut-and-paste UI elements.
7. UI is a distinct **Companions** setting/group, default off. Separate controls for behavior, audio, forms, affection, and animation density. Never bundle these opt-ins into clip recording consent.

## Architectural sequence and dependencies

| Stage | Result | Proof gate |
| --- | --- | --- |
| A — this PR | Opt-in OBS clip controls, local-only no upload, pure companion event/director tests, this spec | Unit/UI CI + OBS smoke test pending |
| B — native acceptance | OBS recording test on Windows 11; verify real replay file duration/audio, startup/shutdown, no fallback and no crash | Owner-observed MP4/MKV + logs; playable file |
| C — useful Clips | hotkey, local library, file verifier, thumbnail/trim and overflow safeguards | Several games, disk pressure, crash recovery |
| D — creator workflows | local voice phrase, event adapters, AI highlights, editor, captions and permissioned share | Precision/recall, no unapproved upload |
| E — original character pack | approved cast + editable 2D rigs, asset licenses | Owner image/video review and paired visual tests |
| F — real multi-agent scene | backend events into rigs, choreography, cat/dog and optional affection, voice lip sync | Truthful statuses, animation QA and game FPS |

Review sign-off for GPL-licensed libobs/RePlays code, AGPL Nuclear code, Live2D SDK and commercial Rive assets must precede incorporation. Calling OBS as an independent process over its local WebSocket API is a cleaner architectural boundary than copying libobs into STAR; it does not eliminate the need to honor distributed-component licenses.

## Go/no-go acceptance for this branch

- [x] Research map and explicit limitations
- [x] Qt-allowlisted opt-in OBS replay bridge on localhost
- [x] Manual replay control UI under STAR Tools
- [x] Fake OBS action tests and pure companion contract tests authored
- [ ] CI green (must be checked from PR checks)
- [ ] OBS real installation connected on native Windows
- [ ] Actual video saved with verified path and playable A/V
- [ ] Voice "Clip that!" trigger
- [ ] Game event plugins and self-hosted clip library
- [ ] Original characters approved/rigged/animated
- [ ] Companion director connected to real agent events
- [ ] Windows installer distributed/released

Never describe unchecked items as shipped. Do not auto-merge this PR.
