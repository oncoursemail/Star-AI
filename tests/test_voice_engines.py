"""Speech-recognition wrapper logic that does not need a model: hint-text filtering and the automatic model choice."""
import threading
from types import SimpleNamespace

from star.voice import engines


def make_asr(monkeypatch, said: str, prompt: str):
    """A FasterWhisperASR whose model 'hears' `said`, without loading anything."""
    asr = engines.FasterWhisperASR.__new__(engines.FasterWhisperASR)
    asr.language, asr.prompt, asr._lock = "en", prompt, threading.Lock()
    asr._model = SimpleNamespace(transcribe=lambda audio, **kw: ([SimpleNamespace(text=said)], None))
    monkeypatch.setattr(engines, "pcm16_to_float", lambda pcm: SimpleNamespace(size=len(pcm) // 2))
    return asr


CLIP = b"\x01\x00" * 16000          # one second of 16 kHz samples; the fake model ignores the content


def test_a_transcript_that_is_only_the_hint_text_is_not_speech(monkeypatch):
    hint = "Star, Roblox, RemoteEvent, Luau, ModuleScript."
    asr = make_asr(monkeypatch, "Star, Roblox, RemoteEvent, Luau.", hint)        # most of the hint repeated back
    assert asr.transcribe(CLIP) == ""


def test_real_speech_that_uses_the_hint_words_is_kept(monkeypatch):
    hint = "Star, Roblox, RemoteEvent, Luau, ModuleScript."
    said = "How does a RemoteEvent work in Roblox?"
    assert make_asr(monkeypatch, said, hint).transcribe(CLIP) == said
    assert make_asr(monkeypatch, "Roblox", hint).transcribe(CLIP) == "Roblox"       # a short true word is not discarded


def test_no_hint_means_no_filtering(monkeypatch):
    assert make_asr(monkeypatch, "Hello there.", "").transcribe(CLIP) == "Hello there."


def test_auto_model_depends_on_the_device():
    assert engines.AUTO_ASR_MODEL == {"cuda": "small.en", "cpu": "base.en"}
