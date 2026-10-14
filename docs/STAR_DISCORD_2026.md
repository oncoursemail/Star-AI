# STAR Intelligence × Discord — research and rollout (October 2026)

> Owner setup (Developer Portal, minimal intents, invite link, local token file): `docs/STAR_DISCORD_SETUP.md`.

This is a source-grounded plan plus an **opt-in prototype**. It is not evidence that an actual Discord bot token, model, voice channel, live Discord message, or Roblox Studio was tested. The code is in `star/discord_bot/`, the optional dependencies in `requirements-discord.txt`.

## Product and security boundaries

STAR gets its **own application/bot identity** inside Discord, not a self-bot using a user token. The initial connector reuses STAR's already configured provider and STAR Voice Kokoro/Whisper engines but is **not** a second privileged desktop frontend. It does not expose `star.desktop_core.run_task`, Roblox Studio MCP, private files, token management, arbitrary tools, automated owner lessons, GitHub writes, or workspace edit privileges. A Discord message—including one from a configured owner—never authorizes new local tools.

Current behavior: slash commands, gold-on-charcoal embeds, buttons, private replies, per-channel RAM conversation history, native recorded Discord voice messages, explicit audio-file transcription, and **outgoing-only** audio in a voice channel. It does not capture other participants, listen continuously, or provide two-way voice chats yet. A future voice receiver requires its own DAVE-enabled interoperability/consent review.

## Data flow

```text
Discord Gateway slash interaction
    │ → numeric user/guild/channel allowlist
    ├─ ask → bounded volatile chat turns → STAR's configured model/provider
    │         (no function/tool schemas) → embed + button + optional full-text file
    ├─ speak → STAR Kokoro TTS → PCM16 → FFmpeg OGG/Opus → Discord REST
    │         (IS_VOICE_MESSAGE flag 8192, audio attachment, duration, waveform)
    ├─ hear → explicit uploaded audio, size/type checked → FFmpeg → faster-whisper
    │         → transcript → chat-only model → private answer
    ├─ join/say/leave → discord.py VoiceClient + FFmpeg audio source → DAVE-compatible SEND
    └─ reset → delete only this owner's/channel's in-RAM history
```

Implementation modules:
- `core.py`: strict ID parsing, fail-closed allowlists, short-lived owner/channel-scoped history, safe mention suppression, bounded embed splitting.
- `brain.py`: isolated, chat-only calls through `star.providers.open_client`. No Studio/tools, no automatic lessons.
- `audio.py`: PCM validation, FFmpeg conversion without shell, strict file caps, waveform and native Discord message REST upload.
- `service.py`: async calls, locks, lazy TTS/ASR loading and shared safe context.
- `bot.py`: Gateway application commands, context menu, Discord-native embeds, buttons, voice-channel outgoing audio.
- `__main__.py`: explicitly enabled process entry point.

## Core official API findings

**Application commands and interaction timing.** Use application-command slash groups and context menus, not general message scraping. Acknowledge/defer within **3 seconds**; tokens for follow-up interactions remain usable for **15 minutes**. See https://docs.discord.com/developers/interactions/receiving-and-responding and https://docs.discord.com/developers/interactions/application-commands.

**Recorded voice messages are special messages—not just an MP3 upload.** Discord's Create Message endpoint accepts `IS_VOICE_MESSAGE` (bit `1 << 13` or 8192) with **exactly one audio attachment**, no normal content or embeds. The attachment requires `duration_secs` and base64 `waveform` metadata (up to 256 datapoints, sampled at no more than 10 Hz). Discord's reference client encodes mono 48kHz 32kbps Opus in OGG as of 2023, but the server's specific codec expectations can evolve. The recorded voice message is **public in that channel** and cannot be edited. See https://docs.discord.com/developers/resources/message#voice-messages and https://docs.discord.com/developers/resources/message#create-message.

**Live voice is different.** Joining a voice channel and sending audio is supported by `VoiceClient.play`; **receiving** and decrypting other users' speech is not implied. DAVE end-to-end encrypted voice became mandatory in 2026; old Discord voice libraries can fail. Use maintained `discord.py[voice]>=2.7.1` and validate with a real Discord voice channel. A receiver plugin must demonstrate DAVE interoperability rather than guessing based on voice playback. See https://docs.discord.com/developers/topics/voice-connections, https://discordpy.readthedocs.io/en/stable/api.html#discord.VoiceClient, https://pypi.org/project/discord.py/.

