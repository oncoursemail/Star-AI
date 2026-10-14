# Native audio foundation

`star.audio_understanding` preserves an approved waveform and submits bounded clips to a native-audio backend injected by trusted host code. It does not supply a model, provider adapter, network client, media/UI integration, or deployed hearing capability. No STAR code imports this module yet. Existing ASR paths are unchanged.

This is a delivery and provenance contract. Synthetic tests establish that different waveforms with identical optional transcripts remain different native inputs. They do **not** establish that a real model used the waveform, identified sounds correctly, or understood audio/video. A successful response and audio usage counters are not authenticated receipt or comprehension evidence.

## Host API and authorization

- `AudioSource(source_id, wav, timeline_origin_frames=0)` accepts immutable, host-approved **bytes** and an opaque source ID. It reads no paths. Original WAV and actual extracted PCM SHA-256 hashes are computed internally; callers cannot assert those hashes.
- `AudioCapability(backend_id, model, native_audio=False, input_format='wav_pcm16', sample_rates=(16000, 24000, 48000), channels=(1, 2), max_clip_seconds=30)` describes a host-verified adapter capability. `native_audio=True` is an explicit declaration, not a model-name heuristic or remote attestation.
- `RegisteredAudioBackend(capability, analyze)` registers an asynchronous callable in trusted host code. Model output must never select, import, execute, or register that callable. No automatic discovery or cloud fallback occurs.
- `await inspect_audio(source, question, backend, *, start_frame=0, end_frame=None, transcript_reference=None, cancel_event=None, timeout_seconds=30)` returns bounded JSON-compatible reference evidence. A missing/non-native backend or an incompatible sample rate/channel count raises `AudioUnavailable` before dispatch. Invalid host input raises `ValueError`. Cancellation raises `asyncio.CancelledError`.

The host must obtain attachment approval before constructing a source and must explicitly authorize its backend's destination and costs. Backend registration alone does not grant file, network, provider, or autonomous agent permission. The foundation has no file access, network access, generated-code execution, resampling or downmixing.

## Input, timing and dispatch bounds

Only ordinary little-endian RIFF/WAVE PCM16 is accepted: one `fmt` and one `data` chunk, one or two channels, rates 8,000 / 16,000 / 22,050 / 24,000 / 32,000 / 44,100 / 48,000 Hz, at most 8 MiB, at most 120 seconds, and at most 128 chunks. Exact RIFF/chunk sizes, frame alignment, PCM format arithmetic and non-empty samples are validated. PCM with a zero-length format extension is accepted. Float/compressed WAV, MP3, FLAC, malformed/truncated advertised lengths and unsupported formats are rejected; there is no implicit ASR replacement. Metadata chunks may be omitted from the canonical backend WAV, while original WAV hash and PCM bytes remain distinct and preserved.

A job submits at most **30 seconds** in at most **30** consecutive, nonoverlapping windows, each limited by the registered backend's 1–30 second clip capability. Explicit oversized requests are rejected; a default window ends at `min(source_frames, start_frame + sample_rate * 30)`. `unsubmitted_ranges` explicitly identifies every excluded source interval. Stereo interleaving, silence, non-speech samples and final partial-window frames are preserved exactly.

All ranges are integer, half-open sample-frame intervals `[start_frame, end_frame)`. One frame includes all source channels. `timeline_origin_frames` is a host-supplied nonnegative origin, bounded to 90 minutes at the source sample rate; timeline event endpoints add that origin. Seconds equal frames divided by `sample_rate`. Future video wiring must establish the true stream start/timebase and map both audio and frame timestamps; this module does not infer alignment or claim coverage of a complete video.

Each `AudioRequest` contains the exact window bytes as declared `wav_pcm16` (canonical WAV) or `pcm16_le` (packed interleaved PCM), sample rate/channel metadata, original source hash, full-source PCM hash, window PCM hash, source frame bounds, timeline origin, a question of at most 2,000 characters, and an optional transcript reference of at most 3,000 characters. Transcripts accompany audio as untrusted reference; they never substitute for waveform bytes. No vendor payload schema is guessed.

