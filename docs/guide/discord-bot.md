# Talk to STAR on Discord

**Status: Opt-in** (early version; set up from a command window, not from inside the STAR app)

You can give STAR its own Discord bot so you can ask it things from your phone or another computer. The bot
runs on your PC, uses the same brain you chose in STAR, and **only answers you**.

> **Before you start, be aware:**
> - Setup takes about 15 minutes and needs a **copy of STAR's source code with Python 3.11 or 3.12**, because
>   the bot is started with a script from the source folder. The normal STAR installer does not include it.
>   If that sounds unfamiliar, ask someone technical to help with step 4.
> - The bot only works while your PC is on and the bot window is open.
> - STAR uses its **own** bot account. It never logs into your personal Discord account.

## 1. Create the bot on Discord

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and click **New
   Application**. Name it `STAR`.
2. **Installation** tab: tick **Guild Install** only, and set **Install Link** to **None**.
3. **Bot** tab:
   - Turn **Public Bot** off, so only you can add it to a server.
   - Leave **Presence**, **Server Members** and **Message Content** all **off**. STAR does not need them and
     never reads your server's conversations.
   - Click **Reset Token**, then **Copy**. This token is like a password for the bot: never paste it into a
     chat, a screenshot or anywhere except the file in the next step.
4. **General Information** tab: copy the **Application ID**.

## 2. Put the token and your IDs on your PC

1. Open Notepad. Type one line, with your token after the `=`:

   ```
   DISCORD_BOT_TOKEN=paste-the-token-here
   ```

   Save it as `discord.env` (choose "All files") in the folder `%USERPROFILE%\.star` (create the `.star`
   folder if it does not exist).
2. In Discord, turn on **User Settings → Advanced → Developer Mode**. Right-click your own name and choose
   **Copy User ID**; right-click your server's icon and choose **Copy Server ID**.
3. In the same `.star` folder, create `discord-settings.env` with:

   ```
   DISCORD_OWNER_ID=your-user-ID
   DISCORD_GUILD_ID=your-server-ID
   STAR_DISCORD_DM_CHAT=1
   STAR_DISCORD_SYNC_COMMANDS=global
   ```

   `STAR_DISCORD_DM_CHAT=1` lets you chat with the bot in private messages (it is off if the line is
   missing). Other optional switches are listed [below](#optional-switches).

## 3. Invite the bot to your server

Open this link in your browser while logged into Discord, after replacing `APP_ID` with your Application ID:

```
https://discord.com/oauth2/authorize?client_id=APP_ID&scope=bot+applications.commands&permissions=52224&integration_type=0
```

This asks only for: view channels, send messages, embed links and attach files. No admin rights. (For the voice
features, use `permissions=70368747375616` instead, which adds connect, speak and send voice messages.)

## 4. Start the bot

First choose and test a brain in the STAR app (see [Getting started](getting-started.md)); the bot uses the
same one. Then, in a Command Prompt window inside the STAR source folder (after installing its requirements with
`pip install -r requirements.txt -r requirements-discord.txt`):

| Command | What it does |
|---|---|
| `scripts\star_discord.cmd doctor` | Checks your setup without going online. Never shows the token. Lines starting with `[SETUP]` tell you what to fix. |
| `scripts\star_discord.cmd smoke` | Logs in once to confirm the bot and your server. Sends nothing. |
| `scripts\star_discord.cmd` | Runs the bot. Keep the window open; press Ctrl+C to stop. |

After the first good start, change `STAR_DISCORD_SYNC_COMMANDS=global` to `STAR_DISCORD_SYNC_COMMANDS=0` in
`discord-settings.env`. (It only needs to register the commands with Discord once.)

## 5. Use it

- **Private messages:** click the bot in your server's member list, choose **Message**, and chat. It remembers
  the last 6 messages for an hour (in memory only). Send `help` for a reminder.
- **Commands:** `/ask` (private by default), `/image` (ask about a picture), `/screen`, `/status`, `/digest`,
  and the `/star` group: `ask`, `research`, `help`, `status`, `doctor`, `reset` (forget the conversation), plus
  voice commands `speak`, `hear`, `converse`, `join`, `say`, `stop`, `leave`.
- **Right-click a message → Apps → Ask STAR about this.**
- **News and fresh facts:** for questions about news, prices, weather or "the latest" something, the bot looks
  on the web (if a search is set up, see [Search the web](chatting.md#search-the-web)) and ends its answer with
  source links. `/star research` always searches and lists its sources.

Voice messages and the voice channel features post in public; the bot speaks in voice channels but never
listens. These voice features need the optional voice add-on and are less tested.

## Who can use it

Only the Discord user ID in `DISCORD_OWNER_ID`. Without it the bot refuses to start. Other people get "Only the
configured STAR owner can use this bot" on commands, and no reply at all in private messages. It only works in
the server you listed, and ignores group messages.

## What the bot can and cannot do

- It sends your messages to the brain chosen in STAR (your PC, your STAR Server, or a cloud provider if you
  picked one). Pictures are only looked at by a brain on your own hardware, never a cloud provider, and are not
  saved.
- From Discord it can **never** write files, edit Roblox Studio, use GitHub, run commands, or change settings.
- Its log records only timings, not your messages.

## Optional switches

Add these lines to `discord-settings.env` to change behaviour (1 = on, 0 = off):

| Line | If missing | What it does |
|---|---|---|
| `STAR_DISCORD_DM_CHAT=1` | off | Answer your private messages. |
| `STAR_DISCORD_DM_IMAGES=1` | off | Look at pictures you send (needs `STAR_DISCORD_DM_CHAT=1` and a brain that can see images on your own hardware). |
| `STAR_DISCORD_SCREEN_CAPTURE=1` | off | Lets `/screen` look at your PC's screen. Every capture needs you to press **Capture my screen now** (it expires after 60 seconds). |
| `STAR_DISCORD_DM_LEARNING_CANDIDATES=1` | off | `remember: ...` or `wrong: ...` in a private message suggests a lesson or correction. You approve it in the STAR app ([Self-learning](self-learning.md)). |
| `STAR_DISCORD_RATE_LIMIT=30` | 30 | How many requests per 10 minutes before STAR asks you to slow down. |
| `DISCORD_CHANNEL_IDS=` | any channel | Limit the bot to these channels in your server. |

## Turn it off or revoke it

- Press Ctrl+C in the bot window to stop it.
- To cut it off for good: Developer Portal → **Bot** → **Reset Token** (the old token stops working at once),
  or remove the bot from your server, and delete `discord.env`.

## Coming soon

**Status: Coming soon.** Starting the bot automatically with Windows, and a Discord section in STAR's Settings,
are being worked on but are not in STAR yet.
