# Roblox tools

STAR is built to help you make Roblox games: it answers Roblox and Luau questions, checks Luau code, plans
maps, and can look at (and, in a test place, build in) Roblox Studio.

> **The golden rule: only let STAR build in a test place.** STAR can only change a blank, unsaved place (or,
> if you allow it, a place owned by STAR's own Roblox account). Every other place stays read-only, whatever
> you switch on. Still, keep a copy of anything you care about, and never point STAR at a game other people
> play.

## Ask Roblox questions

**Status: Available**

Just ask in a chat. Name the thing you need ("a Luau ModuleScript for a server-side inventory", "why does my
RemoteEvent fire twice?"). The starter idea **Review my Luau script** fills in a review request for you.

When STAR has looked something up in the official Roblox documentation, the answer ends with **Sources
retrieved by STAR** and links to the Roblox Creator Hub. Open them and check. If an answer has no sources, do
not assume STAR checked the documentation.

Documentation search needs the STAR Knowledge service on a [STAR Server](star-server.md). In Agent mode STAR
can also look at public Roblox, DevForum and YouTube pages (Tools → **STAR Tool Workshop** → **Enable public
Roblox game, docs, forum and Poly Haven asset research**, on by default).

## Luau checks

**Status: Available** (the full check needs a STAR Server)

When an answer contains Luau code, STAR can check it before you see it. The answer then shows **Luau check by
STAR:** with the result.

- **Always on:** a quick built-in scan for common mistakes and unsafe patterns (for example trusting what a
  player's client sends).
- **With a STAR Server:** the official Luau compiler and type checker run on the server. The code is checked,
  **not run**.
- **Advanced, opt-in:** a local `luau-analyze` checker, turned on with the `STAR_LUAU_ANALYZE=on` environment
  variable when `luau-analyze` is already installed.

A passed check means the code compiles and its types make sense. It does **not** mean STAR ran it in Roblox
Studio or that the game behaves the way you want. Test in Studio yourself.

## Map plans

**Status: Available** (plans only; nothing is built automatically)

Ask for a map, blockout, greybox or level layout, for example: *"Plan a greybox obby map with three sections
and a checkpoint between each."* STAR writes a plan and checks it on paper: that parts do not overlap, that
spawns have head room, that jumps are possible (gaps up to 8 studs, rises up to 6.5 studs), and that only
allowed assets are used.

It can also write one Luau script that builds the plan under `Workspace/MapDrafts` as a single undo step. STAR
does not run that script for you. You can paste it into a test place yourself, or let STAR build it if you have
connected Studio with edits allowed (below).

## Connect Roblox Studio

**Status: Opt-in.** Reading is safe to try; editing is off until you switch it on.

### 1. Prepare Studio

1. Open Roblox Studio and create a **new, blank place**. Do not save or publish it.
2. In Studio, open **Assistant → Manage MCP Servers** and switch Studio on as an MCP server. (Roblox's guide:
   [Studio MCP](https://create.roblox.com/docs/studio/mcp).)

### 2. Connect STAR

1. In STAR, open **Tools** and find **STAR local MCP · Roblox Studio**.
2. Under **Studio connection**, choose **This PC · your Studio**.
3. Click **Test & discover Studio**. The test lists what STAR can do and which places are open. It changes
   nothing in Studio.
4. Under **Open Studio instance**, choose your blank place.

(Settings also has a **Roblox Studio** panel with **This PC** and **Test connection**; it is the same
connection.)

STAR can now **read**: look at the place's objects and scripts, read the output window, and take Studio
screenshots.

### 3. Allow building (only in a test place)

On the same panel:

- **Allow edits in the selected Studio**: lets STAR edit scripts and objects and start playtests, but only
  when it has confirmed the place is a blank, unsaved place.
- **Allow Luau and instance building**: lets STAR run Luau inside that test place to create parts and UI.

Changing the connection or the place switches both off again. In **Settings → Roblox** you will find the same
choices worded as **Studio edits in a blank, unsaved place** and **Let STAR run Luau in the sandbox**, plus
**Also places of STAR's own account (the account of the tested key)** for places owned by STAR's own Roblox
account. All of them start **off**.

### What keeps your games safe

- STAR asks Studio which place is open before **every** change. If you switched to another place in the
  meantime, the change is refused and the rest of the turn only reads.
- Published places, other people's places, unsaved places that already contain scripts STAR did not make, and
  places STAR cannot identify are always read-only. A built-in block list always wins.
- STAR never saves or publishes a place from Studio, and never inserts marketplace assets or uploads images.
- There is no pop-up before each edit. Instead, each answer ends with a list of what STAR created or changed
  and how to undo it. Afterwards, Studio's own **Undo** (Ctrl+Z) is the way back.

## Roblox Open Cloud key (publishing tests)

**Status: Opt-in.** Only needed for STAR's automated test pipeline on a private test experience.

1. In the [Roblox Creator Dashboard](https://create.roblox.com/), create an API key limited to a **private
   test experience** owned by the account STAR should use.
2. In STAR, open **Settings → Roblox**, paste it, click **Save key**, then **Test**. The key is kept in Windows
   Credential Manager. **Forget key** removes it.
3. Fill in **Universe ID** and **Place ID** and click **Use this experience**. STAR checks that the experience
   is private and owned by the key's account.

Every publish or test request then waits under **Actions waiting for you** for you to click **Approve** or
**Reject**. Requests expire after 15 minutes. A publish creates a saved version, not a live update. Never paste
keys into a chat or a screenshot.

## Studio Lab

**Status: Coming soon.** Studio Lab is a planned loop in which STAR plans a build, applies it in a real test
Studio, playtests, looks at the result and fixes problems. It is being worked on but is **not** in STAR yet.
