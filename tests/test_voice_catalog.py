"""The voice catalog, the per-style speaking manners and the bridge actions that use them."""
import json

import pytest

from star.voice import catalog
from star.voice.bridge import VOICE_ACTIONS, VoiceBridge
from star.voice.persona import ANIME_PROMPT, COMMANDING_PROMPT, STYLE_PROMPTS, VOICE_SYSTEM_PROMPT, system_message
from star.voice.settings import TTS_ENGINES, VoiceSettings
from voice_fakes import FakeSpeaker, FakeTTS


def entry(**over):
    base = {"id": "demo", "name": "Demo", "style": "confident-commanding", "archetype": "commanding",
            "engine": "kokoro", "engine_settings": {"recipe": [["af_kore", 1.0]], "speed": 0.7, "lang": "en-us",
                                                    "sentence_gap_ms": 450},
            "audition": "kokoro-styles/kore-slow", "licence": "Apache-2.0",
            "latency": {"first_audio_seconds": 0.33}, "measured": {"pitch_hz": 160}}
    base.update(over)
    return base


def write_catalog(path, *entries):
    path.write_text(json.dumps({"version": 1, "voices": list(entries)}), encoding="utf-8")
    return path


# -- the shipped catalog ---------------------------------------------------------------------------------------
def test_shipped_catalog_is_complete_and_original():
    voices = catalog.load_catalog()
    assert len({v.id for v in voices}) == len(voices) >= 8
    for style in catalog.STYLE_IDS:
        in_style = catalog.voices_for_style(style)
        assert in_style, f"no voices for {style}"
        assert any(v.engine in TTS_ENGINES for v in in_style), f"{style} has no voice that works in calls today"
    for v in voices:
        assert v.licence and v.audition and v.measured.get("pitch_hz"), v.id
        assert v.latency.get("first_audio_seconds") is not None, v.id
        if v.engine == "kokoro":
            assert v.engine_settings["recipe"] and v.engine_settings["speed"], v.id
        if v.engine == "qwen3-tts":
            assert v.engine_settings.get("instruct") or v.reference_clip, v.id
        if v.style == "anime-bright":
            assert v.measured["pitch_hz"] < 295, f"{v.id} is too high: could sound like a child"
        if v.style == "confident-commanding":
            assert v.measured["pitch_hz"] < 215, v.id


def test_each_style_has_one_recommendation_for_live_calls_that_runs_in_calls():
    for style in ("confident-commanding", "anime-bright"):
        live = [v for v in catalog.voices_for_style(style) if "live" in v.recommended_for]
        assert len(live) == 1 and live[0].engine in TTS_ENGINES


def test_default_voice_is_the_warm_one():
    assert VoiceSettings().voice_style == "warm-caring" == catalog.DEFAULT_STYLE
    assert catalog.find_voice(VoiceSettings().voice_id) is not None         # "star-mum" is in the catalog


def test_loading_rejects_unknown_style_and_duplicate_ids(tmp_path):
    with pytest.raises(ValueError, match="unknown style"):
        catalog.load_catalog(write_catalog(tmp_path / "a.json", entry(style="cartoon")))
    with pytest.raises(ValueError, match="duplicate"):
        catalog.load_catalog(write_catalog(tmp_path / "b.json", entry(), entry()))


def test_kokoro_recipe_string_matches_what_the_engine_parses():
    from star.voice.engines import parse_kokoro_voice
    e = catalog.load_catalog(write_catalog(
        __import__("pathlib").Path(__import__("tempfile").mkdtemp()) / "c.json",
        entry(engine_settings={"recipe": [["bf_emma", 0.5], ["af_kore", 0.5]], "speed": 0.7})))[0]
    assert parse_kokoro_voice(catalog.kokoro_recipe(e)) == [("bf_emma", 0.5), ("af_kore", 0.5)]


