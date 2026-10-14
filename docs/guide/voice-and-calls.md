# Voice and calls

## Talk to STAR in a live call

**Status: Coming soon.** A call screen in the STAR app, where you talk and STAR answers out loud, is being built
but is **not** in STAR yet. The speech parts behind it exist and have been tested with recorded audio files, but
not yet with a real microphone and speakers, and there is no button in the app that starts a call.

Technical users can try an early command-line version (it needs a STAR Server, Python and about 1 GB of
downloads); see the developer notes in [Voice calls](../STAR_VOICE_CALLS.md). Everyone else: please wait for the
in-app version.

## Choose Star's voice

**Status: Available** (hearing a preview needs the optional voice engine)

Open **Settings** and find **Star's voice** (in the **Where STAR generates** area).

- Each voice has **Preview** and **Use this voice**. The one in use says **In use**.
- Tags help you choose: **Best for live calls**, **Best quality**, and **Not usable in live calls yet**.
- The warm, caring style is the **Default**. Turn on **Offer the confident and commanding voices** to see the
  optional extra styles.
- Every voice is an original synthetic voice; none copies a real person.

If the voice engine is not installed you will see "The voice engine is not installed on this PC". You can still
pick a voice now; it will be used once the engine is installed. Your choice is saved in `voice.json` in your
[STAR files](privacy-and-data.md).

## Turn a recording into text

**Status: Opt-in** (needs the optional voice add-on)

In a chat, choose **+ → More → Transcribe audio** and pick an audio file (WAV, MP3, M4A, FLAC, OGG or AAC, up to
200 MB). STAR writes out what is said into the message box, so you can edit it before sending. This runs on your
PC; the recording is not sent anywhere.

If the add-on is missing, STAR says so. The add-on is not part of the normal installer yet.

## Voice on Discord

**Status: Opt-in.** The [Discord bot](discord-bot.md) can send spoken replies as voice messages and speak in a
voice channel (it never listens there). These need the voice add-on too.

## Where voice models are kept

Voice models, once installed, live in `%LOCALAPPDATA%\STAR\voice-models`, separate from your other STAR files.
Settings → **Where STAR generates** → **Voice** is set to **This PC (your GPU)**. The **STAR Brains (servers)**
choice is shown but not available for voice yet.
