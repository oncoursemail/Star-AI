"""Validation, coercion and config conversion of untrusted voice UI settings."""
import pytest

from star.voice.settings import VoiceSettings


def test_defaults_and_none_mapping_are_valid_and_independent():
    defaults = VoiceSettings().validate()
    loaded = VoiceSettings.from_mapping(None)
    assert loaded == defaults
    assert loaded is not defaults


def test_valid_bounds_are_inclusive_and_unknown_ui_keys_are_ignored():
    settings = VoiceSettings.from_mapping({
        "voice": "x" * 120, "voice_id": "y" * 120,
        "speed": "1.4", "sentence_gap_ms": "1500", "pitch_semitones": "-6",
        "asr_prompt": "a" * 300, "system_extra": "z" * 1200,
        "input_device": "i" * 120, "output_device": "o" * 120,
        "max_reply_tokens": "800", "end_silence_ms": "3000",
        "min_end_silence_ms": "2000", "max_silence_ms": "6000",
        "barge_in_ms": "2000", "not_a_setting": "ignored",
    })
    assert settings.speed == 1.4
    assert settings.sentence_gap_ms == 1500
    assert settings.pitch_semitones == -6.0
    assert settings.max_reply_tokens == 800
    assert settings.max_silence_ms == 6000
    assert "not_a_setting" not in vars(settings)
    assert VoiceSettings.from_mapping({
        "speed": 0.6, "max_reply_tokens": 16, "min_end_silence_ms": 256,
        "end_silence_ms": 300, "max_silence_ms": 300, "barge_in_ms": 96,
        "pitch_semitones": 6.0,
    }).validate()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"voice": ""}, "Invalid voice id"),
        ({"voice": "x" * 121}, "Invalid voice id"),
        ({"voice_id": "../bad"}, "Invalid voice catalog id"),
        ({"tts_lang": "fr"}, "Unknown voice language"),
        ({"voice_style": "other"}, "Unknown voice style"),
        ({"sentence_gap_ms": 1501}, "sentence_gap_ms"),
        ({"pitch_semitones": 6.01}, "pitch_semitones"),
        ({"asr_prompt": "a" * 301}, "Speech-to-text hint"),
        ({"vad": "other"}, "Unknown voice activity detector"),
        ({"endpointer": "other"}, "Unknown end-of-turn setting"),
        ({"min_end_silence_ms": 255}, "min_end_silence_ms"),
        ({"max_silence_ms": 639}, "max_silence_ms"),
        ({"barge_in_ms": 2001}, "barge_in_ms"),
        ({"input_device": "a" * 121}, "Device name is too long"),
        ({"system_extra": "z" * 1201}, "Extra context is too long"),
    ],
)
def test_invalid_settings_reject_each_untrusted_boundary(payload, message):
    with pytest.raises(ValueError, match=message):
        VoiceSettings.from_mapping(payload)


def test_mapping_overlays_base_without_mutation_and_coerces_boolean():
    base = VoiceSettings(speed=1.1, asr_model="tiny", partial_transcripts=True)
    updated = VoiceSettings.from_mapping(
        {"speed": "0.6", "partial_transcripts": "no", "sentence_gap_ms": "200",
         "system_extra": None, "ignored": "anything"},
        base=base,
    )
    assert (updated.speed, updated.asr_model, updated.partial_transcripts, updated.sentence_gap_ms) == (
        0.6, "tiny", False, 200)
    assert updated.system_extra == base.system_extra
    assert base.speed == 1.1 and base.partial_transcripts is True
    assert VoiceSettings.from_mapping({"partial_transcripts": "ON"}).partial_transcripts is True


def test_invalid_numeric_value_fails_before_instantation():
    with pytest.raises(ValueError):
        VoiceSettings.from_mapping({"speed": "not-a-number"})


def test_environment_only_overrides_selected_known_fields(monkeypatch):
    for key in VoiceSettings.__dataclass_fields__:
        monkeypatch.delenv(f"STAR_VOICE_{key.upper()}", raising=False)
    monkeypatch.setenv("STAR_VOICE_VOICE", "blend-heart")
    monkeypatch.setenv("STAR_VOICE_MAX_REPLY_TOKENS", "800")
    monkeypatch.setenv("STAR_VOICE_PARTIAL_TRANSCRIPTS", "false")
    settings = VoiceSettings.from_env()
    assert settings.voice == "blend-heart"
    assert settings.max_reply_tokens == 800
    assert settings.partial_transcripts is False
    assert settings.asr_model == VoiceSettings().asr_model
    monkeypatch.setenv("STAR_VOICE_SPEED", "unparseable")
    with pytest.raises(ValueError):
        VoiceSettings.from_env()


def test_call_config_propagates_selected_modes_and_caps_minimum_silence():
    settings = VoiceSettings.from_mapping({
        "end_silence_ms": 300, "max_silence_ms": 300, "min_end_silence_ms": 1200,
        "output": "speakers", "voice_style": "anime-bright",
        "system_extra": "test context", "partial_transcripts": False,
        "barge_in_ms": 96,
    })
    config = settings.call_config()
    assert config.turn.end_silence_ms == 300
    assert config.turn.max_silence_ms == 300
    assert config.turn.min_end_silence_ms == 300
    assert config.turn.barge_in_ms == 96
    assert config.use_echo_gate is True
    assert config.style == "anime-bright"
    assert config.system_extra == "test context"
    assert config.partial_transcripts is False
