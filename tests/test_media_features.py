"""Optional offline media helpers (FFmpeg frames, faster-whisper, SAPI speech) with the tools faked.

No FFmpeg, Whisper model or speech engine is needed: the tests replace them and check the
bounds STAR applies before anything heavy runs.
"""
import subprocess
import sys
import types

import pytest

import star.media_features as media


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "gameplay.mp4"
    path.write_bytes(b"not really a video")
    return path


class FakeFFmpeg:
    """Answers ffprobe with a duration and writes a small JPEG for every ffmpeg frame request."""

    def __init__(self, duration="120.0", write=True):
        self.duration, self.write, self.calls = duration, write, []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert kwargs.get("timeout") and kwargs.get("check") is True and "shell" not in kwargs
        if argv[0] == "ffprobe":
            return subprocess.CompletedProcess(argv, 0, stdout=self.duration + "\n", stderr="")
        if self.write:
            with open(argv[-1], "wb") as handle:
                handle.write(b"jpeg")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


@pytest.fixture
def ffmpeg(monkeypatch):
    fake = FakeFFmpeg()
    monkeypatch.setattr(media.shutil, "which", lambda name: "C:/ffmpeg/bin/" + name + ".exe")
    monkeypatch.setattr(media.subprocess, "run", fake)
    return fake


def test_frames_are_sampled_evenly_through_the_video(clip, tmp_path, ffmpeg):
    frames = media.video_frames(clip, tmp_path / "frames", max_frames=4)
    assert [frame.name for frame in frames] == ["frame_01.jpg", "frame_02.jpg", "frame_03.jpg", "frame_04.jpg"]
    seeks = [argv[argv.index("-ss") + 1] for argv in ffmpeg.calls if argv[0] == "ffmpeg"]
    assert seeks == ["15.000", "45.000", "75.000", "105.000"]       # the middle of each quarter
    assert all(argv[argv.index("-frames:v") + 1] == "1" for argv in ffmpeg.calls if argv[0] == "ffmpeg")


@pytest.mark.parametrize("duration", ["0", "-3", "5401", "nan", "inf", "N/A", ""])
def test_videos_without_a_usable_duration_are_refused_before_decoding(clip, tmp_path, ffmpeg, duration):
    ffmpeg.duration = duration
    with pytest.raises(ValueError, match="duration"):
        media.video_frames(clip, tmp_path / "frames")
    assert [argv[0] for argv in ffmpeg.calls] == ["ffprobe"]          # no frame was decoded
    assert not (tmp_path / "frames").exists()


@pytest.mark.parametrize("count", [0, 5, 2.5, "2"])
def test_one_to_four_whole_frames_per_request(clip, tmp_path, ffmpeg, count):
    with pytest.raises((ValueError, TypeError)):
        media.video_frames(clip, tmp_path / "frames", max_frames=count)
    assert ffmpeg.calls == []


def test_other_file_types_are_refused(tmp_path, ffmpeg):
    other = tmp_path / "notes.txt"
    other.write_text("x")
    with pytest.raises(ValueError, match="Unsupported video"):
        media.video_frames(other, tmp_path / "frames")
    with pytest.raises(FileNotFoundError):
        media.video_frames(tmp_path / "missing.mp4", tmp_path / "frames")


def test_missing_ffmpeg_says_how_to_install_it(clip, tmp_path, monkeypatch):
    monkeypatch.setattr(media.shutil, "which", lambda name: None if name == "ffprobe" else "ffmpeg.exe")
    with pytest.raises(RuntimeError, match="Install FFmpeg"):
        media.video_frames(clip, tmp_path / "frames")


def test_no_decodable_frame_is_an_error_not_an_empty_list(clip, tmp_path, ffmpeg):
    ffmpeg.write = False
    with pytest.raises(RuntimeError, match="Unable to decode"):
        media.video_frames(clip, tmp_path / "frames", max_frames=2)


# ---------- transcription and speech, with the optional packages faked ----------

class FakeWhisper:
    created = []

    def __init__(self, name, device, compute_type):
        FakeWhisper.created.append((name, device, compute_type))

    def transcribe(self, path, vad_filter, beam_size):
        assert vad_filter is True
        segments = [types.SimpleNamespace(text=" Hello there. "), types.SimpleNamespace(text="   "),
                    types.SimpleNamespace(text="Build a lobby.")]
        return iter(segments), {"language": "en"}


@pytest.fixture
def whisper(monkeypatch):
    FakeWhisper.created = []
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisper))
    return FakeWhisper


@pytest.fixture
def voice_note(tmp_path):
    path = tmp_path / "note.wav"
    path.write_bytes(b"RIFF")
    return path


def test_transcription_joins_non_empty_segments_and_uses_int8_on_cpu(voice_note, whisper):
    assert media.transcribe_audio(voice_note) == "Hello there. Build a lobby."
    assert whisper.created == [("base", "cpu", "int8")]
    media.transcribe_audio(voice_note, model_name="tiny", device="cuda")
    assert whisper.created[-1] == ("tiny", "cuda", "float16")


@pytest.mark.parametrize("options", [{"model_name": "large-v3"}, {"device": "npu"}])
def test_transcription_refuses_unknown_models_and_devices(voice_note, whisper, options):
    with pytest.raises(ValueError):
        media.transcribe_audio(voice_note, **options)
    assert whisper.created == []


def test_transcription_without_the_voice_extras_says_what_to_install(voice_note, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)          # import fails
    with pytest.raises(RuntimeError, match="not set up"):
        media.transcribe_audio(voice_note)


def test_transcription_refuses_non_audio_files(tmp_path, whisper):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported audio"):
        media.transcribe_audio(video)


def test_local_speech_speaks_once_and_refuses_very_long_text(monkeypatch):
    spoken = []

    class Engine:
        def say(self, text):
            spoken.append(text)

        def runAndWait(self):
            spoken.append("<done>")

    monkeypatch.setitem(sys.modules, "pyttsx3", types.SimpleNamespace(init=Engine))
    media.local_speak("Your build is ready.")
    assert spoken == ["Your build is ready.", "<done>"]
    with pytest.raises(ValueError, match="too long"):
        media.local_speak("x" * 8001)
    monkeypatch.setitem(sys.modules, "pyttsx3", None)
    with pytest.raises(RuntimeError, match="not set up"):
        media.local_speak("Hello")