# -- speaking manners ------------------------------------------------------------------------------------------
def test_each_style_has_its_own_short_stable_prompt():
    assert set(STYLE_PROMPTS) == set(catalog.STYLE_IDS)
    assert system_message()["content"] == VOICE_SYSTEM_PROMPT                       # the default is unchanged
    assert system_message("", "confident-commanding")["content"] == COMMANDING_PROMPT
    assert system_message("", "anime-bright")["content"] == ANIME_PROMPT
    assert system_message("", "no-such-style")["content"] == VOICE_SYSTEM_PROMPT
    assert system_message("Name: Alex", "anime-bright")["content"].endswith("Name: Alex")
    for prompt in STYLE_PROMPTS.values():
        assert len(prompt) < 2400                                                    # short so the server can cache it
        assert "markdown" in prompt and "full stop" in prompt.lower() or "exclamation" in prompt.lower()


def test_commanding_and_anime_prompts_are_firm_about_what_they_never_do():
    c, a = COMMANDING_PROMPT.lower(), ANIME_PROMPT.lower()
    assert "nothing romantic or sexual" in c and "no pet names" in c and "role-play" in c
    assert "short, firm sentences" in c and "never plead or hedge" in c
    assert "no baby talk" in a and "no fan-service" in a and "no flirting" in a and "adult" in a
    assert "you are an ai" in c and "you are an ai" in a


def test_voice_style_flows_into_the_call_config_and_is_validated():
    settings = VoiceSettings.from_mapping({"voice_style": "anime-bright", "sentence_gap_ms": "450"})
    assert settings.call_config().style == "anime-bright" and settings.sentence_gap_ms == 450
    for bad in ({"voice_style": "dommy"}, {"tts_lang": "fr"}, {"sentence_gap_ms": 9000}, {"voice_id": "bad id!"}):
        with pytest.raises(ValueError):
            VoiceSettings.from_mapping(bad)


# -- bridge ------------------------------------------------------------------------------------------------------
class FakeKokoroLike(FakeTTS):
    """A TTS fake that has the same knobs as KokoroTTS (voice, speed, lang, gap)."""
    voice = "heart"
    speed = 0.92
    lang = "en-us"
    gap_ms = 0

    def set_voice(self, voice):
        self.voice = voice


def make_bridge(tmp_path, shipped=True):
    spoken = []

    class Tts(FakeKokoroLike):
        def synthesize(self, text):
            spoken.append((text, self.voice, self.speed, self.lang, self.gap_ms))
            return super().synthesize(text)

    class Factories:
        @staticmethod
        def engines(settings, progress):
            from star.voice.runtime import Engines
            from voice_fakes import FakeASR, FakeVAD
            return Engines(FakeVAD(), None, FakeASR({}), Tts(seconds_per_word=0.01), {})

        @staticmethod
        def speaker(sample_rate, device):
            class S(FakeSpeaker):
                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    self.stop()
            return S()

    events = []
    bridge = VoiceBridge(lambda cid, data: events.append((cid, data)), settings_path=tmp_path / "voice.json",
                         factories=Factories)
    bridge._engines = Factories.engines(VoiceSettings(), None)
    return bridge, events, spoken


def test_select_voice_is_a_registered_action():
    assert {"voiceListVoices", "voiceSelectVoice", "voicePreviewVoice"} <= VOICE_ACTIONS


def test_list_voices_returns_styles_voices_and_the_current_selection(tmp_path):
    bridge, _events, _spoken = make_bridge(tmp_path)
    out = bridge.handle("voiceListVoices", {})
    assert [s["id"] for s in out["styles"]] == list(catalog.STYLE_IDS)
    assert out["selected"]["style"] == "warm-caring"
    by_style = {}
    for v in out["voices"]:
        by_style.setdefault(v["style"], []).append(v)
        assert {"id", "name", "label", "engine", "engine_settings", "licence", "latency", "callable"} <= set(v)
        json.dumps(v)
    assert set(by_style) == set(catalog.STYLE_IDS)
    only = bridge.handle("voiceListVoices", {"style": "anime-bright"})["voices"]
    assert only and {v["style"] for v in only} == {"anime-bright"}
    with pytest.raises(ValueError, match="Unknown voice style"):
        bridge.handle("voiceListVoices", {"style": "x"})
    unusable = [v for v in out["voices"] if not v["callable"]]
    assert all(v["reason"] for v in unusable)


