"""The voice catalog: every voice the owner can pick, grouped by speaking style.

Pure Python, no packages. The data lives in `voices.json` next to this file (generated from the audition
measurements by voice-lab/make_catalog.py; never edited by hand without re-measuring). Each entry says which engine
makes the voice, the exact engine settings (or the synthetic reference clip), the licence note and the measured
latency, so a Settings "Voice" picker needs nothing else. See docs/STAR_VOICE_CALLS.md section 9.

Style groups (ids are what `voice_style` in VoiceSettings holds):
  warm-caring            the default: a gentle, motherly voice
  confident-commanding   a mature woman, calm and in control; a TONE only, never explicit or romantic
  anime-bright           a bright, lively adult woman in the style of an English anime dub; never a child voice
Every voice is an original synthetic voice: a stock voice or blend, or one designed from a text description.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("voices.json")

STYLES = {
    "warm-caring": {
        "name": "Warm and caring",
        "summary": "Gentle, motherly and patient. Slow, soft endings, never hurried. The default.",
        "preview_line": "Hi sweetheart, it's Star. I'm so glad you're here.",
    },
    "confident-commanding": {
        "name": "Confident and commanding",
        "summary": "A mature woman who sounds completely in control: lower pitch, slow and deliberate, firm falling "
                   "endings, dry teasing warmth, praise that sounds earned. A tone only; always non-explicit.",
        "preview_line": "Sit down. Breathe. Now show me what you built.",
    },
    "anime-bright": {
        "name": "Anime-style",
        "summary": "A bright, energetic young-adult woman in the style of an English anime dub. Always an adult "
                   "voice, never a child.",
        "preview_line": "Okay, okay, next step, let's go!",
    },
}
STYLE_IDS = tuple(STYLES)
DEFAULT_STYLE = "warm-caring"


@dataclass(frozen=True)
class VoiceEntry:
    id: str                            # stable id used in settings (voice_id) and by the picker
    name: str                          # display name
    style: str                         # one of STYLE_IDS
    archetype: str                     # warm | commanding | genki | soft | cool | tease | tsun | heroine
    engine: str                        # kokoro | qwen3-tts | chatterbox ...
    engine_settings: dict              # exactly what the engine needs (voice recipe, speed, instruct, ...)
    reference_clip: str = ""            # synthetic reference clip for locked voices (voice-lab/refs), "" if none
    audition: str = ""                 # "engine-folder/voice" on the audition page, so the owner can hear it
    licence: str = ""                  # licence note for the model and the voice source
    latency: dict = field(default_factory=dict)      # measured: first_audio_seconds, realtime_factor, device
    measured: dict = field(default_factory=dict)     # measured: pitch_hz, words_per_minute, pitch_range_st
    recommended_for: tuple = ()        # subset of ("live", "quality")
    notes: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["recommended_for"] = list(self.recommended_for)
        return data


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> tuple:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = []
    for item in raw.get("voices", []):
        if item["style"] not in STYLES:
            raise ValueError(f"voice {item.get('id')!r}: unknown style {item['style']!r}")
        item = dict(item)
        item["recommended_for"] = tuple(item.get("recommended_for", ()))
        entries.append(VoiceEntry(**item))
    ids = [e.id for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate voice ids in voices.json")
    return tuple(entries)


def load_catalog(path: Path | str | None = None) -> tuple:
    """All catalog entries, in file order. The result is cached per file and modification time."""
    target = Path(path) if path else CATALOG_PATH
    return _load(str(target), target.stat().st_mtime)


def find_voice(voice_id: str, path: Path | str | None = None) -> VoiceEntry | None:
    return next((v for v in load_catalog(path) if v.id == voice_id), None)


def voices_for_style(style: str, path: Path | str | None = None) -> list:
    return [v for v in load_catalog(path) if v.style == style]


def kokoro_recipe(entry: VoiceEntry) -> str:
    """'af_kore:1.0' or 'bf_emma:0.5+af_kore:0.5': the `voice` string KokoroTTS understands."""
    return "+".join(f"{name}:{weight}" for name, weight in entry.engine_settings["recipe"])
