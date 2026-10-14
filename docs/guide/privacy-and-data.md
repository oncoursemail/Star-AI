# Privacy and data

STAR is built to be **local-first**: your chats and settings stay on your PC, and STAR only contacts the
internet for things you turn on or click. This page lists what is stored where and exactly what can leave
your computer.

## Short version

- **No telemetry.** STAR has no usage tracking, crash reporting or analytics service. The **Analytics**
  page only shows events stored on your own PC.
- **Your chats stay on your PC** (or go to the [STAR Server](star-server.md) you chose, if you chose one).
- **Keys and passwords** you give STAR are kept in **Windows Credential Manager**, not in normal files.
- **Nothing is sent to a cloud AI** unless you pick a cloud provider in Settings and add your own key.

## What is stored where

**Status: Available**

Almost everything lives in one folder: **`%APPDATA%\STAR`**. To open it, go to **More → Library** and click
**Open local STAR files**, or paste `%APPDATA%\STAR` into the File Explorer address bar.

| What | Where, inside `%APPDATA%\STAR` |
|---|---|
| Settings (never keys) | `settings.json`, voice settings in `voice.json` |
| Your chats, thumbs up/down, chat memory | `conversations.sqlite3` |
| What STAR learned (lessons, project knowledge) | `knowledge\knowledge.sqlite3` |
| Your corrections | `corrections.sqlite3` |
| Documents you attached | `documents.sqlite3` |
| Local activity charts | `analytics.sqlite3` |
| A record of each answer (secrets removed) | `runs\` |
| Created images, pinned pictures, screenshots | `generated-images\`, `references\`, `screen-captures\` (only the newest 40 screenshots are kept) |
| The brain on your PC | `models\`, `engines\`, `downloads\`, `brain.json` |
| Downloaded updates | `updates\` |
| Log files for troubleshooting | `logs\` |

Stored elsewhere:

- **Program files**: `%LOCALAPPDATA%\Programs\STAR` (replaced on every update; holds none of your data).
- **Voice models**, if you install them: `%LOCALAPPDATA%\STAR\voice-models`.
- **Keys**: Windows Credential Manager, under "STAR Intelligence" (STAR Server key, search keys, cloud AI
  keys, Roblox key). Some optional tools can also read a key file in the `.star` folder of your Windows user
  folder (STAR Server key, Roblox key, Discord bot token). Keep that folder private.

## What can leave your PC, and when

| Feature | What is sent | Where | When | Status |
|---|---|---|---|---|
| STAR Server brain | Your messages and the chat so far | Only the server address you typed | Every message, plus a short warm-up when STAR opens; it also reads the server's clock about every 30 minutes | Opt-in |
| Cloud AI provider (GroqCloud, OpenRouter, Gemini, Cerebras) | Your messages | That provider | Only if you select it and add your own key | Opt-in |
| Web search | Up to 600 characters of your message, as a search | Your Brave or Tavily account, or the search on your STAR Server | When **Search the web** is on, or automatically for questions about news, weather, prices or "latest" things, **if** a search provider is set up | Opt-in (needs a search key or server) |
| Roblox research tool | Search terms | Fixed Roblox, DevForum and YouTube addresses | When STAR decides to look something up about Roblox in Agent mode | Available |
| Roblox Open Cloud | Requests you approve | `apis.roblox.com` only | Only after you approve each action | Opt-in |
| Discord bot | Messages you send the bot, and its replies | Discord | Only if you set up your own bot | Opt-in |
| Read STAR source | File names and paths of STAR's own code | The public STAR repository on GitHub | Only when you switch on **Read STAR source** in Agent mode | Available |
| Model download | A file request | GitHub and Hugging Face | Only when you click **Download and start** | Available |
| Update check | A version request | GitHub releases | Only when you click **Check for updates** | Available |
| Links in answers | Opens your web browser | The link | Only when you click it (STAR opens only a short list of trusted sites, such as Roblox docs and GitHub) | Available |
| Background note summaries | Raw learning notes (they quote your chats) | The brain you chose (on a STAR Server, its spare fast model); a cloud provider only if you also turn on **Also summarise with a hosted provider** | After answers, when **Summarise raw notes in the background** is on (on by default) | Available; cloud is Opt-in |

Things that **do not** leave your PC: your settings, your lesson and correction databases as files, and screenshots
from **Look at my screen** until you send them. A screenshot or picture you attach goes, like the rest of that
message, to the brain you chose (the brain on your PC, your STAR Server, or a cloud provider if you picked one).

> **Good to know about automatic search.** STAR may search the web by itself for clearly time-sensitive
> questions, even if you did not switch on **Search the web**. This only happens when a search provider
> (a Brave or Tavily key, or your STAR Server's search) is set up. Without one, nothing is searched.

## Delete things

**Status: Available**

- **One chat:** in the sidebar, open the chat's **…** menu and choose **Delete**. An **Undo** button
  appears for about 6 seconds; after that the chat, its thumbs and its memory are removed for good.
  Images it created stay in `generated-images\`.
- **Something STAR learned:** see [Self-learning](self-learning.md#undo-and-forget).
- **A saved key:** in Settings, click **Forget key** next to it.
- **Everything:** STAR has no single "reset" button yet. Close STAR, then move or delete the
  `%APPDATA%\STAR` folder. STAR starts fresh next time (you will need to download the brain again).

## Back up and move to a new PC

1. Close STAR.
2. Copy the whole `%APPDATA%\STAR` folder to a USB drive or another disk.
3. On the new PC, install STAR, close it, and copy the folder back to the same place.

Keys in Windows Credential Manager are **not** in that folder; you will need to enter them again. A full
restore on a brand-new Windows install has not been formally tested, so keep your copy until you have
checked your chats.

## Copy or export

- **A chat:** open the chat's menu (the **…** at the top right) and choose **Copy conversation**. It is copied
  as text you can paste anywhere. There is no "save chat as a file" button yet.
- **Lessons:** the learning page can export them as a `.json` file. See
  [Self-learning](self-learning.md#undo-and-forget).
