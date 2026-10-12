"""Bounded native waveform preparation; backends are injected by trusted host code.

No provider discovery, ASR fallback, file/network access, or deployed model is supplied.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import re
import struct
from dataclasses import dataclass, field
from typing import Awaitable, Callable

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_SECONDS = 120
MAX_JOB_SECONDS = 30
MAX_WINDOWS = 30
MAX_OUTPUT_CHARS = 12000
RATES = frozenset({8000, 16000, 22050, 24000, 32000, 44100, 48000})
NOTICE = 'Untrusted native-audio reference observations; verify against the original waveform.'
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,119}')
_SOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}')


class AudioUnavailable(RuntimeError):
    """Native audio cannot run under the host's registered capability."""


def _integer(value, low: int, high: int, name: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Invalid {name}')
    return value


def _cancel(flag) -> None:
    if flag is not None and flag.is_set():
        raise asyncio.CancelledError('Native audio inspection cancelled')


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pcm(raw: bytes) -> tuple[bytes, int, int]:
    if type(raw) is not bytes or not 44 <= len(raw) <= MAX_SOURCE_BYTES:
        raise ValueError('WAV bytes are missing or exceed 8 MiB')
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE' or struct.unpack_from('<I', raw, 4)[0] != len(raw) - 8:
        raise ValueError('Malformed RIFF/WAVE length or signature')
    fmt, pcm, position, chunks = None, None, 12, 0
    while position < len(raw):
        chunks += 1
        if chunks > 128:
            raise ValueError('Too many WAV chunks')
        if position + 8 > len(raw):
            raise ValueError('Truncated WAV chunk header')
        tag, size = raw[position:position + 4], struct.unpack_from('<I', raw, position + 4)[0]
        start, end = position + 8, position + 8 + size
        if end + (size % 2) > len(raw):
            raise ValueError('Truncated WAV chunk payload')
        if tag == b'fmt ':
            if fmt is not None or size not in (16, 18) or (size == 18 and raw[end - 2:end] != b'\0\0'):
                raise ValueError('Unsupported or duplicate WAV format')
            fmt = struct.unpack_from('<HHIIHH', raw, start)
        elif tag == b'data':
            if pcm is not None or fmt is None:
                raise ValueError('Missing WAV format or duplicate data')
            pcm = raw[start:end]
        position = end + (size % 2)
    if fmt is None or pcm is None:
        raise ValueError('Missing WAV format or data')
    encoding, channels, rate, byte_rate, align, bits = fmt
    if encoding != 1 or bits != 16 or channels not in (1, 2) or rate not in RATES:
        raise ValueError('Use PCM16 WAV, 1–2 channels, and an explicitly supported 8–48 kHz rate')
    if align != channels * 2 or byte_rate != rate * align or not pcm or len(pcm) % align:
        raise ValueError('Malformed PCM frame length or format arithmetic')
    if len(pcm) // align > rate * MAX_SOURCE_SECONDS:
        raise ValueError('WAV duration exceeds 120 seconds')
    return pcm, rate, channels


@dataclass(frozen=True)
class AudioSource:
    """Construct only from host-approved bytes; provenance is computed, never asserted."""
    source_id: str
    wav: bytes = field(repr=False)
    timeline_origin_frames: int = 0
    pcm: bytes = field(init=False, repr=False)
    sample_rate: int = field(init=False)
    channels: int = field(init=False)
    frames: int = field(init=False)
    source_sha256: str = field(init=False)
    waveform_sha256: str = field(init=False)

    def __post_init__(self):
        if not isinstance(self.source_id, str) or not _SOURCE_ID.fullmatch(self.source_id):
            raise ValueError('Invalid opaque audio source ID')
        pcm, rate, channels = _pcm(self.wav)
        _integer(self.timeline_origin_frames, 0, rate * 90 * 60, 'timeline origin')
        for key, value in {'pcm': pcm, 'sample_rate': rate, 'channels': channels,
                           'frames': len(pcm) // (channels * 2), 'source_sha256': _hash(self.wav),
                           'waveform_sha256': _hash(pcm)}.items():
            object.__setattr__(self, key, value)


@dataclass(frozen=True)
class AudioCapability:
    """Host declaration, not a model-name heuristic or proof of remote comprehension."""
    backend_id: str
    model: str
    native_audio: bool = False
    input_format: str = 'wav_pcm16'
    sample_rates: tuple[int, ...] = (16000, 24000, 48000)
    channels: tuple[int, ...] = (1, 2)
    max_clip_seconds: int = 30

    def __post_init__(self):
        if any(not isinstance(x, str) or not _ID.fullmatch(x) for x in (self.backend_id, self.model)):
            raise ValueError('Invalid registered backend or model ID')
        if type(self.native_audio) is not bool or self.input_format not in ('wav_pcm16', 'pcm16_le'):
            raise ValueError('Invalid native audio capability or packed format')
        if (type(self.sample_rates) is not tuple or not self.sample_rates
                or any(type(x) is not int or x not in RATES for x in self.sample_rates)
                or type(self.channels) is not tuple or not self.channels
                or any(type(x) is not int or x not in (1, 2) for x in self.channels)):
            raise ValueError('Invalid native audio rate/channel capability')
        _integer(self.max_clip_seconds, 1, MAX_JOB_SECONDS, 'backend clip limit')


@dataclass(frozen=True)
class AudioRequest:
    source_id: str
    source_sha256: str
    waveform_sha256: str
    clip_waveform_sha256: str
    audio: bytes = field(repr=False)
    input_format: str
    sample_rate: int
    channels: int
    start_frame: int
    end_frame: int
    timeline_origin_frames: int
    question: str
    transcript_reference: str | None = None


@dataclass(frozen=True)
class RegisteredAudioBackend:
    """Only trusted host code registers the callable; nothing imports/executes model code."""
    capability: AudioCapability
    analyze: Callable[[AudioRequest], Awaitable[dict]]


def _wav(pcm: bytes, rate: int, channels: int) -> bytes:
    fmt = struct.pack('<HHIIHH', 1, channels, rate, rate * channels * 2, channels * 2, 16)
    return b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<I', 16) + fmt + b'data' + struct.pack('<I', len(pcm)) + pcm


async def _dispatch(backend, request, cancel_event, deadline):
    _cancel(cancel_event)
    try:
        pending = backend.analyze(request)
    except Exception:
        raise AudioUnavailable('Native audio backend failed') from None
    if not inspect.isawaitable(pending):
        raise AudioUnavailable('Native backend must be asynchronous')
    if isinstance(pending, asyncio.Future) and pending.get_loop() is not asyncio.get_running_loop():
        raise AudioUnavailable('Native backend returned an unavailable async operation')
    task = asyncio.ensure_future(pending)
    try:
        while True:
            _cancel(cancel_event)
            left = deadline - asyncio.get_running_loop().time()
            if left <= 0:
                raise AudioUnavailable('Native audio inspection timed out')
            done, _ = await asyncio.wait({task}, timeout=min(0.05, left))
            if done:
                try:
                    result = await task
                except asyncio.CancelledError:
                    raise
                except Exception:
                    raise AudioUnavailable('Native audio backend failed') from None
                _cancel(cancel_event)
                return result
    finally:
        if not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=0.05)
        # A host adapter must cooperate with cancellation; do not wait forever if it does not.
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())


