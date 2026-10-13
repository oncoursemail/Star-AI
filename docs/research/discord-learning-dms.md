# STAR Discord learning digests (draft, default OFF)

STAR already includes an owner-only Discord bot with slash commands, web research, voice features, and no desktop tool permissions. This proposal adds a **separate opt-in one-shot sender** for evidence-backed Night School updates. It does not listen to user messages, install a background service, import screenshots automatically, or change model weights.

## Before using it

A bot token must be created and stored **outside** the repository and logs. Do not paste it in GitHub, Discord chats, or AI messages. The user must approve the exact Discord recipient (a numeric owner ID). The app does not send to arbitrary channels or guilds.

Required trusted host environment variables:

- STAR_DISCORD_OWNER_IDS: comma-separated numeric Discord owner IDs already permitted by the existing bot.
- STAR_DISCORD_LEARNING_DM_OWNER_ID: one of those exact owner IDs.
- STAR_DISCORD_LEARNING_DM_OPT_IN=1: mandatory permission for delivery.
- STAR_DISCORD_BOT_TOKEN: existing bot token; needed only to send.
- STAR_DISCORD_LEARNING_REPORT: absolute path to the verified Night School latest.md.
- STAR_DISCORD_LEARNING_STATE: absolute path to a private SQLite state file in an existing directory.
- STAR_DISCORD_LEARNING_DM_COOLDOWN_HOURS: optional 1..168, default 6.

An operator can test without sending a message using:

    python -m star.discord_bot.learning_sender --dry-run

Only after reviewing the local preview:

    python -m star.discord_bot.learning_sender --send

There is **no automatic schedule** created by this PR. A trusted owner may separately set a daily/nightly scheduled one-shot invocation after seeing the first test. The sender only sends when checked examples, lesson-assisted repairs or unseen validation scores have improved; repeated rewrites while the service is held do not trigger a new DM. The state database prevents duplicate automatic sends and marks uncertain network deliveries for manual investigation rather than retrying blindly.

A DM explicitly says which test tier it represents. A Night School report means Luau static/stand-in VM checks only; it must never claim live Roblox Studio gameplay tests, perfected design, new neural weights or general intelligence gains.

### Optional real screenshots

By default **no images or user files leave the machine**. To attach a particular, reviewed PNG/JPEG image, the operator must additionally configure:

- STAR_DISCORD_LEARNING_VISUAL_DIRECTORY: absolute directory containing an actual test screenshot.
- STAR_DISCORD_LEARNING_VISUAL_MANIFEST: absolute JSON path explicitly approved for the current report.

Example manifest (hash is illustrative and must be recomputed from the real file):

    {
      "format": "star-owner-approved-visual-v1",
      "report_stamp": "2026-10-13T04:41:55Z",
      "filename": "studio-ui-after.png",
      "sha256": "REPLACE_WITH_REAL_64_CHARACTER_LOWERCASE_HEX_SHA256",
      "approved_for_owner_dm": true
    }

The manifest itself is not an automatic permission grant: the host's operator is responsible for preparing and approving it. The sender only accepts bounded regular PNG/JPEG files with a matching digest and safe filename. Unapproved, modified, oversized or symlinked files are rejected. Model text cannot select screenshots or new file paths.

### What learning means

The sender only **reports** verified local results. Owner corrections can enter the existing STAR LessonStore as **candidates** after an explicit action and must be reviewed in the desktop UI before they are trusted across projects. No code in this PR records Discord messages as lessons. Future DM conversation and image analysis should be built in a separately tested addition.

### Security and rollback

- No Discord privileged MESSAGE_CONTENT intent, account scraping, self-bots, filesystem commands, Studio edits, arbitrary tool access, or new model calls.
- Rate limit at the application layer, plus discord.py's HTTP 429 handling.
- Stop sending immediately by removing STAR_DISCORD_LEARNING_DM_OPT_IN.
- Keep the existing Discord chat bot running independently; this notifier is a one-shot REST-only tool.
- Never ship tokens, Discord IDs, chat histories or raw training transcripts as PR artifacts.

## Primary references

- Discord Gateway intents: https://github.com/discord/discord-api-docs/blob/main/developers/events/gateway.mdx
- Discord API rate-limit policy: https://github.com/discord/discord-api-docs/blob/main/developers/topics/rate-limits.mdx
- Discord API message attachment limits: https://github.com/discord/discord-api-docs/blob/main/developers/resources/message.mdx
- STAR existing bot: star/discord_bot
- Night School verification: server/night_school