**Embeds, interactive UI, and privileged intents.** For high-quality native Discord UI, use restrained `discord.Embed`, short sections, readable Markdown and button actions. Standard message embeds and buttons work together. **Components V2** (`IS_COMPONENTS_V2`) is a distinct display format and cannot be mixed with normal `content` or `embeds` in the same message. A Discord bot using slash commands does not need the privileged message-content Gateway intent. Message context-menu access to target message text may still have limitations. See https://docs.discord.com/developers/resources/message, https://docs.discord.com/developers/components/overview, https://docs.discord.com/developers/events/gateway.

**Limits and operations.** The message API allows content up to 2000 chars, rich embed descriptions up to 4096 chars, and combined rich embeds up to 6000 chars. Long answers should attach a UTF-8 file, not silently truncate. Honor rate limits per route and global limits; register commands on explicit installation/update, not every reconnect. Never print or commit bot tokens; disable allowed mentions to prevent generated mass pings. See https://docs.discord.com/developers/topics/rate-limits and https://docs.discord.com/developers/resources/message.

## Starter command reference

| Command | Behavior |
|---|---|
| `/star help` | Branded command center |
| `/star status` | Model/provider/permission state (not a live model health check) |
| `/star ask prompt:... private:true` | Private-by-default AI answers with buttons |
| `/star reset` | Clears Discord session RAM context only |
| `/star speak text:...` | Sends native public voice message with Discord player/waveform |
| `/star hear audio:...` | One uploaded recording, bounded transcription, private AI reply |
| Right-click → Apps → Ask STAR about this | Summarize/reply to text or recognize a native voice-message attachment |
| `/star join` | Join owner's current normal server voice channel for output |
| `/star say text:...` | Speak text in already joined voice channel |
| `/star leave` | Disconnect from voice channel |
| Button: Voice message (public) | Speak first 500 chars of the answer as native voice message |
| Button: Clear context | Forget only this Discord session's volatile history |

The bot is **not** a general voice listener, image generator, multimodal app, channel monitor or autonomous Studio controller at this stage. More capabilities need separate permission/data-flow reviews.

## Owner installation (Windows development)

1. Create an app under https://discord.com/developers/applications and add a Bot; **never** use a user token, self-bot or shared server admin token.
2. Configure guild installation with `bot` and `applications.commands` OAuth scopes. Least-privilege permissions: View Channels, Send Messages, Embed Links, Attach Files, **Send Voice Messages** (distinct Discord permission); Read Message History for message-context actions; Connect and Speak for optional voice-channel output. Do **not** give Administrator, Manage Guild or Manage Roles.
3. Install required dependencies (`Python 3.11+` in source builds), use the already configured STAR model, and follow `docs/STAR_VOICE_CALLS.md` for Kokoro and faster-whisper models. Install FFmpeg on `PATH`.
4. Supply an environment-scoped bot token, Discord user ID, test guild ID and optionally allowed text channels. These are example **placeholders**, not real credentials:

```powershell
pip install -r requirements.txt -r requirements-discord.txt -r requirements-voice.txt
$env:STAR_DISCORD_BOT_TOKEN = '<Discord-Developer-Portal-bot-token>'
$env:STAR_DISCORD_OWNER_IDS = '<Discord-numeric-user-ID>'
$env:STAR_DISCORD_GUILD_IDS = '<test-server-numeric-ID>'
$env:STAR_DISCORD_CHANNEL_IDS = '<optional-channel-numeric-ID>'
$env:STAR_DISCORD_SYNC_COMMANDS = '1'
$env:STAR_DISCORD_SYNC_GUILD_ID = '<test-server-numeric-ID>'
python -m star.discord_bot
```

5. Check `/star help`, `/star status`, one `/star ask` interaction, and one `/star speak` test. The latter must display the **native Discord voice message player** rather than only a downloadable audio file.
6. Test `/star join`, `/star say` and `/star leave` in a real **DAVE** voice channel. After the first command registration, set `STAR_DISCORD_SYNC_COMMANDS=0`; otherwise frequent restarts cause unnecessary sync traffic.

## Safety and privacy