def _observations(reply, start, end):
    if (type(reply) is not dict or set(reply) != {'complete', 'observations'}
            or reply['complete'] is not True or type(reply['observations']) is not list
            or len(reply['observations']) > 30):
        raise AudioUnavailable('Native backend returned incomplete or malformed observations')
    output = []
    for item in reply['observations']:
        if type(item) is not dict or not {'start_frame', 'end_frame', 'text'} <= set(item) <= {'start_frame', 'end_frame', 'text', 'score'}:
            raise AudioUnavailable('Native backend returned malformed observations')
        try:
            begin = _integer(item['start_frame'], 0, end - start - 1, 'observation start')
            stop = _integer(item['end_frame'], begin + 1, end - start, 'observation end')
            text, score = item['text'], item.get('score')
            if not isinstance(text, str) or not text.strip() or len(text) > 500:
                raise ValueError('Invalid observation text')
            if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError('Invalid uncalibrated score')
        except (ValueError, OverflowError):
            raise AudioUnavailable('Native backend returned invalid observation bounds or values') from None
        output.append({'start_frame': start + begin, 'end_frame': start + stop, 'text': text,
                       'score': score, 'score_status': 'uncalibrated' if score is not None else 'not_reported'})
    return output


def _gaps(start, end, intervals):
    position, gaps = start, []
    for begin, stop in sorted(intervals):
        if begin > position:
            gaps.append([position, begin])
        position = max(position, stop)
    if position < end:
        gaps.append([position, end])
    return gaps


