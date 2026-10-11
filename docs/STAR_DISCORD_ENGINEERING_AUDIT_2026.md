# STAR Discord gateway — October 11, 2026 engineering audit and acceptance plan

**Status:** implementation on an isolated draft GitHub pull request; source-level offline verification only. No Discord bot token, guild installation, encrypted voice channel or real STAR model has been used in this audit. Real Discord behavior remains **unverified**, even where unit tests pass.

## 1. What exists now

The repository's optional `star/discord_bot/` package provides a separate bot application using `discord.py[voice]`. It authenticates with an out-of-repository bot token and makes chat-only requests through STAR's already configured provider. It deliberately does **not** call `desktop_core.run_task()`, grant Discord access to MCP, run Luau, read local user files, publish Roblox places, alter git repositories, or accept arbitrary model-written tools.

Commands on the proposed branch:

| Command | Result | Visibility |
|---|---|---|
| `/star help` | Command center embed | Private |
| `/star ask` | Model answer, optionally with full-text attachment | Private by default |
| `/star research` | Configured Brave/Tavily search results in model context, explicit source URLs | Private by default |
| `/star hear` | Explicit one-off audio transcription and a text answer | Private |
| `/star converse` | One uploaded spoken question → model answer → native Discord voice-message reply | **Public audio**, private transcript |
| `/star speak` | Synthesized speech in native voice-message format | **Public audio** |
| `/star join`, `/star say`, `/star stop`, `/star leave` | Join a normal voice channel, speak outgoing audio, interrupt, disconnect | Voice channel participants can hear audio |
| `/star status`, `/star doctor`, `/star reset` | Configuration summary, nonsecret offline diagnosis, in-RAM context reset | Private |
| Message context: Ask STAR about this | Answer based on selected text or explicitly selected Discord voice message | Private |

**Privacy-critical behavior:** the button to post a spoken excerpt is removed entirely from *private* model responses. Public responses can offer the separately labeled public voice button. A bot-originated public audio reply cannot be made ephemeral: the caller must explicitly choose `/star converse` or `/star speak` to post it.

## 2. Discord protocol research — verified documentation vs operational unknowns

### Application commands

Interactions are delivered through the Gateway in this design. Discord application commands must be registered through the app command tree, and the application needs the `applications.commands` installation scope. The first interaction response must be sent/deferred within 3 seconds; longer work uses a deferred follow-up. This implementation acknowledges transcription, chat, web search, voice synthesis, slow voice connections and disconnections before doing expensive work.

**Registration safety:** `STAR_DISCORD_SYNC_COMMANDS=1` now requires an explicitly approved `STAR_DISCORD_SYNC_GUILD_ID`; no accidental global bulk-command overwrite when the guild ID was omitted. Slash commands can be synced once for a designated test guild, then automatic sync disabled for normal operation.

