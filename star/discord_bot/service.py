"""STAR Discord chat, opt-in speech, and opt-in transcription services.

This service never dispatches desktop tools and never writes conversation memory.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .audio import decode_attachment, ffmpeg_path, synthesize_pcm, validate_attachment, voice_message
from .brain import DiscordBrain
from .core import AccessPolicy, SessionMemory, MAX_AUDIO_TEXT, MAX_PROMPT, clean_text, session_key


class DiscordService:
    def __init__(self, policy: AccessPolicy, *, brain=None, memory: SessionMemory | None = None,
                 ffmpeg_dir: str = "") -> None:
        self.policy = policy
        self.brain = brain or DiscordBrain()
        self.memory = memory or SessionMemory()
        self.ffmpeg_dir = ffmpeg_dir
        # One owner conversation at a time to prevent two simultaneous answers from
        # committing out of order. CPU-heavy voice engines have their own locks.
        self._brain_lock = asyncio.Lock()
        self._tts_lock = asyncio.Lock()
        self._asr_lock = asyncio.Lock()
        self._tts = None
        self._asr = None

    def authorized(self, user_id: int, guild_id: int | None, channel_id: int) -> tuple:
        self.policy.require(user_id, guild_id, channel_id)
        return session_key(guild_id, channel_id, user_id)

    async def ask(self, key: tuple, prompt: str) -> str:
        question = clean_text(prompt, max_chars=MAX_PROMPT)
        if not question:
            raise ValueError("Ask STAR a question")
        async with self._brain_lock:
            history = self.memory.history(key)
            answer = await self.brain.reply(question, history)
            self.memory.remember(key, question, answer)
            return answer

    def forget(self, key: tuple) -> None:
        self.memory.forget(key)

    @staticmethod
    def _voice_settings():
        from ..desktop_core import app_data
        from ..voice.settings import VoiceSettings
        path = app_data() / "voice.json"
        if not path.is_file():
            return VoiceSettings().validate()
        try:
            return VoiceSettings.from_mapping(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return VoiceSettings().validate()

    def _speech(self, text: str) -> tuple[bytes, int]:
        from ..voice.engines import make_tts
        if self._tts is None:
            settings = self._voice_settings()
            self._tts = make_tts(settings.tts_engine, settings.voice, settings.speed, settings.device,
                                 lang=settings.tts_lang, gap_ms=settings.sentence_gap_ms,
                                 pitch_semitones=settings.pitch_semitones)
        return synthesize_pcm(self._tts, text)

    async def speak_pcm(self, text: str) -> tuple[bytes, int]:
        if len(text) > MAX_AUDIO_TEXT:
            raise ValueError("Discord speech is limited to 500 characters")
        async with self._tts_lock:
            return await asyncio.to_thread(self._speech, text)

    async def voice_message(self, text: str):
        pcm, rate = await self.speak_pcm(text)
        return await asyncio.to_thread(voice_message, pcm, rate, executable=ffmpeg_path(self.ffmpeg_dir))

    def _transcribe(self, pcm: bytes) -> str:
        from ..voice.engines import make_asr
        if self._asr is None:
            config = self._voice_settings()
            self._asr = make_asr(config.asr_engine, config.asr_model, config.device, config.asr_prompt)
        text = self._asr.transcribe(pcm, 16000)
        return clean_text(text, max_chars=MAX_PROMPT)

    async def transcribe(self, *, filename: str, content_type: str | None, data: bytes) -> str:
        validate_attachment(filename, content_type, len(data))
        async with self._asr_lock:
            pcm = await asyncio.to_thread(decode_attachment, data, executable=ffmpeg_path(self.ffmpeg_dir))
            transcript = await asyncio.to_thread(self._transcribe, pcm)
        if not transcript:
            raise ValueError("No intelligible speech was detected in the attachment")
        return transcript
