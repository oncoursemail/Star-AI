# Set up a STAR Server brain

**Status: Opt-in.** You only need this page if you want a more powerful computer on your home network to
do the thinking for STAR, instead of your own PC.

## What a STAR Server is

A STAR Server is another computer in your home (often an always-on machine with lots of memory) that runs
the AI model. Your PC sends each message to it over your home network and shows the answer. Your PC
then needs no model download and no strong graphics card.

- Your messages go **only** to the address you type in. STAR never sends them to a cloud service instead.
- If the server is switched off, STAR tells you. It does **not** quietly switch to the brain on your PC
  or to anything else.
- The connection uses plain `http`, which is not encrypted. Use it only on a network you trust, such as
  your own home network.

> **Setting up the server computer itself** is a technical job (it runs a Linux AI server that speaks the
> same "OpenAI-compatible" language many AI tools use). The scripts STAR's own server uses are in the
> repository under [`server/brain`](../../server/brain). This page covers the part you do on your PC:
> connecting to a server that already runs.

## What you need from the person who runs the server

Ask them for three things:

1. **Server address.** It looks like `http://<server-address>:8080/v1`, where `<server-address>` is the
   server's private network number (it usually starts with `192.168.`, `10.` or `172.`). STAR only
   accepts a private network number here, not a name and not an internet address, and it must end in `/v1`.
2. **Server key.** A password-like key that lets your PC use the server.
3. **Model ID** (optional). STAR can list the server's models for you, so you can leave this until the test.

If the server's owner has put the key in a file called `server_api_key` in the `.star` folder of your
Windows user folder, STAR finds it and offers a **Use it** button, so you do not have to paste it.

## Connect STAR to the server

1. Open **Settings** and find the **Model & provider** panel.
2. Click **Connect to STAR Server** (or choose **STAR Server (LAN)** under **Inference provider**).
3. In the **STAR Server on your network** section, fill in:
   - **Server address**: the address from above.
   - **Server key**: paste the key, then click **Save key**. STAR stores it in Windows Credential Manager,
     not in a normal file. When it is saved you will see "Key present in OS vault". **Forget key** removes it.
4. Click **Test server**. STAR saves your settings, then checks four things in order:
   **Server reachable**, **Key and model list**, **Context and slots**, **Real test reply**.
5. If the test lists models as buttons, click the one you want. That fills in **Server model ID**.
6. When you see "STAR Server is ready", you are done. Start a [new chat](getting-started.md#your-first-chat).

The chat box then shows a green dot with **STAR Server** and the model name next to the send button.

### Optional settings

Under **Server limits (optional)** you can change how long STAR waits for an answer (**Wait per request
(seconds)**, default 600), how many requests may run at once (**Parallel requests (server slots)**, 1 to 4)
and the conversation size (**Context tokens per request**, 0 means "ask the server"). The test offers
**Use and save these limits** with values that suit the server, so most people never touch these.

**Allow Tailscale and carrier-grade NAT addresses** (off by default) is only for people who reach their
server through a private VPN such as Tailscale.

## When the test fails

| What STAR says (short) | What to do |
|---|---|
| "Cannot reach STAR Server" | Check that the server is on, that your PC is on the same network, and that the address and port are right. |
| "did not answer in time" | The server may be busy or still loading. Wait and test again, or raise **Wait per request**. |
| "refused the API key (401)" | The key is wrong. Paste the right key and click **Save key** again. |
| "still loading its model (503)" | Wait a minute, then test again. |
| "does not offer this model ID" | Pick one of the models the test lists. |
| "not as an OpenAI-compatible /v1 server" | The address points at something else. Check the port and the `/v1` ending. |
| "busy (429)" | Another request is running. Wait for it to finish. |
| "must use a private IP literal" or "must be on your private network" | Type the server's network number, not its name or an internet address. |

More help: [Troubleshooting](troubleshooting.md).

## Things the server can also provide

These work automatically once the server is connected, if the server's owner has installed them:

- **Web search without a paid key** (STAR's self-hosted search on the server). See
  [web search](chatting.md#search-the-web).
- **Roblox documentation search and Luau checks** (the STAR Knowledge service). See
  [Roblox tools](roblox-tools.md#luau-checks).

## Optional: a backup brain on this PC

**Status: Opt-in.** When STAR Server is selected, Settings shows **Optional: on-device backup brain**. You
can set up the brain on your PC there too, but STAR will **not** switch to it automatically when the server
is down. To use it, choose it yourself.

One related setting: **Instant answers on this PC** (Settings, **Interface & performance**, off by default)
lets STAR answer short, simple messages with a model that is already running on your PC, and use the
server for everything else. It never starts a model by itself.
