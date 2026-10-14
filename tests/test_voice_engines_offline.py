"""Voice engine logic that needs no model, GPU or numpy: model lookup, voice blends, the energy VAD,
engine fallbacks, the registries, and how Engines.load / build_session put a call together.

The optional voice packages (numpy, onnxruntime, faster-whisper, kokoro-onnx) are not installed on
CI, so they are replaced by small fakes and the numpy helpers by plain-Python stand-ins.
"""
import sys
import types
from types import SimpleNamespace

import pytest

from star.voice import engines, runtime
from star.voice.pcm import SAMPLE_RATE


def tone(level: int, samples: int = 512) -> bytes:
    return int(level).to_bytes(2, "little", signed=True) * samples


# ---------- where model files come from ----------

def test_models_come_from_the_configured_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("STAR_VOICE_MODELS", str(tmp_path))
    (tmp_path / "silero_vad.onnx").write_bytes(b"onnx")
    assert engines.model_file("silero_vad.onnx") == tmp_path / "silero_vad.onnx"
    with pytest.raises(FileNotFoundError, match="docs/STAR_VOICE_CALLS.md"):
        engines.model_file("kokoro-v1.0.onnx")


def test_without_configuration_models_live_under_local_app_data(tmp_path, monkeypatch):
    monkeypatch.delenv("STAR_VOICE_MODELS", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert engines.models_dir() == tmp_path / "STAR" / "voice-models"


# ---------- voice blends ----------

def test_named_voices_and_custom_blends_are_normalised():
    assert engines.parse_kokoro_voice("heart") == [("af_heart", 1.0)]
    assert engines.parse_kokoro_voice(" af_bella ") == [("af_bella", 1.0)]
    blend = engines.parse_kokoro_voice("af_heart:3+af_nicole:1")
    assert blend == [("af_heart", 0.75), ("af_nicole", 0.25)]
    assert sum(weight for _, weight in engines.parse_kokoro_voice("blend-heart-bella-nicole")) == pytest.approx(1.0)


@pytest.mark.parametrize("voice", [
    "af_heart:nan", "af_heart:inf", "af_heart:1+af_bella:nan", "af_heart:-1+af_bella:2",
    "af_heart:0", "af_heart:+", ":1", "af_heart:loud",
])
def test_impossible_blends_are_refused_instead_of_making_noise(voice):
    # Regression: "nan" and "inf" passed the checks and produced NaN style weights.
    with pytest.raises(ValueError, match="Unknown Kokoro voice"):
        engines.parse_kokoro_voice(voice)


def test_pitch_ratio_is_two_per_octave():
    assert engines.pitch_ratio(12) == pytest.approx(2.0)
    assert engines.pitch_ratio(-12) == pytest.approx(0.5)
    assert engines.pitch_ratio(0) == 1.0


# ---------- the energy VAD fallback ----------

def test_energy_vad_hears_speech_over_a_quiet_room_and_adapts_to_noise():
    vad = engines.EnergyVAD()
    assert vad.probability(tone(0)) == 0.0
    assert vad.probability(tone(8000)) == 1.0                  # clear speech
    noisy = engines.EnergyVAD()
    first = noisy.probability(tone(300))
    for _ in range(200):                                        # a steady fan in the room
        later = noisy.probability(tone(300))
    assert later < first                                        # the floor rose to meet the noise
    assert noisy.probability(tone(8000)) == 1.0                 # a voice still stands out


# ---------- speech recognition set-up and fallbacks ----------

class FakeWhisperModel:
    created = []
    fail_on = set()

    def __init__(self, name, device, compute_type):
        if device in FakeWhisperModel.fail_on:
            raise RuntimeError("cublas64_12.dll not found")
        FakeWhisperModel.created.append((name, device, compute_type))
        self.calls = []

    def transcribe(self, audio, **options):
        self.calls.append(options)
        return [SimpleNamespace(text=" Hello Star. ")], None


@pytest.fixture
def whisper(monkeypatch):
    FakeWhisperModel.created, FakeWhisperModel.fail_on = [], set()
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(engines, "add_nvidia_dll_dirs", lambda: None)
    monkeypatch.setattr(engines, "pcm16_to_float", lambda pcm: SimpleNamespace(size=len(pcm) // 2))
    return FakeWhisperModel


def test_automatic_choice_uses_the_small_model_on_a_gpu_and_base_on_a_cpu(whisper, monkeypatch):
    monkeypatch.setattr(engines, "gpu_available", lambda: True)
    asr = engines.FasterWhisperASR()
    assert (asr.device, asr.model_name) == ("cuda", "small.en") and whisper.created[-1][2] == "float16"
    monkeypatch.setattr(engines, "gpu_available", lambda: False)
    asr = engines.FasterWhisperASR()
    assert (asr.device, asr.model_name) == ("cpu", "base.en") and whisper.created[-1][2] == "int8"


def test_a_broken_cuda_runtime_falls_back_to_the_cpu_instead_of_failing_the_call(whisper):
    whisper.fail_on = {"cuda"}
    asr = engines.FasterWhisperASR("small.en", device="cuda")
    assert asr.device == "cpu" and whisper.created == [("small.en", "cpu", "int8")]


def test_a_cpu_failure_is_reported(whisper):
    whisper.fail_on = {"cpu"}
    with pytest.raises(RuntimeError, match="cublas"):
        engines.FasterWhisperASR("base.en", device="cpu")


def test_very_short_clips_are_not_sent_to_the_model_and_other_rates_are_resampled(whisper, monkeypatch):
    asr = engines.FasterWhisperASR("base.en", device="cpu")
    assert asr.transcribe(tone(100, SAMPLE_RATE // 20)) == ""          # 50 ms: nothing to recognise
    assert asr._model.calls == []
    seen = []
    monkeypatch.setattr(engines, "resample", lambda audio, source, target: seen.append((source, target)) or
                        SimpleNamespace(size=audio.size * target // source))
    assert asr.transcribe(tone(100, 48000), sample_rate=48000) == "Hello Star."
    assert seen == [(48000, SAMPLE_RATE)]
    options = asr._model.calls[-1]
    assert options["vad_filter"] is False and options["condition_on_previous_text"] is False
    assert options["initial_prompt"] is None                         # no hint configured


# ---------- text to speech: pace, pitch and pauses ----------

class FakeKokoro:
    def __init__(self):
        self.requests = []

    def create(self, text, voice, speed, lang):
        self.requests.append((text, speed, lang))
        return [0.0] * 2400, 24000


def kokoro(monkeypatch, *, pitch=0.0, gap_ms=0, speed=1.0):
    tts = engines.KokoroTTS.__new__(engines.KokoroTTS)
    import threading
    tts._kokoro, tts._lock, tts._style = FakeKokoro(), threading.Lock(), object()
    tts.speed, tts.lang, tts.gap_ms, tts.pitch_semitones = speed, "en-us", gap_ms, pitch
    monkeypatch.setattr(engines, "float_to_pcm16", lambda samples: b"\x01\x00" * len(samples))
    return tts


def test_speech_without_pitch_change_is_one_chunk_at_the_asked_speed(monkeypatch):
    tts = kokoro(monkeypatch, speed=0.92)
    chunks = list(tts.synthesize("Hello."))
    assert chunks == [(b"\x01\x00" * 2400, 24000)]
    assert tts._kokoro.requests == [("Hello.", 0.92, "en-us")]


def test_a_pitch_change_resamples_and_compensates_the_speed(monkeypatch):
    tts = kokoro(monkeypatch, pitch=12, speed=1.0)                 # one octave up
    resampled = []
    monkeypatch.setattr(engines, "resample", lambda samples, source, target: resampled.append((source, target)) or
                        samples[: len(samples) * target // source])
    [(pcm, rate)] = list(tts.synthesize("Hi."))
    assert tts._kokoro.requests[0][1] == pytest.approx(0.5)         # Kokoro speaks slower ...
    assert resampled == [(24000, 12000)] and rate == 24000          # ... and the clip is played back faster
    assert len(pcm) == 2 * 1200


def test_a_sentence_gap_adds_exact_silence(monkeypatch):
    tts = kokoro(monkeypatch, gap_ms=250)
    chunks = list(tts.synthesize("Listen."))
    assert chunks[1] == (b"\x00\x00" * 6000, 24000)                 # 250 ms at 24 kHz


# ---------- registries ----------

def test_registries_build_known_engines_and_refuse_unknown_names(monkeypatch):
    assert isinstance(engines.make_vad("energy"), engines.EnergyVAD)
    for name in ("", "none", "silence"):
        assert engines.make_endpointer(name) is None
    for factory, name in ((engines.make_vad, "webrtc"), (engines.make_endpointer, "pause"),
                          (engines.make_asr, "whisper.cpp"), (engines.make_tts, "piper")):
        with pytest.raises(ValueError, match="Unknown"):
            factory(name)


def test_no_gpu_is_reported_when_onnxruntime_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    assert engines.gpu_available() is False


# ---------- putting a call together (star/voice/runtime.py) ----------

class Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return method


def test_engines_load_in_order_with_progress_and_are_warmed_up(monkeypatch):
    from star.voice.settings import VoiceSettings
    built = {name: Recorder() for name in ("vad", "endpointer", "asr", "tts")}
    monkeypatch.setattr(engines, "make_vad", lambda name: built["vad"])
    monkeypatch.setattr(engines, "make_endpointer", lambda name: built["endpointer"])
    monkeypatch.setattr(engines, "make_asr", lambda *args: built["asr"])
    monkeypatch.setattr(engines, "make_tts", lambda *args, **kwargs: built["tts"])
    messages = []
    loaded = runtime.Engines.load(VoiceSettings(), progress=messages.append)
    assert messages == ["Loading voice activity detector", "Loading end-of-turn model", "Loading speech recognition",
                        "Loading Star's voice", "Warming up"]
    assert set(loaded.load_seconds) == set(messages)
    assert [call[0] for call in built["tts"].calls] == ["warm_up"]
    assert built["asr"].calls[0][0] == "transcribe" and built["asr"].calls[0][1][1] == 16000
    assert built["endpointer"].calls[0][0] == "complete_probability"


def test_a_session_primes_the_brain_and_resets_the_vad(monkeypatch):
    from star.voice.settings import VoiceSettings
    vad, brain = Recorder(), Recorder()
    loaded = runtime.Engines(vad=vad, endpointer=None, asr=object(), tts=object(), load_seconds={})
    session = runtime.build_session(VoiceSettings(), loaded, speaker=object(), brain=brain)
    assert [call[0] for call in brain.calls] == ["prime"]
    assert brain.calls[0][1][0][0]["role"] == "system"
    assert [call[0] for call in vad.calls] == ["reset"]
    assert session is not None
    runtime.build_session(VoiceSettings(), loaded, speaker=object(), brain=brain, prime=False)
    assert len(brain.calls) == 1
