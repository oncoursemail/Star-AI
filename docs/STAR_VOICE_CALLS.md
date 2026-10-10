# STAR voice calls

Status: working backend prototype (branch `star/voice-call-20261010`). You speak, Star answers out loud in a warm
voice, and she stops talking when you talk over her. There is no call screen in the app yet: this document defines
the bridge actions and events that screen needs, so it can be wired afterwards.

What has been run and what has not:

| Item | Status |
|---|---|
| Whole pipeline from recorded audio files against the real STAR Server, including an interruption | Run, measured (section 7) |
| Turn logic, sentence chunking, cancellation, bridge, model download | Unit tests with fakes (`tests/test_voice_*.py`) |
| Loudspeaker echo handling | Simulation only (Star's audio mixed back into the fake microphone) |
| A real microphone and real loudspeakers or headphones | **Not tested.** The launcher exists; nobody has spoken into it yet |
| The call screen in the React app | Not built (bridge contract below) |

## 1. How a call works

```
microphone (16 kHz, 32 ms frames)
   -> voice activity (Silero VAD)            is someone talking?
   -> end of turn (pause + Smart Turn model)  have they finished?
   -> speech to text (faster-whisper)         starts during the pause, so it is usually ready in time
   -> brain (STAR Server, streaming)          short spoken-style reply, warm persona
   -> sentence chunker                        first sentence goes to the voice the moment it is complete
   -> text to speech (Kokoro)                 one sentence at a time
   -> speaker
```

- **Speech starts on the first sentence.** The server produces text at about speaking pace, so waiting for the whole
  reply would add many seconds. The voice prompt asks Star to open with two to five words ("Oh, well done.") so the
  first audio does not wait for a long sentence.
- **Interruption (barge-in).** If you speak for about 0.3 s while Star is talking, playback stops within one audio
  block, the request to the server is closed, and queued sentences are dropped. Only the words that were actually
  played are kept in the conversation history, so Star knows what you did and did not hear.
- **Thinking out loud.** If you pause and then carry on before Star has said anything, the half-started reply is
  cancelled and both parts of what you said are answered as one turn.
- **End of turn.** After a 0.26 s pause the transcript is started and the Smart Turn model judges whether you sounded
  finished. If yes, the turn ends once the silence reaches 0.6 s (people pause about that long between two
  sentences; ending earlier made Star start answers that then had to be thrown away). If not, the model is asked
  again every 0.19 s while the bar it must clear falls from 0.5 to 0.25; after 2 s of silence the turn ends
  regardless. Without the model (`endpointer: silence`) a turn ends after 0.64 s of silence.
- **Prompt cache.** The system prompt is short and never changes, and history is trimmed in large blocks instead of
  sliding every turn, so the server re-reads as little as possible before each reply. This matters: on the CPU
  server reading the prompt is the slowest part of a turn (section 7).

## 2. Code map

Everything lives in `star/voice/`. The first group is pure Python and always importable; the second group needs the
optional packages.

| Module | What it does |
|---|---|
| `chunker.py` | Streamed model text to speakable sentences; strips markdown, emoji, links, code |
| `turn.py` | `TurnDetector` (start, pause, resume, end of turn, barge-in rules) and `EchoGate` |
| `call.py` | `CallSession`: wires the stages, runs replies on worker threads, handles interruption and history |
| `brain.py` | `ServerBrain`: cancellable streaming client; `ScriptedBrain` for offline tests |
| `persona.py` | The voice system prompt (warm, caring, short spoken sentences) |
| `metrics.py` | `TurnMetrics` and the latency table |
| `settings.py` | `VoiceSettings`: validated settings (voice id, engines, timings) |
| `filecall.py` | Scripted calls from WAV files with a real-time virtual microphone and speaker |
| `bridge.py` | UI actions and events (section 5) |
| `setup_models.py` | Downloads the four small model files, checked by size and SHA-256 |
| `engines.py` | Silero VAD, Smart Turn, faster-whisper, Kokoro; the registries where new engines plug in |
| `devices.py` | Real microphone and speaker (`sounddevice`) |
| `runtime.py` | Loads engines once, warms them up, builds a session |
| `__main__.py` | `python -m star.voice setup | call | file-call | make-test-audio | say | devices` |

Adding an engine: write a class with `synthesize(text) -> iterable of (pcm16_bytes, sample_rate)` (text to speech) or
`transcribe(pcm16_bytes, sample_rate) -> str` (speech to text), add one line to `make_tts` / `make_asr` in
`engines.py`, and add its name to `TTS_ENGINES` / `ASR_ENGINES` in `settings.py`. Streaming voices simply yield
several chunks; the session already plays them as they arrive and can cancel between chunks.

## 3. Setup

```
pip install -r requirements.txt -r requirements-voice.txt
python -m star.voice setup          # Kokoro, Silero VAD, Smart Turn: about 365 MB, verified by SHA-256
```

Environment variables:

| Variable | Meaning |
|---|---|
| `STAR_SERVER_URL` | Brain address, for example `http://10.17.0.146:8080/v1`. Must be an IP on your own network ending in `/v1` |
| `STAR_SERVER_API_KEY` | Brain key. Only ever sent in the Authorization header; never logged or printed |
| `STAR_VOICE_MODEL` | Model name on the server (default `star-fast`) |
| `STAR_VOICE_MODELS` | Folder with the voice model files (default `%LOCALAPPDATA%\STAR\voice-models`) |
| `STAR_VOICE_<SETTING>` | Any field of `VoiceSettings`, for example `STAR_VOICE_VOICE=blend-heart-nicole` |

The speech-recognition model (`small.en`, about 460 MB) is downloaded by faster-whisper from Hugging Face the first
time it is used.

**GPU (NVIDIA, optional).** Replace `onnxruntime` with `onnxruntime-gpu[cuda,cudnn]==1.26.*`. Two traps, both
handled or documented here:

1. `kokoro-onnx` and `faster-whisper` depend on the CPU `onnxruntime` wheel, which overwrites the GPU build because
   both install the same import package. Uninstall `onnxruntime` and reinstall `onnxruntime-gpu`, or with uv add
   `override-dependencies = ["onnxruntime ; sys_platform == 'never'"]` (see `voice-lab/call-env/pyproject.toml`).
2. cuDNN 9 loads sub-libraries by name at run time. If the wheel's `nvidia/*/bin` folders are not on the DLL search
   path, the first convolution fails with "Failed to initialize CUDNN Frontend" and onnxruntime silently falls back
   to the CPU. `engines.add_nvidia_dll_dirs()` adds those folders before any model is loaded.

Measured on the RTX 3060 Ti: Kokoro about 14 times faster than real time on the GPU, about 2.5 times on the CPU.

## 4. Running it

Double-click launchers (real microphone; **not yet tested with a real microphone**):

- `scripts\star-voice-call.cmd`: generic. First start creates `.venv-voice` and downloads models (CPU build).
- `voice-lab\star-voice-call.cmd` (outside the repository, on the owner's PC): uses the GPU environment and models
  that are already set up there, so it starts in a few seconds.

Both read the key from `%USERPROFILE%\.star\server_api_key` without showing it. Use headphones, or pass
`--output speakers` to turn the echo gate on. Pick a voice with `--voice <id>` (ids as on the audition page).

Without a person (this is how the pipeline was tested):

```
python -m star.voice make-test-audio --out call-tests          # synthesises five caller questions + scenario.json
python -m star.voice file-call --scenario call-tests/scenario.json --out call-tests/run1 --verify
python -m star.voice file-call --scenario call-tests/scenario.json --offline-brain      # no server needed
python -m star.voice file-call --scenario call-tests/scenario.json --echo-db -15 --output speakers
```

`file-call` plays the questions into a virtual microphone in real time, lets Star answer through a virtual speaker,
talks over her in the middle of one answer, prints the latency table, and saves `user.wav`, `star.wav` (what was
audible, cut where the interruption cut it), `turns.json` and `latency.txt`. `--verify` transcribes Star's recorded
audio back to text as a sanity check that real speech came out.

## 5. Bridge contract for the call screen

The actions are registered in `star/react_shell.py` (`VOICE_ACTIONS`) and handled by `star/voice/bridge.py`. They use
the existing `starBridge.invoke(JSON)` call and answer immediately with `{"ok": true, "data": ...}` or
`{"ok": false, "error": "..."}`. Call events arrive on the existing `starBridge.event` signal as
`{"requestId": <callId>, "kind": "voice", "data": {...}}`, where `callId` is the `requestId` of the `voiceStartCall`
request.

### Actions

| Action | Payload | Immediate `data` |
|---|---|---|
| `voiceStatus` | none | `{available, missingPackages[], missingModels[], serverConfigured, inCall, callId, state, muted}` |
| `voiceGetSettings` | none | `{settings: VoiceSettings, choices: {asr_model[], endpointer[], output[]}}` |
| `voiceSaveSettings` | `{settings: {...partial}}` | `{settings}` after validation; stored in `voice.json` in the app data folder |
| `voiceListVoices` | none | `{voices: [{engine, id, label, recipe}]}` (ids match the audition page) |
| `voiceListDevices` | none | `{devices: [{index, kind: "input"|"output", name, default}]}` |
| `voiceStartCall` | `{settings?: {...partial}}` | `{callId, settings}`; loading and the call run in the background |
| `voiceStopCall` | none | `{stopped: true|false}`; an `ended` event follows |
| `voiceInterrupt` | none | `{interrupted: true}` (a "stop talking" button) |
| `voiceSetMuted` | `{muted: true|false}` | `{muted}`; while muted the microphone is ignored |
| `voicePreviewVoice` | `{voice?, speed?, text?}` | `{previewing}`; speaks one sample line when no call is active |

Only one call can exist. `voiceStartCall` during a call returns an error. Invalid settings are rejected before
anything starts.

### Events (`data.type`)

| Type | Fields | When |
|---|---|---|
| `state` | `state`: `starting`, `listening`, `user_speaking`, `thinking`, `speaking`, `ended` | Every change. Drive the main visual from this |
| `progress` | `message` | While models load during `starting` (first call takes a few seconds) |
| `level` | `mic`, `speaker` (0 to 1) | About 12 times a second, for level meters or an orb |
| `speech_started` | `barge_in` (true if Star was cut off) | The user began to talk |
| `partial_transcript` | `text` | Live transcript while the user talks (about once a second) |
| `final_transcript` | `turn`, `text` | The user's finished turn (empty text = nothing understood) |
| `assistant_delta` | `turn`, `text` | Raw text pieces from the brain as they stream |
| `assistant_sentence` | `turn`, `text` | A sentence has been synthesised and queued to play: use for captions |
| `interrupted` | `turn`, `reason` (`barge_in`, `user_kept_talking`, `button`, `call_ended`), `heard_text` | A reply was cut; `heard_text` is what was audible |
| `turn_metrics` | `turn`, `user_text`, `reply_text`, `stages{...}`, `interrupted`, ... | After every turn; `stages` holds the latency breakdown in seconds |
| `error` | `message` | Something failed (server unreachable, wrong key, model file missing). The call keeps listening when it can |
| `preview_done` | `voice` | A voice preview finished |
| `ended` | `turns[]` | The call is over; includes all turn metrics |

State flow in a normal turn: `listening -> user_speaking -> thinking -> speaking -> listening`. With an interruption:
`speaking -> user_speaking -> thinking -> speaking`. Finished turns are also written to the active chat (user text and
the words Star actually spoke), so a call appears in the conversation history like typed messages.

### Settings (`VoiceSettings`)

| Field | Default | Notes |
|---|---|---|
| `tts_engine` | `kokoro` | Only Kokoro is wired in today |
| `voice` | `heart` | Audition-page id (`heart`, `blend-heart-nicole`, ...) or a custom blend `af_heart:0.7+af_nicole:0.3` |
| `speed` | `0.92` | 0.6 to 1.4; slightly under 1 reads calmer |
| `asr_engine`, `asr_model` | `faster-whisper`, `auto` | `auto` = `small.en` on an NVIDIA GPU, `base.en` on the CPU (section 6) |
| `asr_prompt` | names such as Star, Roblox, RemoteEvent | Spellings the transcript should prefer |
| `device` | `auto` | `auto`, `cuda` or `cpu` |
| `vad`, `endpointer` | `silero`, `smart-turn` | `endpointer: silence` uses the plain silence timer |
| `output` | `headphones` | `speakers` turns the echo gate on |
| `min_end_silence_ms` | 608 | Shortest wait after you stop talking, even when the end-of-turn model is sure |
| `end_silence_ms`, `max_silence_ms`, `barge_in_ms` | 640, 2000, 288 | Turn-taking patience (silence timer without the model; hard limit; speech needed to interrupt) |
| `max_reply_tokens` | 220 | Upper bound for one spoken reply |
| `partial_transcripts` | true | Live transcript events |
| `input_device`, `output_device` | empty | Device name or index from `voiceListDevices`; empty = system default |

### Suggested screen behaviour

- Before showing a call button, call `voiceStatus`. If `available` is false, show what is missing instead
  (`missingPackages`, `missingModels`, or "STAR Server not set up").
- On `voiceStartCall`, show "getting ready" with the `progress` messages until `state: listening`.
- Show the live `partial_transcript`, replace it with `final_transcript`, then show Star's `assistant_sentence`
  captions. On `interrupted`, trim the caption to `heard_text`.
- A mute toggle (`voiceSetMuted`), a "stop talking" button (`voiceInterrupt`) and a hang-up button (`voiceStopCall`).
- Voice picker: `voiceListVoices` + `voicePreviewVoice`, saved through `voiceSaveSettings`.

## 6. Speech recognition choice

<!-- ASR -->

## 7. Measured latency

<!-- LATENCY -->

## 8. Hand-off notes and open problems

- **Server provider.** `star/providers.py` and `Settings` are being changed on another branch (`star_server`
  provider). Until that lands, `ServerBrain.from_env()` reads `STAR_SERVER_URL` and `STAR_SERVER_API_KEY`. After it
  lands, build the brain from `connection_for(settings)` in `runtime.make_brain` (one function); `validate_server_url`
  in `brain.py` can then be replaced by the provider's own LAN check. In the packaged app nothing sets those two
  variables yet, so `voiceStatus` reports `serverConfigured: false` there.
- **Real microphone untested.** Device opening, sample-rate negotiation on unusual audio hardware, and how the
  thresholds feel with a human voice all still need a person. `Microphone` asks PortAudio for 16 kHz mono directly.
- **Echo.** With loudspeakers the microphone hears Star. The energy echo gate (`output: speakers`) stops her
  interrupting herself in simulation, but it is not echo cancellation: the user has to speak clearly louder than the
  echo, and it has not been tried in a real room. Proper fix: WebRTC AEC3 in front of the VAD (for example the
  `pywebrtc-audio` package), or headphones.
- **Packaging.** The optional packages and models are not part of the Windows installer. `voiceStatus` reports them
  as missing rather than failing.
- **Other voices.** Only Kokoro is wired into calls. The audition page also has Chatterbox, Qwen3-TTS, Pocket TTS and
  Supertonic samples; adding one is an `engines.py` class (section 2). See `docs/research/voice.md` in the project
  folder for the measurements behind the recommendations.
- **False end of turn between sentences.** Smart Turn sometimes ends the turn after the first of two sentences; the
  session cancels and merges, at the cost of one abandoned request to the server.
- **Server speed dominates.** Every other stage adds well under a second in total; the brain's first token and its
  tokens per second decide how the call feels.