def test_select_voice_saves_voice_speed_language_gap_and_style(tmp_path):
    bridge, _events, _spoken = make_bridge(tmp_path)
    live = next(v for v in catalog.voices_for_style("confident-commanding") if "live" in v.recommended_for)
    out = bridge.handle("voiceSelectVoice", {"voiceId": live.id})
    saved = json.loads((tmp_path / "voice.json").read_text(encoding="utf-8"))
    assert saved == out["settings"]
    assert saved["voice_style"] == "confident-commanding" and saved["voice_id"] == live.id
    assert saved["speed"] == live.engine_settings["speed"]
    assert saved["sentence_gap_ms"] == live.engine_settings.get("sentence_gap_ms", 0)
    assert saved["voice"] == catalog.kokoro_recipe(live)
    again = bridge.handle("voiceGetSettings", {})["settings"]
    assert again["voice_id"] == live.id
    assert bridge.handle("voiceListVoices", {})["selected"]["voiceId"] == live.id


def test_select_voice_rejects_unknown_ids_and_engines_that_calls_cannot_run(tmp_path):
    bridge, _events, _spoken = make_bridge(tmp_path)
    with pytest.raises(ValueError, match="Unknown voice"):
        bridge.handle("voiceSelectVoice", {"voiceId": "no-such-voice"})
    other = next(v for v in catalog.load_catalog() if v.engine not in TTS_ENGINES)
    with pytest.raises(ValueError, match="not built into calls yet"):
        bridge.handle("voiceSelectVoice", {"voiceId": other.id})
    assert not (tmp_path / "voice.json").exists()


def test_preview_speaks_the_style_line_with_the_voice_settings(tmp_path):
    bridge, events, spoken = make_bridge(tmp_path)
    live = next(v for v in catalog.voices_for_style("anime-bright") if "live" in v.recommended_for)
    out = bridge.handle("voicePreviewVoice", {"voiceId": live.id}, "pv-1")
    assert out["voiceId"] == live.id
    deadline = __import__("time").time() + 5
    while not spoken and __import__("time").time() < deadline:
        __import__("time").sleep(0.01)
    text, voice, speed, lang, gap = spoken[0]
    assert text == catalog.STYLES["anime-bright"]["preview_line"]
    assert voice == catalog.kokoro_recipe(live) and speed == live.engine_settings["speed"]
    assert lang == live.engine_settings.get("lang", "en-us")
    with pytest.raises(ValueError, match="Unknown voice"):
        bridge.handle("voicePreviewVoice", {"voiceId": "nope"}, "pv-2")


def test_a_call_started_after_selecting_uses_the_selected_voice_and_style(tmp_path):
    bridge, _events, _spoken = make_bridge(tmp_path)
    live = next(v for v in catalog.voices_for_style("confident-commanding") if "live" in v.recommended_for)
    bridge.handle("voiceSelectVoice", {"voiceId": live.id})
    settings = bridge._load_settings()
    assert settings.call_config().style == "confident-commanding"
    engines = bridge._get_engines(settings, lambda _m: None)
    assert engines.tts.voice == catalog.kokoro_recipe(live) and engines.tts.speed == live.engine_settings["speed"]
    assert engines.tts.gap_ms == live.engine_settings.get("sentence_gap_ms", 0)


def test_pitch_change_is_a_validated_setting_and_a_pure_ratio():
    from star.voice.engines import pitch_ratio
    assert pitch_ratio(0) == 1.0 and pitch_ratio(12) == 2.0 and pitch_ratio(-12) == 0.5
    assert abs(pitch_ratio(3.0) - 1.1892) < 1e-3
    assert VoiceSettings.from_mapping({"pitch_semitones": "3.5"}).pitch_semitones == 3.5
    with pytest.raises(ValueError, match="pitch_semitones"):
        VoiceSettings.from_mapping({"pitch_semitones": 9})


def test_catalog_pitch_shifts_are_small_enough_to_stay_adult_sounding():
    for v in catalog.load_catalog():
        shift = v.engine_settings.get("pitch_semitones", 0.0)
        assert -3.5 <= shift <= 3.5, v.id                 # a bigger shift also changes the voice's apparent size
        if v.style == "anime-bright":
            assert shift >= 0, v.id
        if v.style == "confident-commanding":
            assert shift <= 0, v.id
