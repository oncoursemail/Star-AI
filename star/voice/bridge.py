"""Bridge between the desktop UI and voice calls: a small set of actions in, a stream of events out.

The React call screen is not built yet (another branch owns the chat UI). This module is the whole backend
contract it needs, documented in docs/STAR_VOICE_CALLS.md:

  actions  voiceStatus, voiceGetSettings, voiceSaveSettings, voiceListVoices, voiceListDevices,
           voiceStartCall, voiceStopCall, voiceInterrupt, voiceSetMuted, voicePreviewVoice
  events   kind "voice", data {type: state | level | speech_started | partial_transcript | final_transcript
           | assistant_delta | assistant_sentence | interrupted | turn_metrics | error | progress | ended}

At most one call exists at a time. Everything slow (loading models, the call itself) runs on a worker
thread; handle() only validates and returns.
"""
from __future__ import annotations

import importlib.util
import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .settings import ASR_MODELS, ENDPOINTERS, OUTPUT_MODES, VoiceSettings

VOICE_ACTIONS = frozenset({
    "voiceStatus", "voiceGetSettings", "voiceSaveSettings", "voiceListVoices", "voiceListDevices",
    "voiceStartCall", "voiceStopCall", "voiceInterrupt", "voiceSetMuted", "voicePreviewVoice",
})
REQUIRED_PACKAGES = {"numpy": "numpy", "onnxruntime": "onnxruntime", "sounddevice": "sounddevice",
                     "faster_whisper": "faster-whisper", "kokoro_onnx": "kokoro-onnx", "httpx": "httpx"}
PREVIEW_LINE = "Hi sweetheart, it's Star. I'm so glad you're here."


class _Factories:
    """The real engines and devices. Tests replace these with fakes."""

    @staticmethod
    def engines(settings: VoiceSettings, progress):
        from .runtime import Engines
        return Engines.load(settings, progress)

    @staticmethod
    def brain(settings: VoiceSettings):
        from .runtime import make_brain
        return make_brain(settings)

    @staticmethod
    def microphone(device):
        from .devices import Microphone
        return Microphone(device=device or None)

    @staticmethod
    def speaker(sample_rate: int, device):
        from .devices import SoundSpeaker
        return SoundSpeaker(sample_rate=sample_rate, device=device or None)

    @staticmethod
    def devices() -> list[dict]:
        from .devices import list_devices
        return list_devices()


class _Call:
    def __init__(self, call_id: str, settings: VoiceSettings) -> None:
        self.id = call_id
        self.settings = settings
        self.stop = threading.Event()
        self.session = None
        self.microphone = None
        self.thread: threading.Thread | None = None