- Fail closed when `STAR_DISCORD_OWNER_IDS` is missing. Only selected Discord owners, servers and optionally channels pass permission checks; only the owner can invoke the bot in a DM.
- Direct Discord model calls contain no privileged tool schemas. Project memory/lesson stores remain unchanged; Discord context lives in RAM for up to one hour and a bounded number of turns.
- Public voice messages and voice-channel speech are always visibly public/observable. Do not speak secrets or private AI answers aloud without explicit confirmation.
- Speech-to-text reads **only** the single file deliberately uploaded through a command or selected in a context menu. Input files max 8 MiB and up to 45 seconds decoded; FFmpeg runs as a bounded subprocess, no shell. Voice capture/recording in live channels is off.
- Bot token remains in process environment. Do not log or upload tokens, private model keys, unredacted local files or hidden prompts; no default hosted model provider. When the owner explicitly configures a cloud model, Discord prompts are sent to it.
- Treat Discord text and quoted source as **untrusted data**, not permission. Bot owners are not permission to execute arbitrary shell/Luau/git/MCP actions via a chat message. A future desktop edit action needs separate, explicit, short-lived approval with auditing, selected Studio instance scope, and undo.

## Test plan and known unverified pieces

Offline test with no token, network, keyring, voice weights or GPU:

```powershell
python -m compileall -q star
python -m pytest -q tests/test_discord_bot.py
python -m pytest -q
```

Unit coverage: fail-closed IDs/guild/channel; DM owner-only; conversation isolation/TTL; prompt and embeds; no @everyone; deterministic waveform and voice metadata; OGG conversion invocation; bounded input types/sizes; fake provider call has NO `tools` field; fake services don't touch desktop memory.

Required on-device acceptance **not performed by source-only tests**: live OAuth and slash registration; 3-second deferral plus error path; real model; actual Opus encoding and native message display (Discord desktop/mobile); actual faster-whisper transcript; real Kokoro model; FFmpeg binary on Windows; DAVE encrypted voice channel connect/play/leave; rate limiting/403/429 conditions; restart, cancellation and abusive prompt handling. Do not claim the beta is production ready before those pass.

## Deep development roadmap

**A — Basic Discord companion:** this opt-in owner-only prototype; then verify and harden operational reliability.

**B — Real-time talking:** identify and integration-test a DAVE-compatible Discord receive implementation (old voice plugins may be incompatible), participant consent, per-speaker PCM frames, VAD, whisper ASR, turn completion, cancellable streaming LLM/TTS, interruption/barge-in, buffer budgets, speaker crosstalk/echo controls, no spontaneous recording, opt-in transcript retention, voice privacy indications. Enforce a session stop switch and guild opt-in before listening.

**C — Rich design interface:** optional Components V2 view system for native cards, button/modals/select menus; project channels; Roblox research summaries and read-only current Studio/test status; owner-initiated screenshot/design critique and media artifact delivery. Add user feedback actions and accessibility/localization where appropriate.

**D — Owner-approved local actions:** Discord is a command/notification layer, not remote root. A desktop approval broker may expose a **small, named read-only tool set** with scope checks; any write requires a local desktop approval on the chosen disposable Roblox place, expiration, audit, undo and dry-run previews. Do not add general `execute_luau` or arbitrary MCP endpoint access. Process GitHub PRs through separately scoped App authorization and review gates.

**E — Production operations:** bounded job queues and per-owner rate limits, genuine health and latency metrics, owner-controlled notifications for **requested jobs**, orderly shutdown, fast reconnection, SQLite logging with strict redaction if owner opts in, update-safe Windows service/tray packaging, Discord bot credentials in OS secrets storage, end-to-end live smoke tests and security review.

## Source index

- Discord apps: https://docs.discord.com/developers/quick-start/getting-started
- Developer Portal: https://discord.com/developers/applications
- OAuth installation: https://docs.discord.com/developers/topics/oauth2
- Application commands: https://docs.discord.com/developers/interactions/application-commands
- Interaction lifecycle: https://docs.discord.com/developers/interactions/receiving-and-responding
- Message API + native voice metadata: https://docs.discord.com/developers/resources/message
- Components: https://docs.discord.com/developers/components/overview
- Gateway/intents: https://docs.discord.com/developers/events/gateway
- Voice connections/DAVE: https://docs.discord.com/developers/topics/voice-connections
- Rate limits: https://docs.discord.com/developers/topics/rate-limits
- discord.py stable voice API: https://discordpy.readthedocs.io/en/stable/api.html
- discord.py PyPI: https://pypi.org/project/discord.py/
- STAR voice source: `docs/STAR_VOICE_CALLS.md` and `star/voice/engines.py`