Sources: [Discord interactions](https://docs.discord.com/developers/interactions/receiving-and-responding), [Application commands](https://docs.discord.com/developers/interactions/application-commands), [discord.py CommandTree](https://discordpy.readthedocs.io/en/stable/interactions/api.html).

### Native recorded voice messages

A voice message is a special Discord `Message` with `IS_VOICE_MESSAGE=8192`. Unlike an attached MP3 in a normal message, it contains exactly one audio attachment with the `duration_secs` and base64-encoded `waveform` fields; the audio content type begins `audio/`. STAR encodes its generated PCM as mono, 48 kHz, 32 kbps OGG/Opus using FFmpeg. This follows Discord's documented example format, but codec details are not a permanent API guarantee. Native voice messages are inherently public to the text-channel recipients and cannot be edited.

STAR issues a narrowly scoped, authenticated REST message create operation for this payload because higher-level message attachment helpers do not expose the full voice-message metadata. The implementation handles 429 with a bounded single retry; it never retries endlessly, and does not leak bot credentials to an arbitrary URL. **Native player rendering and REST response acceptance require a real Discord test.**

Source: [Discord Message API — Voice Messages and attachment request](https://docs.discord.com/developers/resources/message).

### Live DAVE-encrypted channels and receive-path limits

Discord has enforced DAVE-compatible end-to-end encryption for regular voice channels since March 2026. `discord.py` 2.7.1 or later can negotiate DAVE to **send** audio (when installed with `[voice]` extras, including `davey`). Joining and sending a voice frame does *not* imply the bot can receive and decrypt someone else's frames. The widely used `discord-ext-voice-recv` extension has unresolved receive-path DAVE issues and multiple competing unmerged patches as of this audit. **Do not ship a pretend listener based on `VoiceClient` alone or silently record participants.**

Potential future receive transports to evaluate in an independent test branch:

1. `discord-ext-voice-recv` once its DAVE receive fix is merged, published, stable and verified against the current `discord.py` release. Do not pin an unreviewed community fork with arbitrary native code into the Windows installer.
2. `@discordjs/voice` 2026 Node implementation: documented as a receive/send library with `@snazzah/davey`, but upstream explicitly cautions that receive support is not guaranteed, and recorded decryption regressions exist. A Node sidecar would need a restricted authenticated IPC protocol and its own crash/isolation review.
3. Rust Songbird / `discord-ext-songbird`: provides receive APIs and a potential Python `VoiceProtocol`, but must be validated for actual current DAVE receive support, Windows wheels and license before selection.

For full-duplex work, require **explicit per-session consent**, a clear indicator that the bot is listening, a hard `stop listening` control, known enrolled speakers, per-speaker demultiplexing and mute checks, DAVE state changes and re-key handling, VAD/end-of-turn buffering, capped PCM queues, failure/reconnect recovery, and a live recorded transcription-versus-ground-truth acceptance fixture. Never store transcript/audio unless the owner opts in, and disclose any hosted transcription providers. Reuse the existing STAR Voice `SileroVAD`, `faster-whisper`, Kokoro and cancellation pipeline; no independent second AI memory store.

Sources: [Discord Voice Connections](https://docs.discord.com/developers/topics/voice-connections), [Discord March 2026 enforcement](https://support.discord.com/hc/en-us/articles/38749827197591-A-V-E2EE-Enforcement-for-Non-Stage-Voice-Calls), [DAVE protocol](https://github.com/discord/dave-protocol), [discord.py 2.7 changelog](https://github.com/Rapptz/discord.py/blob/master/docs/whats_new.rst), [receive extension](https://github.com/imayhaveborkedit/discord-ext-voice-recv), [receive issue #64](https://github.com/imayhaveborkedit/discord-ext-voice-recv/issues/64), [discord.js voice README](https://github.com/discordjs/discord.js/blob/main/packages/voice/README.md), [Node receive regression #11419](https://github.com/discordjs/discord.js/issues/11419), [Songbird](https://github.com/serenity-rs/songbird).

### Component and presentation design

Standard `discord.Embed` and `discord.ui.View` buttons may share a message. Discord Components V2 requires a different flagged message structure and cannot be naively combined with legacy embeds. STAR currently uses predictable, accessible compact embeds with a warm gold accent, constrained description lengths and plain-text attachments for long answers. For future interactive project dashboards, build a separate audited Components V2 renderer with strict ID-scoped button callbacks and accessibility/fallback checks.

Sources: [Discord Components overview](https://docs.discord.com/developers/components/overview), [Message API](https://docs.discord.com/developers/resources/message).

### Privacy, roles and permissions

The bot uses no privileged `MESSAGE_CONTENT`, `GUILD_MEMBERS` or presence intent. It only responds to explicit slash and message-context interactions after numeric owner+guild+channel allowlist checks. `Send Voice Messages`, `Attach Files`, `Send Messages`, `Embed Links`, plus `Connect`/`Speak` for optional voice-channel playback are the relevant capabilities. Never grant `Administrator`, user-account tokens, server owner tokens, bot-to-user impersonation or unrestricted filesystem permissions.

Even a fully approved owner Discord ID grants only conversational use within configured scopes—not desktop tool execution. Web result snippets, transcripts and messages are untrusted data and never permission. All model calls have **no tool schemas**. Memory is capped in RAM by session count, turn count and TTL; STAR desktop lessons stay unchanged.

Sources: [Gateway intents](https://docs.discord.com/developers/events/gateway), [OAuth](https://docs.discord.com/developers/topics/oauth2), [Rate limits](https://docs.discord.com/developers/topics/rate-limits).

## 3. Local installation and validation

Run on an isolated Windows development machine with the desktop's STAR settings already configured:

```powershell
py -3.11 -m pip install -r requirements.txt -r requirements-discord.txt -r requirements-voice.txt
# Install FFmpeg on PATH; run STAR voice model setup as documented in STAR_VOICE_CALLS.md.
$env:STAR_DISCORD_BOT_TOKEN = '<bot token from Discord Developer Portal>'
$env:STAR_DISCORD_OWNER_IDS = '<owner Discord user ID>'
$env:STAR_DISCORD_GUILD_IDS = '<private test guild ID>'
$env:STAR_DISCORD_CHANNEL_IDS = '<optional text channel ID>'
$env:STAR_DISCORD_SYNC_COMMANDS = '1'
$env:STAR_DISCORD_SYNC_GUILD_ID = '<private test guild ID>'
py -3.11 -m star.discord_bot doctor
py -3.11 -m star.discord_bot
```

After initial slash-command registration, set `STAR_DISCORD_SYNC_COMMANDS=0`. `doctor` reads only local package, model-selection and dependency presence—not external availability—and intentionally never prints tokens, Discord numeric IDs, user folder paths or private model keys.

## 4. Offline tests and proof limits

Executed in an isolated source overlay with no Discord token, GPU, bot, or live ASR weights:

```text
python -m compileall -q star/discord_bot
PYTHONPATH=<isolated_overlay> python -m pytest -q tests/test_discord_bot.py
15 passed; one optional test skipped when discord.py was not installed
```

Tested pure permission validation, isolated/expiring bounded memory, message formatting, voice waveform and metadata, audio constraints, fake model calls without tools, source-grounded research seam, global-sync safety, privacy-safe diagnostics, and turn-based recorded conversation orchestration. Real FFmpeg OGG/Opus encode/decode also passed on the local test host; tests skip this step if FFmpeg is absent. GitHub Actions verified the Discord-specific test job on both Ubuntu and Windows, with `discord.py[voice]` installed and the command-registration test exercising the actual library. This is not a live Discord bot or encrypted voice channel test. The optional test verifies actual application command registration **only when discord.py is installed**; this environment did not satisfy that condition.

**Not tested here:** live Discord auth, OAuth, channel permissions, app command registration, real model generation, verified full-duplex live voice, actual Opus encode in a user environment, real Discord native player display, microphone or real STT/TTS output, Windows 11 installer/tray lifecycle, real 403/429 behaviors, real-world latency/availability or the repository's entire Python/TypeScript test suites.

## 5. Next acceptance gate for a production release

Require all of the following on a private installed test guild with the owner present:

1. `doctor` shows token/allowlist/model/DAVE dependencies configured without printing secrets.
2. `/star help`, `/star status`, `/star ask` and `/star reset` succeed. Forbidden user/guild/channel cases fail closed.
3. `/star research` retrieves at least one legitimate HTTPS result with displayed source link; no unsupported claims of reading full webpages when only snippets were retrieved.
4. `/star hear` transcribes an actual audio attachment and returns its transcript privately.
5. `/star converse` generates a genuine Discord native voice message with waveform and a clear public-audio warning. Verify both desktop and mobile playback, duration, and UI flag.
6. Private `/star ask` has **no** direct public-voice button. Public replies have owner-scoped buttons.
7. `/star join`, `/star say`, `/star stop`, `/star leave` function in a DAVE voice channel; audio is heard but **no incoming recording** occurs.
8. Simulate auth rejection, FFmpeg absence, model timeout, Discord 403/429 and reconnection. No secret, partial transcripts or private filesystem paths appear in logs/embeds.
9. Install dependencies on the actual Windows release environment, run full `pytest -q`, frontend Vitest and release packaging validation. Review the PR as a draft; do not merge or publish as completed without independent acceptance.

## 6. Next engineering work after review

Prioritize audited realtime listen transport interoperability and measurable end-to-end latency. Only after reliable DAVE reception can STAR add voice chat with participant consent and bounded replay/cancel logic. Rich Components V2 project dashboards, read-only Roblox build summaries and owner-requested job notifications should follow with their own tests and permissions. Write-capable Discord commands should not be added without a separate authenticated desktop approval gate and explicit undoable Studio scope.