class VoiceBridge:
    def __init__(self, emit: Callable[[str, dict], None], *, settings_path: Path | None = None,
                 save_turn: Callable[[str, str], None] | None = None, factories=None) -> None:
        self._emit_raw = emit                    # emit(call_id, data) -> UI event {kind: "voice", data}
        self._settings_path = settings_path
        self._save_turn = save_turn
        self._factories = factories or _Factories
        self._lock = threading.Lock()
        self._call: _Call | None = None
        self._engines = None
        self._engines_key: tuple | None = None

    # -- helpers ------------------------------------------------------------------------------
    def _emit(self, call_id: str, data: dict) -> None:
        try:
            self._emit_raw(call_id, data)
        except Exception:
            pass

    def _load_settings(self) -> VoiceSettings:
        base = VoiceSettings.from_env()
        if self._settings_path and self._settings_path.is_file():
            try:
                return VoiceSettings.from_mapping(json.loads(self._settings_path.read_text(encoding="utf-8")), base)
            except (ValueError, OSError, TypeError):
                return base                     # a damaged file must not block calls: fall back to defaults
        return base

    def _status(self) -> dict:
        missing = [package for module, package in REQUIRED_PACKAGES.items()
                   if importlib.util.find_spec(module) is None]
        models_missing: list[str] = []
        if not missing:
            from .engines import models_dir
            settings = self._load_settings()
            wanted = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]
            wanted += ["silero_vad.onnx"] if settings.vad == "silero" else []
            wanted += ["smart-turn-v3.2-cpu.onnx"] if settings.endpointer == "smart-turn" else []
            models_missing = [name for name in wanted if not (models_dir() / name).is_file()]
        call = self._call
        from .brain import server_configured
        server = server_configured()      # Settings + keyring, or the environment override; no network
        return {
            "available": not missing and not models_missing,
            "missingPackages": missing,
            "missingModels": models_missing,
            "serverConfigured": server,
            "inCall": call is not None,
            "callId": call.id if call else None,
            "state": (call.session.state if call and call.session else ("starting" if call else "idle")),
            "muted": bool(call and call.session and call.session.muted),
        }

    # -- actions ------------------------------------------------------------------------------
    def handle(self, action: str, body: dict, request_id: str = "") -> dict:
        if action not in VOICE_ACTIONS:
            raise PermissionError("Action not permitted")
        if action == "voiceStatus":
            return self._status()
        if action == "voiceGetSettings":
            return {"settings": asdict(self._load_settings()),
                    "choices": {"asr_model": list(ASR_MODELS), "endpointer": list(ENDPOINTERS),
                                "output": list(OUTPUT_MODES)}}
        if action == "voiceSaveSettings":
            settings = VoiceSettings.from_mapping(body.get("settings") or {}, self._load_settings())
            if self._settings_path is None:
                raise RuntimeError("Voice settings cannot be saved here")
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._settings_path.write_text(json.dumps(asdict(settings), indent=1), encoding="utf-8")
            return {"settings": asdict(settings)}
        if action == "voiceListVoices":
            from .engines import KOKORO_VOICES
            return {"voices": [{"engine": "kokoro", "id": vid, "label": vid.replace("-", " ").title(),
                                "recipe": [[name, weight] for name, weight in recipe]}
                               for vid, recipe in KOKORO_VOICES.items()]}
        if action == "voiceListDevices":
            return {"devices": self._factories.devices()}
        if action == "voiceStartCall":
            return self._start_call(body, request_id)
        if action == "voiceStopCall":
            return {"stopped": self.stop_call()}
        if action == "voicePreviewVoice":
            return self._preview(body, request_id)
        call = self._call
        if call is None or call.session is None:
            raise RuntimeError("No voice call is active")
        if action == "voiceInterrupt":
            call.session.interrupt()
            return {"interrupted": True}
        call.session.set_muted(body.get("muted") is True)          # voiceSetMuted
        return {"muted": call.session.muted}

    def _start_call(self, body: dict, request_id: str) -> dict:
        settings = VoiceSettings.from_mapping(body.get("settings") or {}, self._load_settings())
        with self._lock:
            if self._call is not None:
                raise RuntimeError("A voice call is already running")
            call = _Call(request_id or "voice", settings)
            self._call = call
        call.thread = threading.Thread(target=self._run_call, args=(call,), name="star-voice-call", daemon=True)
        call.thread.start()
        return {"callId": call.id, "settings": asdict(settings)}

    def stop_call(self, wait: float = 5.0) -> bool:
        call = self._call
        if call is None:
            return False
        call.stop.set()
        if call.microphone is not None:
            try:
                call.microphone.close()             # unblocks the frame loop
            except Exception:
                pass
        if call.thread is not None and call.thread is not threading.current_thread():
            call.thread.join(wait)
        return True

    def close(self) -> None:
        self.stop_call(wait=2.0)

    # -- workers ------------------------------------------------------------------------------
    def _get_engines(self, settings: VoiceSettings, progress):
        key = (settings.tts_engine, settings.asr_engine, settings.asr_model, settings.asr_prompt, settings.device,
               settings.vad, settings.endpointer)
        if self._engines is None or self._engines_key != key:
            self._engines = self._factories.engines(settings, progress)
            self._engines_key = key
        tts = self._engines.tts
        if hasattr(tts, "set_voice") and getattr(tts, "voice", None) != settings.voice:
            tts.set_voice(settings.voice)
        if hasattr(tts, "speed"):
            tts.speed = float(settings.speed)
        return self._engines

    def _run_call(self, call: _Call) -> None:
        from .runtime import build_session
        session = None
        try:
            self._emit(call.id, {"type": "state", "state": "starting"})
            engines = self._get_engines(call.settings, lambda m: self._emit(call.id, {"type": "progress", "message": m}))
            if call.stop.is_set():
                return
            brain = self._factories.brain(call.settings)
            speaker = self._factories.speaker(int(getattr(engines.tts, "sample_rate", 24000)),
                                              call.settings.output_device)
            call.microphone = self._factories.microphone(call.settings.input_device)

            def forward(event: dict) -> None:
                self._emit(call.id, event)
                if event.get("type") == "turn_metrics" and self._save_turn and event.get("user_text"):
                    try:
                        self._save_turn(event["user_text"], event.get("reply_text", ""))
                    except Exception:
                        pass              # history is best effort; never break the call for it

            session = build_session(call.settings, engines, speaker, brain=brain, on_event=forward)
            call.session = session
            with call.microphone, speaker:
                session.start()
                for frame in call.microphone:
                    if call.stop.is_set():
                        break
                    session.feed(frame)
        except Exception as exc:
            self._emit(call.id, {"type": "error", "message": f"{str(exc)[:300] or type(exc).__name__}"})
        finally:
            turns = []
            if session is not None:
                try:
                    session.stop()
                    turns = [m.to_dict() for m in session.turns]
                except Exception:
                    pass
            with self._lock:
                if self._call is call:
                    self._call = None
            self._emit(call.id, {"type": "ended", "turns": turns})

    def _preview(self, body: dict, request_id: str) -> dict:
        """Speak one sample line in a voice, outside a call, so the owner can compare voices in the app."""
        if self._call is not None:
            raise RuntimeError("Stop the call before previewing a voice")
        settings = VoiceSettings.from_mapping({k: body[k] for k in ("voice", "speed", "output_device") if k in body},
                                              self._load_settings())
        text = str(body.get("text") or PREVIEW_LINE)[:400]

        def work() -> None:
            try:
                from .engines import make_tts
                tts = self._engines.tts if self._engines is not None else make_tts(
                    settings.tts_engine, settings.voice, settings.speed, settings.device)
                if hasattr(tts, "set_voice"):
                    tts.set_voice(settings.voice)
                speaker = self._factories.speaker(int(getattr(tts, "sample_rate", 24000)), settings.output_device)
                with speaker:
                    for pcm, rate in tts.synthesize(text):
                        speaker.play(pcm, rate)
                    while speaker.pending_seconds() > 0 and self._call is None:
                        threading.Event().wait(0.05)
                self._emit(request_id, {"type": "preview_done", "voice": settings.voice})
            except Exception as exc:
                self._emit(request_id, {"type": "error", "message": str(exc)[:300] or type(exc).__name__})

        threading.Thread(target=work, name="star-voice-preview", daemon=True).start()
        return {"previewing": settings.voice}
