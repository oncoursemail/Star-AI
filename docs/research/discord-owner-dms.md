# STAR Discord owner DMs, screenshots and reviewable lessons (DRAFT)

This integrates with STAR's existing opt-in Discord bot, not a new bot, self-bot, developer-account scraper or privileged guild listener.

## Capabilities

- Owner-only **normal Discord DMs**: a typed message can receive a local STAR reply without needing to enter a slash command. Existing /star ask and /star research commands remain available.
- Owner-only **one-at-a-time screenshots**: accept PNG, JPEG or WebP attachments up to 6 MiB and 16 million pixels, strip metadata by normalizing to bounded JPEG, then ask the **already configured, explicitly chosen local vision model** to analyze that one image. No screenshot is written to disk; a brief question/answer may remain in temporary session memory.
- Owner-only **lesson candidates**: a message beginning with "remember: ..." or "remember correction: ..." proposes a local preference/correction candidate to STAR's existing desktop LessonStore. The user still reviews it before STAR trusts it across sessions.
- Fail-closed errors: no image-capable local model => no image analysis; no permissions to execute Roblox Studio or modify GitHub from Discord. The bot does not claim a UI was playtested merely because it saw a screenshot.

## Default-off host configuration

Set these only in the trusted host environment, not in a GitHub commit or Discord message:

    STAR_DISCORD_BOT_TOKEN=...                   # existing bot token, never print
    STAR_DISCORD_OWNER_IDS=123456789012345678    # comma-separated owner IDs
    STAR_DISCORD_DM_CHAT=1                       # turn on direct-message chat
    STAR_DISCORD_DM_IMAGES=1                     # separately allow images
    STAR_DISCORD_DM_LEARNING_CANDIDATES=1        # separately allow explicit remember requests
    STAR_DISCORD_DM_PROJECT=STAR                 # project receiving untrusted candidate notes

Only the first two entries are required for existing slash-command functions; all three new DM feature flags default to 0. Image/lesson flags cannot be enabled unless DM chat is enabled. No other people, guild channels or permissions are added.

In the desktop application, configure a **vision-capable model** before attempting screenshots. The image path explicitly rejects a cloud provider; no private attachments are forwarded to third-party inference by this path.

## What a Discord DM can do

    Hey STAR, what is the difference between RemoteEvent and RemoteFunction?
    [attach hud.png] Identify overlaps and readability problems.
    remember: I prefer compact Roblox menus with no neon glow.
    remember correction: Always verify server-authoritative purchase values.

The final two examples create *candidates*, not accepted instructions. Review them inside STAR Desktop before they are promoted. Not every casual chat turns into a permanent memory. Third-party code, image text and malicious messages are not automatically trusted.

Do not use Discord to grant model runtime tool permissions, account API access, Studio edits, item purchases or training changes. These remain in the operator-owned desktop user interface.

## Security and troubleshooting

Discord officially delivers DMs with the app, including content and attachments, without granting the privileged guild MESSAGE_CONTENT intent. This implementation disables message content intent, never reads other people's server conversations, and requires an owner allowlist match.

When a screenshot fails, confirm: the DM feature flags, file size, allowed image MIME/file signature, the local vision model alias and whether that model truly supports the image protocol. An unsupported model should fail rather than hallucinate an image interpretation.

Raw image bytes are held only for the direct inference call, normalized to JPEG to drop EXIF. Text and the generated description are temporarily retained in in-RAM SessionMemory for follow-up chat, and can be reset using /star reset.

The new listener is OFF until configured and this draft PR is reviewed, tested and integrated. No Discord bot was started or deployed in preparing this change.

## References

- Discord Gateway intents and private-DM exception: https://github.com/discord/discord-api-docs/blob/main/developers/events/gateway.mdx
- Discord Message Content Intent alternatives: https://support-dev.discord.com/hc/en-us/articles/6383579033751-Message-Content-Intent-Alternatives-Workarounds
- Discord messaging and file limits: https://github.com/discord/discord-api-docs/blob/main/developers/resources/message.mdx
- STAR existing bot source: star/discord_bot/bot.py
- STAR candidate-memory storage: star/lessons.py
