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
3. Open `%USERPROFILE%\.star\discord-settings.env` (created for you; the template is in
   `star/discord_bot/local_config.py`) and fill in:

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

## 4b. Start it automatically (optional)

Running the bot in a terminal tab works, but it stops when the tab closes. There are two ways to keep it
running. Pick one; both are off until you switch them on.

**Only one bot runs at a time.** The bot takes a lock file in `%USERPROFILE%\.star` when it starts, so a second
start (terminal, STAR Desktop or Task Scheduler) exits at once instead of answering every message twice.
A bot started before this feature existed does not take the lock: restart it once with the current code
(Ctrl+C, then `scripts\star_discord.cmd`) before you turn on either option below.

### A. With STAR Desktop (Settings > Discord)

Settings > Discord shows the bot's state (Connected, Starting, Not configured, Error, or Running in another
window), a Start and a Stop button, and the switch **Start the Discord bot with STAR** (off by default).

- With the switch on, STAR starts the bot a few seconds after it opens, starts it again after a crash (waiting
  5, 10, 20, 40, 80, 160 and then 300 seconds between tries; a run of two minutes or more resets this), and
  stops it when STAR closes. After 10 quick crashes in a row it gives up and says so; press Start to try again.
- A wrong configuration (exit code 2) or a missing Discord library (exit code 3) is not retried: the page says
  what to fix.
- The page never shows the token, your Discord IDs or the server key. The bot reads the token and IDs from
  `discord.env` / `discord-settings.env` and the STAR Server key from STAR's saved key (Windows credential
  store) or, failing that, `%USERPROFILE%\.star\server_api_key`. "Not configured" lists which setting is missing.
- Turning the switch off leaves a running bot alone (use Stop). If the bot already runs in a terminal or in Task
  Scheduler, STAR shows "Running in another window", starts nothing, and takes over only if that bot stops.
- Logs are in STAR's log folder (`%APPDATA%\STAR\logs`): `discord-bot.log` (rotating, 1 MB x 4) and
  `discord-bot-console.log` (start-up errors).
- Which Python runs the bot: `STAR_DISCORD_PYTHON` if set, else the Python STAR itself runs on when it has
  discord.py, else `.venv` in the checkout, else `discord-venv` in STAR's data folder. The installed (packaged)
  STAR cannot run the bot by itself: set `STAR_DISCORD_PYTHON` (a Python with `requirements-discord.txt`) and
  `STAR_CHECKOUT` (a STAR checkout) as Windows user environment variables.
- If STAR is killed without closing (crash, Task Manager), the bot keeps running; the next STAR start shows it as
  running in another window.

### B. At Windows sign-in, without STAR Desktop (Task Scheduler)

`scripts\star_discord_autostart.cmd` creates one scheduled task, **STAR Discord bot**, for your account. You run it
yourself; nothing installs it for you. It needs no PowerShell and no administrator rights, and stores no password.

```
scripts\star_discord_autostart.cmd print     show the task without creating anything
scripts\star_discord_autostart.cmd install   create (or replace) the task
scripts\star_discord_autostart.cmd status    is it installed, when did it last run
scripts\star_discord_autostart.cmd start     run it now         stop    end the running task
scripts\star_discord_autostart.cmd remove    delete the task
```

The task runs 30 seconds after you sign in, in your own session (`InteractiveToken`, ordinary rights), with
`pythonw.exe` so no console window appears, and Windows restarts it up to 99 times a minute apart if it fails.
It uses the Python found by the script (`STAR_DISCORD_PYTHON`, else `.venv` in the checkout, else `py -3.12`),
so run the script from the checkout you want to keep (after the code is merged, a stable one, not a temporary
worktree) and install `requirements-discord.txt` into that Python first. The log is the same `discord-bot.log`.
The task only runs while you are signed in; "run whether signed in or not" would need your Windows password
and is deliberately not used. Use A or B, or both: if both start, the second one steps aside.

## 5. Use it

- **DM the bot** like a normal chat: click the bot in your server's member list > **Message**.
  It shows "typing…" while it thinks, answers long replies in several messages (code blocks kept
  intact), and remembers the last few turns for an hour (`/star reset` forgets them). Send `help` for
  a reminder.
- Attach **one screenshot** to a DM (or use `/image`) and ask about it.
- Slash commands: `/ask`, `/image`, `/screen`, `/status`, `/digest`, plus the `/star ...` group
  (research, speech, voice channel, reset, doctor).

## Opt-in switches (`discord-settings.env`)

| Switch | Default | What it does |
|---|---|---|
| `STAR_DISCORD_DM_CHAT` | 1 | Answer your DMs to the bot. |
| `STAR_DISCORD_DM_IMAGES` | 1 | Look at images you send (DM or `/image`); needs a vision model in STAR Settings; refused for cloud providers. |
| `STAR_DISCORD_DM_LEARNING_CANDIDATES` | 0 | `remember: ...` in a DM proposes a lesson; you approve it in STAR Desktop; never trusted automatically. |
| `STAR_DISCORD_SCREEN_CAPTURE` | 0 | `/screen` lets STAR look at this PC's screen. **Every capture needs you to press "Capture my screen now"** (expires after 60 s, one capture per press). Nothing is saved; you see the capture privately. |
| `STAR_DISCORD_LEARNING_DM_OPT_IN` | 0 | DM a short Night School digest when the verified practice numbers change (at most one per 6 h); `/digest` shows it on demand. Report source: `STAR_DISCORD_LEARNING_REPORT_SSH` (your existing key login to the brain server) or `STAR_DISCORD_LEARNING_REPORT` (a local file). |
| `STAR_DISCORD_RATE_LIMIT` | 30 | Requests per 10 minutes before STAR asks you to slow down. |
| `DISCORD_CHANNEL_IDS` | empty | Limit server use to these channels. |

## What the bot will never do from Discord

No file writes, no Roblox Studio edits, no GitHub, no shell, no MCP tools, no passwords. Messages
and images sent to it are treated as untrusted data, never as permission. Strangers get no answer at all.

## If something is wrong

- `doctor` shows `[SETUP]` lines with the fix for each.
- `smoke` says the token was rejected: reset it in the Developer Portal and replace the line in `discord.env`.
- Slash commands missing: set `STAR_DISCORD_SYNC_COMMANDS=global`, start once, then set it back to `0`.
- To revoke everything: Developer Portal > Bot > Reset Token (the old token stops working at once),
  or remove the bot from your server.
