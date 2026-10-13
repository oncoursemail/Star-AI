"""STAR Discord chat, opt-in speech, and opt-in transcription services.

This service never dispatches desktop tools and never writes conversation memory.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from .audio import decode_attachment, ffmpeg_path, synthesize_pcm, validate_attachment, voice_message
from .brain import DiscordBrain
from .core import AccessPolicy, SessionMemory, MAX_AUDIO_TEXT, MAX_PROMPT, clean_text, session_key


@dataclass(frozen=True)
class ResearchAnswer:
    text: str
    sources: tuple[dict, ...]


@dataclass(frozen=True)
class SpokenAnswer:
    transcript: str
    text: str
    audio: object


class DiscordService:
    def __init__(self, policy: AccessPolicy, *, brain=None, memory: SessionMemory | None = None,
                 ffmpeg_dir: str = "", searcher=None) -> None:
        self.policy = policy
        self.brain = brain or DiscordBrain()
        self.memory = memory or SessionMemory()
        self.ffmpeg_dir = ffmpeg_dir
        self._searcher = searcher
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

    async def _lock_brain(self) -> None:
        # Don't queue a wall of interactions while a local model is busy.
        try:
            await asyncio.wait_for(self._brain_lock.acquire(), timeout=3.0)
        except asyncio.TimeoutError as exc:
            raise ValueError("STAR is busy with another request. Try again shortly.") from exc

    async def ask(self, key: tuple, prompt: str) -> str:
        question = clean_text(prompt, max_chars=MAX_PROMPT)
        if not question:
            raise ValueError("Ask STAR a question")
        await self._lock_brain()
        try:
            history = self.memory.history(key)
            answer = await self.brain.reply(question, history)
            self.memory.remember(key, question, answer)
            return answer
        finally:
            self._brain_lock.release()

    async def inspect_image(self, key: tuple, prompt: str, jpeg: bytes, *, vision=None) -> str:
        """Owner DM image analysis only; normalized bytes are never persisted."""
        if not isinstance(key, tuple) or len(key) != 3 or key[0] is not None:
            raise PermissionError("Image analysis is owner-DM only")
        self.policy.require(key[2], None, key[1])
        from .dm_mode import DiscordVision
        await self._lock_brain()
        try:
            answer = await (vision or DiscordVision()).reply(prompt, jpeg)
            # Temporary context stores only the question and the reply, never an
            # image file, remote URL, original attachment or image bytes.
            self.memory.remember(key, "[Image discussed] " + prompt[:300], answer)
            return answer
        finally:
            self._brain_lock.release()

    async def propose_dm_lesson(self, key: tuple, *, message_id: int,
                                text: str, kind: str, project: str, home=None):
        """An explicit remember request creates a reviewable local candidate.

        Even a Discord owner cannot skip desktop lesson approval or use a
        Discord conversation to grant agent or Roblox permissions.
        """
        if not isinstance(key, tuple) or len(key) != 3 or key[0] is not None:
            raise PermissionError("Lesson capture is owner-DM only")
        self.policy.require(key[2], None, key[1])
        from ..desktop_core import app_data
        from .dm_mode import capture_discord_lesson_candidate
        return await asyncio.to_thread(
            capture_discord_lesson_candidate,
            owner_id=key[2], allowed_owners=self.policy.owners,
            message_id=message_id, text=text, kind=kind, project=project,
            home=home if home is not None else app_data(),
        )

    async def research(self, key: tuple, question: str) -> ResearchAnswer:
        """Optional cited web search; only existing STAR-configured search providers.

        Source URLs originate from the fixed Brave/Tavily gateway and must never
        grant filesystem, GitHub or Studio permissions to the bot.
        """
        from ..web_search import search_web, source_context
        query = clean_text(question, max_chars=600)
        if not query:
            raise ValueError("Give STAR a research question")
        await self._lock_brain()
        try:
            searcher = self._searcher or search_web
            sources = await asyncio.wait_for(searcher(query, limit=5), timeout=25)
            if not sources:
                raise ValueError("The configured search provider returned no usable sources")
            answer = await self.brain.reply(query, self.memory.history(key), evidence=source_context(sources))
            self.memory.remember(key, query, answer)
            return ResearchAnswer(answer, tuple(sources[:5]))
        finally:
            self._brain_lock.release()

    async def converse(self, key: tuple, *, filename: str, content_type: str | None,
                       data: bytes) -> SpokenAnswer:
        """Explicit voice-message question → private transcript + public spoken answer.

        This is turn-based conversation through uploaded audio, not live VC capture.
        The invoking Discord command must check permissions and communicate that
        the generated audio reply will be public before invoking this method.
        """
        transcript = await self.transcribe(filename=filename, content_type=content_type, data=data)
        answer = await self.ask(key, transcript)
        spoken = await self.voice_message(answer[:MAX_AUDIO_TEXT])
        return SpokenAnswer(transcript, answer, spoken)

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
