# Talk to STAR on Discord: setup (owner only)

STAR uses its **own Discord bot** (an application with a bot token). It never logs into, or
automates, your personal Discord account: self-bots break Discord's terms and are not supported.
The bot answers **only your Discord user ID**, in DMs and in the server you approve.

Time needed: about 10 minutes.

## 1. Create the bot in the Developer Portal

1. Open <https://discord.com/developers/applications> and click **New Application**. Name it `STAR`.
2. **Installation** tab
   - Installation Contexts: tick **Guild Install** only (untick User Install).
   - Install Link: choose **None** (you will use the link in step 3; Discord requires this before the
     bot can be made private).
3. **Bot** tab
   - Turn **Public Bot OFF**, so only you can add it to a server.
   - Privileged Gateway Intents: leave **Presence**, **Server Members** and **Message Content** all
     **OFF**. STAR does not need them: slash commands and DMs to the bot work without them, and the
     bot never reads your server conversations.
   - Click **Reset Token**, then **Copy**. Do not paste it anywhere except the file in step 2 below.
4. **General Information** tab: copy the **Application ID** (needed for the invite link).

## 2. Put the token and your IDs on this PC (never in Git, never in a chat)

1. Open Notepad and create `%USERPROFILE%\.star\discord.env` with one line:

   ```
   DISCORD_BOT_TOKEN=paste-the-token-here
   ```

   Save it (File > Save as, "All files", name `discord.env`). This file is the only place the token lives.
2. In Discord: **User Settings > Advanced > Developer Mode** on. Right-click your own name >
   **Copy User ID**; right-click your server icon > **Copy Server ID**.
3. Open `%USERPROFILE%\.star\discord-settings.env` (created for you the first time you run
   `scripts\star_discord.cmd doctor` or start the bot, if the file is missing; an existing file is never
   overwritten; the template is in `star/discord_bot/local_config.py`) and fill in:

   ```
   DISCORD_OWNER_ID=<your user ID>
   DISCORD_GUILD_ID=<your server ID>
   ```

   The other lines are the opt-in switches (see the table below).

## 3. Invite the bot with only the permissions it needs

Replace `APP_ID` with your Application ID and open the link while logged into Discord:

```
https://discord.com/oauth2/authorize?client_id=APP_ID&scope=bot+applications.commands&permissions=52224&integration_type=0
```

`52224` = View Channels, Send Messages, Embed Links, Attach Files. Nothing else: no Administrator,
Manage Server, Manage Roles, Manage Messages, Mention Everyone or Read Message History.

Optional, only if you want STAR's voice features (`/star speak`, `/star join` and `/star say`): use
`permissions=70368747375616` instead (adds Connect, Speak and Send Voice Messages).

## 4. Start it

From the STAR checkout, in cmd (PowerShell scripts are not needed):

```
scripts\star_discord.cmd doctor     offline check: shows what is set up, never prints the token
scripts\star_discord.cmd smoke      live check: logs in, confirms the bot and your server; sends nothing
scripts\star_discord.cmd            run the bot (stop with Ctrl+C)
```

On the first start keep `STAR_DISCORD_SYNC_COMMANDS=global` so Discord learns the slash commands
(in your server and in your DM with the bot). After that first good start, set it to `0`.

The bot uses the **same model STAR Desktop uses** (Settings > model / fast model; vision model for
images), including the STAR Brain server when that is your provider. Choose those in STAR Desktop first.

## 5. Use it

- **DM the bot** like a normal chat: click the bot in your server's member list > **Message**.
  It shows "typing…" while it thinks, answers long replies in several messages (code blocks kept
  intact), and remembers the last few turns for an hour (`/star reset` forgets them). Send `help` for
  a reminder.
- Attach **one screenshot** to a DM (or use `/image`) and ask about it.
- Attach **two images** to an owner DM (first desired reference, second current STAR result), or use `/compare` with the two attachments. STAR produces a private local-vision critique and a proposed change list; images are normalized and not stored in chat history. A screenshot is not enough to judge motion, rig correctness, or real Studio test results.
- If `STAR_DISCORD_DM_LEARNING_CANDIDATES=1` is enabled and your previous DM was about an image, a follow-up like “I don’t like that” or “you messed up the animation” creates a review-only correction candidate, not automatic changes or training. You can also use `wrong: ...` or `remember correction: ...` explicitly.
- Slash commands: `/ask`, `/image`, `/screen`, `/status`, `/digest`, plus the `/star ...` group
  (research, speech, voice channel, reset, doctor).

## Opt-in switches (`discord-settings.env`)

