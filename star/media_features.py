"""Optional offline media integrations; costly models are loaded only when requested."""
from __future__ import annotations
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.webm', '.avi'}
AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac'}


def video_frames(path: Path, destination: Path, *, max_frames: int = 4) -> list[Path]:
    """Use installed ffprobe/ffmpeg to sample a bounded number of video frames."""
    path = path.expanduser().resolve(strict=True)
    if path.suffix.lower() not in VIDEO_EXTENSIONS or path.stat().st_size > 700_000_000:
        raise ValueError('Unsupported video or file exceeds 700 MB')
    if max_frames < 1 or max_frames > 4:
        raise ValueError('Use 1-4 frames per model request')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Install FFmpeg (ffmpeg and ffprobe) and add them to PATH for video frames')
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
                       capture_output=True, text=True, timeout=20, check=True)
    duration = float(p.stdout.strip())
    if duration <= 0 or duration > 60 * 90:
        raise ValueError('Video duration out of supported range (90 minutes)')
    destination.mkdir(parents=True, exist_ok=True)
    points = [max(0., duration * (i + .5) / max_frames) for i in range(max_frames)]
    outputs = []
    for i, sec in enumerate(points):
        out = destination / f'frame_{i+1:02}.jpg'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{sec:.3f}',
                        '-i',str(path), '-frames:v','1','-vf','scale=1280:720:force_original_aspect_ratio=decrease',
                        '-y',str(out)], capture_output=True, text=True, check=True, timeout=40)
        if out.exists() and out.stat().st_size:
            outputs.append(out)
    if not outputs:
        raise RuntimeError('Unable to decode sampled video frames')
    return outputs


def transcribe_audio(path: Path, *, model_name: str = 'base', device: str = 'cpu') -> str:
    """Optional faster-whisper offline STT; CPU int8 default avoids GPU contention."""
    path = path.expanduser().resolve(strict=True)
    if path.suffix.lower() not in AUDIO_EXTENSIONS or path.stat().st_size > 200_000_000:
        raise ValueError('Unsupported audio or file exceeds 200 MB')
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('Install optional voice extras: pip install -r requirements-voice.txt') from exc
    if model_name not in {'tiny', 'base', 'small'}:
        raise ValueError('Supported STT models: tiny, base, small')
    if device not in {'cpu', 'cuda'}:
        raise ValueError('Invalid transcription device')
    engine = WhisperModel(model_name, device=device, compute_type='int8' if device == 'cpu' else 'float16')
    segments, _ = engine.transcribe(str(path), vad_filter=True, beam_size=3)
    return ' '.join(seg.text.strip() for seg in segments if seg.text.strip()).strip()


def local_speak(text: str) -> None:
    """Optional Windows SAPI speech via pyttsx3; speaking runs in the caller's worker thread."""
    if len(text) > 8000:
        raise ValueError('Text is too long to speak')
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError('Install optional voice extras: pip install -r requirements-voice.txt') from exc
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
