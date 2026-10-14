# Troubleshooting and FAQ

Find the message you see, or the question you have, below. If nothing helps, see
[Asking for help](#asking-for-help) at the end.

## STAR does not answer

**Status: Available** (all the checks below are built into STAR)

| What you see | What to do |
|---|---|
| "STAR Brain is offline" or "Cannot reach STAR Brain" | The brain on your PC is not running. Go to **More → Model & connection** and click **Start local model**. STAR does not start it automatically. |
| "Download STAR Brain first" | Click **Download and start** on **More → Model & connection**. |
| "Not enough free disk space. STAR Brain needs around 4.3 GB free." | Free up disk space, then try again. |
| "failed checksum verification" | A download was damaged. Click the button again; STAR downloads the broken part again. |
| "STAR Brain did not respond in time" | The model may still be loading, or your PC is short of memory. Close other big programs and try again. |
| "STAR Brain ran out of context space" | The chat has become too long. Start a **New chat**. |
| "Local model did not become ready" | Restart STAR and try **Start local model** again. If it keeps failing, see [Asking for help](#asking-for-help) (the log is `logs\star-brain-react.log`). |
| Anything starting with "STAR Server…" | See the table in [STAR Server: when the test fails](star-server.md#when-the-test-fails). |
| "No STAR Server model is selected" | Settings → **Model & provider** → **Test server**, then click one of the models it lists. |
| "…needs an API key" or "denied access" (cloud provider) | Check the cloud provider's key in Settings → **Model & provider**, and your account limits with that provider. |

To test the brain at any time: Settings → **Test actual response** (brain on this PC) or **Test server** (STAR
Server). On **More → Model & connection** there is also **Test connection**.

## Chat questions

**The answer stopped halfway.** Click **Retry**, or **Edit message** to change your question.

**I deleted a chat by mistake.** Click **Undo** in the message at the bottom left within about 6 seconds. After
that it cannot be recovered (unless you have a [backup](privacy-and-data.md#back-up-and-move-to-a-new-pc)).

**Search chats does not find a word I know is in a chat.** **Search chats** only searches chat names. Open the
chat and use **Find in this chat** (the magnifying glass at the top right).

**My older chats are missing.** The list shows the 60 most recent chats of the open project. Check that the right
project is selected on **Projects**.

**"Search the web" is greyed out ("Needs STAR Server or a search key").** STAR has no search service yet. Connect
a [STAR Server](star-server.md) that has search installed, or ask someone technical to add a Brave Search or
Tavily key (see [Search the web](chatting.md#search-the-web)).

**"Web search needs STAR Server (self-hosted search) or a Brave Search / Tavily API key."** Same cause as above.
Switch off **Search the web** (click the **Web** chip's **×**) to chat without it.

**"No image engine is set up".** Creating pictures needs ComfyUI on your PC. In Settings → **Where STAR
generates**, set **ComfyUI folder**, or click **Start ComfyUI**. See [Create image](chatting.md#create-image).

**"ComfyUI stopped right after starting".** Its messages are in `logs\comfyui.log` in your STAR files. A common
cause is not enough graphics memory: click **Free graphics memory** and try again.

**A video file does nothing useful.** Video needs FFmpeg. Set **FFmpeg folder** in Settings → **Where STAR
generates**.

**"Binary Roblox .rbxm/.rbxl files are not supported".** In Roblox Studio, save or export as `.rbxmx` / `.rbxlx`
(XML) and attach that instead.

**"Install optional voice extras".** **Transcribe audio** needs the voice add-on, which is not in the installer
yet. See [Voice and calls](voice-and-calls.md).

## Roblox Studio questions

**STAR cannot find Studio.** Make sure a place is open in Studio and that Studio is switched on under
**Assistant → Manage MCP Servers**. Then click **Test & discover Studio** again and choose the place under **Open
Studio instance**.

**STAR can read but not change my place.** That is the safety rule working. STAR only edits a blank, unsaved place
(and, if you allow it, places of STAR's own Roblox account), and only after you turn on **Allow edits in the
selected Studio**. See [Roblox tools](roblox-tools.md#what-keeps-your-games-safe).

**My edit permissions switched themselves off.** Changing the Studio connection or the chosen place always turns
them off again. Switch them back on for the new test place.

**Roblox Open Cloud says a permission is missing or the key was revoked.** Settings → **Roblox** → **Test**, then
check the key's permissions and expiry in the Roblox Creator Dashboard.

## Discord bot questions

See also [Talk to STAR on Discord](discord-bot.md).

- **The slash commands do not appear.** Set `STAR_DISCORD_SYNC_COMMANDS=global` in `discord-settings.env`, start
  the bot once, then set it back to `0`.
- **The bot ignores my private messages.** Add `STAR_DISCORD_DM_CHAT=1` to `discord-settings.env` and restart the
  bot.
- **"unknown setting name".** A line in one of the `.env` files has a typo. `doctor` tells you which line.
- **Notepad saved the file as `discord.env.txt`.** Rename it so it ends in `.env` (turn on **File name extensions**
  in File Explorer's **View** menu to see the real name).
- **The token was rejected.** Reset it in the Discord Developer Portal and replace the line in `discord.env`.

## Updates and installing

**Windows warns about an unknown publisher.** STAR is not code-signed yet, so Windows shows this warning. Only
download STAR from the official [releases page](https://github.com/oncoursemail/Star-AI/releases/latest).

**Windows asks for administrator approval on every update.** STAR was installed "for all users". To stop the
prompts, uninstall it and install again with the default "just for me" choice. Your data stays in
`%APPDATA%\STAR`.

**"No public STAR Release is accessible".** STAR could not reach GitHub. Click **Open public releases** and
download Setup in your browser.

## FAQ

**Does STAR need the internet?** Only to download STAR and its brain, to check for updates, and for features you
switch on (web search, a cloud provider, Discord). Chatting with the brain on your PC works offline.

**Does STAR send my chats to anyone?** No, unless you choose a STAR Server or a cloud provider as the brain. Then
your messages go to that one place only. There is no telemetry. See [Privacy and data](privacy-and-data.md).

**Does STAR learn from me?** It keeps short written lessons that you can see and remove; it does not retrain its
model. See [Self-learning](self-learning.md).

**Can STAR break my Roblox game?** STAR can only edit a blank, unsaved place (or STAR's own account's places if you
allow it), and never saves or publishes. Still, keep backups and work in test places.

**Is the Discord bot or voice part of the normal install?** Not yet. The Discord bot needs a source copy of STAR,
and live voice calls are coming soon.

**Which features are finished?** Each page in this guide marks features as **Available**, **Opt-in** or **Coming
soon**. See the [guide home page](README.md#feature-status-at-a-glance).

## Asking for help

1. Note the exact error message (a screenshot of the message is fine). **Never** include keys, tokens or passwords.
2. Note your STAR version (bottom left, next to **Settings**).
3. Log files are in `%APPDATA%\STAR\logs`. They do not contain your keys, but may mention file names; check before
   sharing.
4. Report the problem on the [STAR issues page](https://github.com/oncoursemail/Star-AI/issues).
