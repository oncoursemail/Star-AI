"""Tiny PCM16 helpers in pure Python (the core voice modules must not need numpy)."""
from __future__ import annotations

import array
import math
import sys

SAMPLE_RATE = 16000          # microphone / VAD / ASR rate
FRAME_SAMPLES = 512          # Silero VAD frame at 16 kHz
FRAME_BYTES = FRAME_SAMPLES * 2
FRAME_MS = FRAME_SAMPLES * 1000 // SAMPLE_RATE   # 32 ms


def samples(pcm: bytes) -> array.array:
    data = array.array("h")
    data.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        data.byteswap()
    return data


def rms(pcm: bytes) -> float:
    """Root-mean-square level of little-endian PCM16, scaled to 0..1."""
    data = samples(pcm)
    if not data:
        return 0.0
    return math.sqrt(sum(s * s for s in data) / len(data)) / 32768.0


def seconds(pcm: bytes, sample_rate: int) -> float:
    return len(pcm) / 2 / sample_rate


def silence(duration: float, sample_rate: int = SAMPLE_RATE) -> bytes:
    return b"\x00\x00" * int(duration * sample_rate)


def frames(pcm: bytes, frame_bytes: int = FRAME_BYTES):
    """Yield fixed-size frames; the last one is zero-padded."""
    for start in range(0, len(pcm), frame_bytes):
        chunk = pcm[start:start + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk += b"\x00" * (frame_bytes - len(chunk))
        yield chunk