In code every switch is OFF unless set. The generated template turns on DM chat and images; lesson
candidates, screen capture and Night School DMs stay 0 until you change them.

| Switch | Default (if unset) | What it does |
|---|---|---|
| `STAR_DISCORD_DM_CHAT` | 0 (template sets 1) | Answer your DMs to the bot. |
| `STAR_DISCORD_DM_IMAGES` | 0 (template sets 1) | Look at images you send (DM or `/image`); needs a vision model in STAR Settings; refused for cloud providers. |
| `STAR_DISCORD_DM_LEARNING_CANDIDATES` | 0 | `remember: ...` in a DM proposes a lesson; you approve it in STAR Desktop; never trusted automatically. |
| `STAR_DISCORD_SCREEN_CAPTURE` | 0 | `/screen` lets STAR look at this PC's screen. **Every capture needs you to press "Capture my screen now"** (expires after 60 s, one capture per press). Nothing is saved; you see the capture privately. |
| `STAR_DISCORD_LEARNING_DM_OPT_IN` | 0 | DM a short Night School digest when the verified practice numbers change (at most one per 6 h); `/digest` shows it on demand. Report source: `STAR_DISCORD_LEARNING_REPORT_SSH` (your existing key login to the brain server) or `STAR_DISCORD_LEARNING_REPORT` (a local file). |
| `STAR_DISCORD_RATE_LIMIT` | 30 | Requests per 10 minutes before STAR asks you to slow down. |
| `STAR_DISCORD_LAB_STATUS` | 0 | Enable read-only owner Lab progress/screenshot reports from a trusted, pre-staged job receipt; does not control Studio or capture the host desktop. |
| `STAR_DISCORD_LAB_REPORT` | empty | Absolute path on the bot host to an operator-approved latest.json receipt and same-folder checked viewport/render screenshot. |
| `STAR_DISCORD_PRESENCE` | 0 | Optional bot-account activity while connected. Rotate only fixed, privacy-safe Playing/Watching labels. No activity is sent when off. |
| `STAR_DISCORD_PRESENCE_MINUTES` | 15 | Time between changes while online, 10–120 minutes. No rapid presence updates or changes inside `on_ready`. |
| `DISCORD_CHANNEL_IDS` | empty | Limit server use to these channels. |

## Optional Studio Lab / Blender screenshot reports

STAR can answer `/star lab`, `/star labshot` and selected plain-language owner
DM questions about what the test Studio is doing, **only if an operator first
configures a trusted local job receipt**. This is NOT a new remote screen
capture tool. Nothing is fetched from Brain 2 unless an authorized Studio Lab
or Blender producer has already staged timestamped, checksum-matched evidence
on the bot host. Slash command results are private; image sending requires
an explicit owner command. See
[STAR_DISCORD_LAB_EVIDENCE_20261013.md](STAR_DISCORD_LAB_EVIDENCE_20261013.md)
for schema, security limits, integration and validation.

STAR's separate opt-in learning digest already sends owner DMs on meaningful
verified Night School changes when configured with a real report source.
These are practice results, not automatically trained neural weights or
unconditionally successful Roblox Studio builds.

## Optional bot-account activity

To show a simple STAR activity under its Discord bot profile, set `STAR_DISCORD_PRESENCE=1`
in `discord-settings.env` and restart the bot. Initially it displays
`Watching /star help`, then rotates (default every 15 minutes) through a small,
fixed set of privacy-safe activities such as `Playing STAR Intelligence`. Its
status is visible only while the bot is online. This does not change the
Discord application biography, send an MOTD, start any self-training job or
read guild messages. Use `/status` to see whether activity rotation is configured.

For privacy and reliability, activity labels cannot be generated by models or
Discord input. The bot starts the initial presence from its constructor, and
periodic changes run from a cancellable background task rather than the
repeatedly invoked Discord `on_ready` callback. Live verification still requires
the owner to start the bot and look at its actual Discord presence.

## What the bot will never do from Discord

No file writes, no Roblox Studio edits, no GitHub, no shell, no MCP tools, no passwords. Messages
and images sent to it are treated as untrusted data, never as permission. Strangers get no answer at all.

## If something is wrong

- `doctor` shows `[SETUP]` lines with the fix for each.
- `smoke` says the token was rejected: reset it in the Developer Portal and replace the line in `discord.env`.
- Slash commands missing: set `STAR_DISCORD_SYNC_COMMANDS=global`, start once, then set it back to `0`.
- To revoke everything: Developer Portal > Bot > Reset Token (the old token stops working at once),
  or remove the bot from your server.