async def inspect_audio(source: AudioSource, question: str, backend: RegisteredAudioBackend | None = None, *,
                        start_frame: int = 0, end_frame: int | None = None,
                        transcript_reference: str | None = None, cancel_event=None, timeout_seconds: float = 30) -> dict:
    """Submit <=30s of exact PCM, once per nonoverlapping window; never retry/fall back.

    Source/backend objects and frame bounds are host inputs, not model-provided paths or registrations.
    """
    _cancel(cancel_event)
    if not isinstance(source, AudioSource):
        raise ValueError('Host-approved audio source required')
    if (not isinstance(backend, RegisteredAudioBackend) or not isinstance(backend.capability, AudioCapability)
            or not callable(backend.analyze) or backend.capability.native_audio is not True):
        raise AudioUnavailable('No host-registered native audio backend is available')
    cap = backend.capability
    if source.sample_rate not in cap.sample_rates or source.channels not in cap.channels:
        raise AudioUnavailable('Registered backend does not support this audio rate or channel count')
    if not isinstance(question, str) or not 1 <= len(question) <= 2000 or not question.strip():
        raise ValueError('Audio question must be 1–2,000 characters')
    if transcript_reference is not None and (not isinstance(transcript_reference, str) or len(transcript_reference) > 3000):
        raise ValueError('Transcript reference exceeds its bound')
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
        raise ValueError('Invalid native audio timeout')
    start = _integer(start_frame, 0, source.frames - 1, 'clip start')
    end = min(source.frames, start + source.sample_rate * MAX_JOB_SECONDS) if end_frame is None else end_frame
    end = _integer(end, start + 1, source.frames, 'clip end')
    if end - start > source.sample_rate * MAX_JOB_SECONDS:
        raise ValueError('Inspect at most 30 seconds per audio job')
    window = source.sample_rate * cap.max_clip_seconds
    if (end - start + window - 1) // window > MAX_WINDOWS:
        raise ValueError('Too many audio windows')
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    submitted, observations = [], []
    for begin in range(start, end, window):
        _cancel(cancel_event)
        stop = min(end, begin + window)
        pcm = source.pcm[begin * source.channels * 2:stop * source.channels * 2]
        packed = _wav(pcm, source.sample_rate, source.channels) if cap.input_format == 'wav_pcm16' else pcm
        request = AudioRequest(source.source_id, source.source_sha256, source.waveform_sha256, _hash(pcm),
                               packed, cap.input_format, source.sample_rate, source.channels, begin, stop,
                               source.timeline_origin_frames, question.strip(), transcript_reference)
        reply = await _dispatch(backend, request, cancel_event, deadline)
        observations.extend(_observations(reply, begin, stop))
        submitted.append({'start_frame': begin, 'end_frame': stop, 'submitted_sha256': _hash(packed),
                          'waveform_sha256': request.clip_waveform_sha256})
        if len(observations) > 30:
            raise AudioUnavailable('Native backend returned too many observations')
    observations.sort(key=lambda x: (x['start_frame'], x['end_frame'], x['text']))
    for item in observations:
        item['source_id'] = source.source_id
        item['timeline_start_frames'] = source.timeline_origin_frames + item['start_frame']
        item['timeline_end_frames'] = source.timeline_origin_frames + item['end_frame']
    result = {'method': 'native_waveform_submitted', 'reference_data_only': True, 'notice': NOTICE,
              'backend': cap.backend_id, 'model': cap.model, 'source_id': source.source_id,
              'source_sha256': source.source_sha256, 'waveform_sha256': source.waveform_sha256,
              'sample_rate': source.sample_rate, 'channels': source.channels, 'source_frames': source.frames,
              'timeline_origin_frames': source.timeline_origin_frames, 'submitted_ranges': submitted,
              'unsubmitted_ranges': _gaps(0, source.frames, [(start, end)]),
              'unreported_ranges': _gaps(start, end, [(x['start_frame'], x['end_frame']) for x in observations]),
              'observations': observations, 'score_meaning': 'Uncalibrated backend score, not a probability.',
              'coverage_meaning': 'Submitted audio is not proof of comprehension; unreported ranges do not imply silence.'}
    if len(json.dumps(result, ensure_ascii=False)) > MAX_OUTPUT_CHARS:
        raise AudioUnavailable('Native audio evidence exceeds the output bound')
    _cancel(cancel_event)
    return result