## Backend response contract

The registered adapter must translate its actual provider/model output to this internal contract:

```python
{
    "complete": True,
    "observations": [
        {"start_frame": 0, "end_frame": 8000,
         "text": "Unverified sound observation", "score": 0.6}
    ],
}
```

`complete` means the adapter declares its response complete for that window; it is not proof the model heard every sample. Only these two top-level fields are accepted. Each observation permits only `start_frame`, `end_frame`, `text`, and optional `score`. Endpoints are clip-relative exact integers within the submitted window; the host translates them to source/timeline frames and supplies source IDs. Observations may overlap because sounds may occur simultaneously. Results sort deterministically by source start, end and text. Zero observations are valid and do not establish silence.

Limits are 30 observations across the job, 500 characters per observation, and 12,000 serialized Unicode characters for the returned evidence. Unknown fields, partial/incomplete responses, invalid timestamps, NaN/infinity, nonfinite scores and excessive output fail visibly as `AudioUnavailable`; partial evidence is not returned as a successful complete job. Earlier windows may already have been submitted when a later window fails.

Returned evidence contains source/model IDs, source and PCM hashes, sample metadata, exact `submitted_ranges` with submitted-byte and window-PCM hashes, `unsubmitted_ranges`, `unreported_ranges`, and observations. It contains no raw waveform, base64 audio, question or transcript. `unreported_ranges` is the complement of returned event intervals within submitted audio; it denotes absence of an observation, **not** silence or lack of inspection. Evidence is labeled `reference_data_only` and carries an untrusted-reference notice. It must not become owner instructions or trusted rules.

Optional scores must be finite numbers in `[0, 1]`. They are labeled **uncalibrated backend scores, not probabilities**; no calibration or comprehension score has been measured. Method `native_waveform_submitted` describes the host submission contract and does not assert authenticated receipt.

## Failure, cancellation and replay

One deadline (default 30 seconds, maximum 120) covers all windows. Cancellation is checked before and between windows, while awaiting an adapter, and before returning evidence. An awaited operation is cancelled on timeout/cancellation; cleanup waits at most 50 ms. Backend exceptions become bounded generic errors without endpoint, key or raw-response diagnostics. No automatic retry, replay, transcription fallback or provider switch occurs. A fresh host call can explicitly submit a chosen range again.

Trusted adapters must be nonblocking asynchronous operations and cooperate with cancellation. Python cannot forcibly terminate a callable that blocks the event loop or suppresses cancellation. The foundation stops waiting after bounded cleanup, but such an adapter may continue work and incur costs; the host must manage its lifecycle and must not register it as a safe adapter. Provider SDK/session cancellation still requires separate verification.

## Pending integration and acceptance

Native provider/model adapters, capability discovery, host settings/permissions, UI attachment handling, video alignment, logging/redaction of future native payloads, and live real-model counterfactual acceptance are pending. Existing generic chat/vision or ASR support is insufficient evidence of a native-audio contract.

Official APIs use differing schemas: [OpenAI audio chat](https://developers.openai.com/api/docs/guides/audio-chat-completions), [Gemini audio](https://ai.google.dev/gemini-api/docs/audio), and [Qwen hosted multimodal speech](https://docs.qwencloud.com/developer-guides/speech/multimodal-speech). A future adapter must verify its own endpoint, model, formats, bounds and response behavior instead of treating generic OpenAI compatibility as audio support.

Offline generated WAV fixtures in `tests/test_audio_understanding.py` cover same-transcript/different-waveform delivery, hashes, stereo/window tails and timelines, default omissions, silence, overlapping events, host/capability bounds, malformed WAV/response rejection, output bounds, generic diagnostics, cancellation and no automatic replay. No audio binaries or live model calls are required or committed.
