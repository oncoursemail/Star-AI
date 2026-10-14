"""Bounded audio I/O for Discord speech, reusing STAR's existing voice engines.

Only an explicit /star command can transcribe audio. Voice channels are never
recorded or captured by this adapter. FFmpeg is invoked without a shell.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import math
import shutil
import subprocess
import wave
from pathlib import Path

from .core import MAX_AUDIO_TEXT, clean_text

MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_AUDIO_SECONDS = 45
_AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3", ".m4a", ".flac", ".webm", ".opus"}


def validate_attachment(name: str, content_type: str | None, size: int) -> None:
    ext = Path(str(name)).suffix.lower()
    kind = str(content_type or "").lower()
    if not (ext in _AUDIO_EXTENSIONS and
            (not kind or kind.startswith("audio/") or (ext == ".webm" and kind == "video/webm"))):
        raise ValueError("Please attach a supported audio file (WAV, OGG, MP3, M4A, FLAC, WebM)")
    if not 0 < size <= MAX_ATTACHMENT_BYTES:
        raise ValueError("Audio must be nonempty and at most 8 MiB")


def ffmpeg_path(folder: str = "") -> str:
    if folder:
        filename = "ffmpeg.exe" if __import__("os").name == "nt" else "ffmpeg"
        path = Path(folder) / filename
        if not path.is_file():
            raise FileNotFoundError(f"FFmpeg executable not found in configured directory: {folder}")
        return str(path)
    result = shutil.which("ffmpeg")
    if not result:
        raise FileNotFoundError("Install FFmpeg or configure its directory in STAR Settings")
    return result


# Input bytes come from a Discord attachment, possibly another user's message. A playlist-style file
# (HLS, concat, ...) would make FFmpeg open the URLs or local files it names; only stdin may be read.
_INPUT_GUARD = ("-protocol_whitelist", "pipe")


def _ffmpeg(arguments: list[str], payload: bytes, *, executable: str) -> bytes:
    if arguments[:2] != ["-i", "pipe:0"]:
        raise ValueError("Discord audio is only read from stdin")
    try:
        result = subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-nostdin", *_INPUT_GUARD,
                                 *arguments],
                                input=payload, capture_output=True, timeout=35, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Audio conversion exceeded its time limit") from exc
    if result.returncode != 0:
        raise ValueError("Discord audio could not be decoded or encoded by FFmpeg")
    return result.stdout


def decode_attachment(blob: bytes, *, executable: str) -> bytes:
    if not 0 < len(blob) <= MAX_ATTACHMENT_BYTES:
        raise ValueError("Audio attachment is empty or too large")
    # The output is capped to 45 seconds of 16 kHz mono PCM, even for long media.
    result = _ffmpeg(["-i", "pipe:0", "-t", str(MAX_AUDIO_SECONDS), "-vn", "-ac", "1", "-ar", "16000",
                      "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"], blob, executable=executable)
    if not result or len(result) > MAX_AUDIO_SECONDS * 16000 * 2 + 4096:
        raise ValueError("Decoded speech is empty or exceeds the duration limit")
    return result


def pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    if rate < 8000 or rate > 96000 or len(pcm) % 2:
        raise ValueError("Invalid PCM16 audio")
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(pcm)
    return out.getvalue()


def synthesize_pcm(tts, text: str) -> tuple[bytes, int]:
    line = clean_text(text, max_chars=MAX_AUDIO_TEXT)
    if not line:
        raise ValueError("Text for speech is empty")
    chunks = []
    rate = None
    total = 0
    for part, chunk_rate in tts.synthesize(line):
        if not isinstance(part, bytes) or not part or len(part) % 2:
            raise RuntimeError("The speech engine generated invalid PCM")
        if rate is None:
            rate = int(chunk_rate)
        if not 8000 <= rate <= 96000 or chunk_rate != rate:
            raise RuntimeError("The speech engine generated inconsistent sample rates")
        total += len(part)
        if total > MAX_AUDIO_SECONDS * rate * 2:
            raise ValueError("Spoken output exceeds the 45-second limit")
        chunks.append(part)
    if not chunks or rate is None:
        raise RuntimeError("The speech engine generated no audio")
    return b"".join(chunks), rate


def waveform(pcm: bytes, rate: int) -> str:
    """Discord preview: base64 bytes sampled at <=10 Hz, at most 256 datapoints."""
    if not pcm or rate <= 0 or len(pcm) % 2:
        raise ValueError("Invalid audio waveform")
    samples = memoryview(pcm).cast("h")
    points = min(256, max(1, math.ceil(len(samples) / rate * 10)))
    heights = bytearray()
    for index in range(points):
        lo = index * len(samples) // points
        hi = max(lo + 1, (index + 1) * len(samples) // points)
        sample = samples[lo:hi]
        energy = sum(int(value) ** 2 for value in sample) / len(sample)
        heights.append(max(0, min(255, round(math.sqrt(energy) / 32768 * 255))))
    return base64.b64encode(heights).decode("ascii")


@dataclass(frozen=True)
class NativeVoiceMessage:
    ogg: bytes
    duration_secs: float
    waveform: str

    def payload(self) -> dict:
        """Discord Message Create: IS_VOICE_MESSAGE 8192 and exactly one audio file."""
        return {"flags": 1 << 13, "attachments": [{"id": 0, "filename": "star.ogg",
                "duration_secs": self.duration_secs, "waveform": self.waveform}]}


def voice_message(pcm: bytes, rate: int, *, executable: str) -> NativeVoiceMessage:
    if not 8000 <= rate <= 96000 or len(pcm) % 2:
        raise ValueError("Invalid PCM16 audio sample rate or frame length")
    seconds = len(pcm) / (2 * rate)
    if not 0 < seconds <= MAX_AUDIO_SECONDS:
        raise ValueError("Audio length exceeds the voice-message limit")
    ogg = _ffmpeg(["-i", "pipe:0", "-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus",
                   "-b:a", "32k", "-application", "voip", "-f", "ogg", "pipe:1"],
                  pcm_to_wav(pcm, rate), executable=executable)
    if not ogg or len(ogg) > MAX_ATTACHMENT_BYTES:
        raise ValueError("Encoded voice message is empty or too large")
    return NativeVoiceMessage(ogg=ogg, duration_secs=round(seconds, 3), waveform=waveform(pcm, rate))


async def post_voice_message(token: str, channel_id: int, payload: NativeVoiceMessage) -> str:
    """Use the documented REST endpoint; discord.py's send() lacks duration/waveform metadata.

    One deliberately bounded retry for 429. This is not an unrestricted HTTP tool.
    """
    import asyncio
    import json
    import aiohttp

    if not token or channel_id < 1:
        raise ValueError("Discord bot token/channel is not configured")
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout, headers={"Authorization": "Bot " + token,
                                                               "User-Agent": "DiscordBot (https://github.com/oncoursemail/Star-AI, 0.9.0)"}) as session:
        for attempt in range(2):
            form = aiohttp.FormData()
            form.add_field("payload_json", json.dumps(payload.payload()))
            form.add_field("files[0]", payload.ogg, filename="star.ogg", content_type="audio/ogg")
            async with session.post(url, data=form) as response:
                if response.status == 429 and attempt == 0:
                    try:
                        retry = float((await response.json()).get("retry_after", 1))
                    except (ValueError, TypeError):
                        retry = 1.0
                    if not 0 <= retry <= 5:
                        raise RuntimeError("Discord rate limit: retry later")
                    await asyncio.sleep(retry)
                    continue
                if response.status >= 400:
                    raise RuntimeError(f"Discord rejected the voice message (HTTP {response.status})")
                data = await response.json()
                return str(data.get("id", ""))
    raise RuntimeError("Discord voice message rate limit: retry later")
