"""Star's mum persona, read-aloud and push-to-talk calls (2026-10-13): the non-audio logic, with fake engines."""
import json
import threading

import pytest

from star.voice import catalog
from star.voice.bridge import VOICE_ACTIONS, VoiceBridge
from star.voice.call import CallConfig, CallSession
from star.voice.persona import VOICE_SYSTEM_PROMPT
from star.voice.readaloud import CODE_POINTER, REST_ON_SCREEN, TABLE_POINTER, sentences, spoken_text
from star.voice.runtime import Engines
from star.voice.settings import STAR_VOICE, STAR_VOICE_ID, VoiceSettings
from star.voice.turn import TurnConfig
from voice_fakes import Events, FakeASR, FakeBrain, FakeSpeaker, FakeTTS, FakeVAD, quiet, speech, wait_for

TEXTS = {1: "I had a really bad day", 2: "sorry go on", 3: "tell me a story"}


# -- the default persona ------------------------------------------------------------------------
def test_default_voice_is_the_star_mum_from_the_catalog_and_push_to_talk_is_the_default_call_mode():
    settings = VoiceSettings().validate()
    entry = catalog.find_voice(STAR_VOICE_ID)
    assert entry is not None and entry.style == "warm-caring" and "live" in entry.recommended_for
    assert entry.engine == "kokoro" and catalog.kokoro_recipe(entry) == STAR_VOICE == settings.voice
    assert settings.speed == entry.engine_settings["speed"]
    assert settings.sentence_gap_ms == entry.engine_settings["sentence_gap_ms"]
    assert settings.call_mode == "push-to-talk" and settings.read_aloud_auto is False
    assert settings.call_config().push_to_talk is True
    assert VoiceSettings(call_mode="hands-free").call_config().push_to_talk is False
    with pytest.raises(ValueError, match="Call mode"):
        VoiceSettings.from_mapping({"call_mode": "always-listening"})
    assert VoiceSettings.from_mapping({"read_aloud_auto": "true"}).read_aloud_auto is True
    # The first warm-caring voice the picker shows is the default one.
    assert catalog.voices_for_style("warm-caring")[0].id == STAR_VOICE_ID


def test_mum_persona_is_warm_spoken_and_never_romantic():
    prompt = VOICE_SYSTEM_PROMPT.lower()
    assert "mum" in prompt and "short" in prompt and "markdown" in prompt
    assert "never romantic, flirtatious or sexual" in prompt


# -- read-aloud text ----------------------------------------------------------------------------
def test_spoken_text_turns_markdown_into_plain_sentences():
    reply = ("## Fixing your script\n\nHere's what went wrong, sweetheart:\n\n- The `RemoteEvent` was never created\n"
             "- You called it before the **server** loaded\n\n```lua\nlocal x = 1\n```\n\n```lua\nprint(x)\n```\n\n"
             "| a | b |\n|---|---|\n| 1 | 2 |\n\nSee [the docs](https://create.roblox.com) or C:/Users/me/src/main.lua "
             "or https://example.com 🙂\n\n---\n<think>hidden plan</think>")
    text = spoken_text(reply)
    assert text.startswith("Fixing your script. Here's what went wrong, sweetheart:")
    assert "The RemoteEvent was never created. You called it before the server loaded." in text
    assert text.count(CODE_POINTER) == 1 and text.count(TABLE_POINTER) == 1
    for unwanted in ("#", "*", "`", "|", "http", "C:/", "hidden plan", "🙂", "---", "local x"):
        assert unwanted not in text
    assert "the docs" in text and "a file path" in text and "a link" in text


def test_spoken_text_cuts_long_replies_at_a_sentence_and_points_to_the_screen():
    long_reply = " ".join(f"This is sentence number {i}." for i in range(400))
    text = spoken_text(long_reply, max_chars=500)
    assert len(text) <= 500 + len(REST_ON_SCREEN) + 1
    assert text.endswith(REST_ON_SCREEN) and text[: -len(REST_ON_SCREEN)].rstrip().endswith(".")
    assert spoken_text("```python\nprint(1)\n```") == CODE_POINTER
    assert spoken_text("") == "" and spoken_text("***\n---\n🙂") == ""


def test_sentences_split_for_the_voice_engine():
    parts = sentences("Oh, well done. I am so proud of you. What does it do?")
    assert parts == ["Oh, well done.", "I am so proud of you.", "What does it do?"]


# -- push-to-talk in a call ---------------------------------------------------------------------
def ptt_session(replies, *, tts_kwargs=None, brain_kwargs=None, voice_barge_in=True):
    events, speaker = Events(), FakeSpeaker()
    brain, tts = FakeBrain(replies, **(brain_kwargs or {})), FakeTTS(**(tts_kwargs or {}))
    config = CallConfig(turn=TurnConfig(), partial_transcripts=False, push_to_talk=True, ptt_tail_ms=64,
                        ptt_voice_barge_in=voice_barge_in)
    session = CallSession(vad=FakeVAD(), asr=FakeASR(TEXTS), brain=brain, tts=tts, speaker=speaker, config=config,
                          on_event=events)
    session.start()
    return session, events, brain, tts, speaker


def feed(session, frames):
    for frame in frames:
        session.feed(frame)


def test_push_to_talk_turn_ends_on_release_without_waiting_for_silence():
    session, events, brain, tts, _speaker = ptt_session(["Oh, love. I'm sorry. Do you want to tell me about it?"])
    feed(session, speech(1, 20))                   # talking without the key does nothing
    assert session.state == "listening" and not events.of("speech_started")
    session.push_to_talk(True)
    session.push_to_talk(True)                     # key repeat is ignored
    feed(session, speech(1, 20))
    session.push_to_talk(False)
    feed(session, speech(1, 1) + quiet(3))         # the release tail (64 ms) still records trailing words
    assert session.wait_idle(5) and wait_for(lambda: len(session.turns) == 1)
    metrics = session.turns[0]
    assert metrics.end_reason == "push_to_talk" and metrics.user_text == TEXTS[1]
    assert metrics.turn_end - metrics.speech_end < 0.2      # no end-of-turn wait: only the release tail
    assert events.of("speech_started")[0] == {"type": "speech_started", "barge_in": False, "push_to_talk": True}
    assert tts.spoken[0] == "Oh, love." and brain.requests[0][-1] == {"role": "user", "content": TEXTS[1]}
    assert events.states() == ["listening", "user_speaking", "thinking", "speaking", "listening"]


def test_a_tap_with_no_speech_is_discarded():
    session, events, brain, _tts, _speaker = ptt_session(["unused"])
    session.push_to_talk(True)
    feed(session, quiet(10))
    session.push_to_talk(False)
    feed(session, quiet(4))
    assert wait_for(lambda: events.of("discarded"))
    assert not brain.requests and session.state == "listening"


def test_pressing_the_key_while_star_talks_interrupts_her_and_opens_a_new_turn():
    reply = "Oh, sweetheart. " + " ".join(f"word{i}" for i in range(1, 41)) + "."
    session, events, brain, _tts, speaker = ptt_session([reply, "Of course, go on."], brain_kwargs={"delay": 0.01},
                                                        tts_kwargs={"seconds_per_word": 0.05})
    session.push_to_talk(True)
    feed(session, speech(1, 20))
    session.push_to_talk(False)
    feed(session, quiet(3))
    assert wait_for(lambda: session.state == "speaking" and speaker.played_seconds() > 0.3)
    session.push_to_talk(True)                     # barge-in with the key
    assert wait_for(lambda: events.of("interrupted"))
    assert events.of("interrupted")[0]["reason"] == "push_to_talk" and speaker.pending_seconds() == 0
    assert brain.streams[0].closed.is_set()
    feed(session, speech(2, 15))
    session.push_to_talk(False)
    feed(session, quiet(3))
    assert session.wait_idle(5) and wait_for(lambda: len(session.turns) == 2)
    assert brain.requests[1][-1] == {"role": "user", "content": TEXTS[2]}
    assert session.history[-1] == {"role": "assistant", "content": "Of course, go on."}


def test_talking_over_star_without_the_key_silences_her_but_opens_no_turn():
    reply = "Oh, sweetheart. " + " ".join(f"word{i}" for i in range(1, 41)) + "."
    session, events, brain, _tts, speaker = ptt_session([reply], brain_kwargs={"delay": 0.01},
                                                        tts_kwargs={"seconds_per_word": 0.05})
    session.push_to_talk(True)
    feed(session, speech(1, 20))
    session.push_to_talk(False)
    feed(session, quiet(3))
    assert wait_for(lambda: session.state == "speaking" and speaker.played_seconds() > 0.3)
    feed(session, speech(2, 12))                   # 384 ms of talking over her, no key
    assert wait_for(lambda: events.of("interrupted"))
    assert events.of("interrupted")[0]["reason"] == "barge_in"
    assert wait_for(lambda: session.state == "listening")
    assert len(brain.requests) == 1                # no new turn without the key


def test_voice_barge_in_can_be_switched_off_in_push_to_talk():
    session, events, _brain, _tts, speaker = ptt_session(["Oh, sweetheart. " + "word " * 30 + "end."],
                                                         tts_kwargs={"seconds_per_word": 0.05}, voice_barge_in=False)
    session.push_to_talk(True)
    feed(session, speech(1, 20))
    session.push_to_talk(False)
    feed(session, quiet(3))
    assert wait_for(lambda: session.state == "speaking")
    feed(session, speech(2, 20))
    assert not events.of("interrupted")
    session.stop()


def test_push_to_talk_is_ignored_in_a_hands_free_call():
    events = Events()
    session = CallSession(vad=FakeVAD(), asr=FakeASR(TEXTS), brain=FakeBrain(["Hi."]), tts=FakeTTS(),
                          speaker=FakeSpeaker(), config=CallConfig(partial_transcripts=False), on_event=events)
    session.start()
    session.push_to_talk(True)
    assert session.state == "listening" and not events.of("speech_started")


# -- the bridge: consent, push-to-talk action, read-aloud ---------------------------------------
class ContextSpeaker(FakeSpeaker):
    instances: list = []

    def __init__(self):
        super().__init__()
        ContextSpeaker.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.stop()


class HeldMicrophone:
    """Room silence until closed; the test drives push-to-talk through the bridge."""

    def __init__(self, frames=None):
        self.closed = threading.Event()
        self.frames = frames if frames is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self):
        self.closed.set()

    def __iter__(self):
        while not self.closed.wait(0.004):
            yield (self.frames.pop(0) if self.frames else quiet(1)[0])


def make_bridge(tmp_path, mic=None, tts=None):
    events, saved = [], []
    tts = tts or FakeTTS(seconds_per_word=0.02)

    class Factories:
        @staticmethod
        def engines(settings, progress):
            return Engines(FakeVAD(), None, FakeASR({1: "hello star"}), tts, {})

        @staticmethod
        def brain(settings):
            return FakeBrain(["Hello, love."])

        @staticmethod
        def microphone(device):
            return mic or HeldMicrophone()

        @staticmethod
        def speaker(sample_rate, device):
            return ContextSpeaker()

        @staticmethod
        def tts(settings):
            return tts

        @staticmethod
        def devices():
            return []

    bridge = VoiceBridge(lambda call_id, data: events.append((call_id, data)), settings_path=tmp_path / "voice.json",
                         save_turn=lambda user, reply: saved.append((user, reply)), factories=Factories)
    return bridge, events, saved, tts


def types(events, request_id=None):
    return [d["type"] for rid, d in events if request_id is None or rid == request_id]


def test_a_call_needs_explicit_microphone_consent(tmp_path):
    bridge, _events, _saved, _tts = make_bridge(tmp_path)
    assert {"voicePushToTalk", "voiceSpeak", "voiceStopSpeaking"} <= VOICE_ACTIONS
    for body in ({}, {"micConsent": "yes"}, {"micConsent": 1}):
        with pytest.raises(PermissionError, match="microphone"):
            bridge.handle("voiceStartCall", body, "r1")
    assert bridge.handle("voiceStatus", {})["inCall"] is False


def test_push_to_talk_through_the_bridge_runs_a_turn_and_saves_it(tmp_path):
    frames = []
    bridge, events, saved, _tts = make_bridge(tmp_path, mic=HeldMicrophone(frames))
    with pytest.raises(RuntimeError, match="No voice call"):
        bridge.handle("voicePushToTalk", {"down": True})
    started = bridge.handle("voiceStartCall", {"micConsent": True}, "call-1")
    assert started["settings"]["call_mode"] == "push-to-talk"
    assert wait_for(lambda: bridge.handle("voiceStatus", {})["state"] == "listening")
    assert bridge.handle("voicePushToTalk", {"down": True}) == {"down": True}
    frames.extend(speech(1, 20))
    assert wait_for(lambda: not frames)
    assert bridge.handle("voicePushToTalk", {"down": False}) == {"down": False}
    assert wait_for(lambda: "turn_metrics" in types(events))
    assert saved == [("hello star", "Hello, love.")]
    metrics = [d for _r, d in events if d["type"] == "turn_metrics"][0]
    assert metrics["end_reason"] == "push_to_talk"
    json.dumps([d for _r, d in events])
    bridge.close()


def test_hands_free_call_refuses_push_to_talk(tmp_path):
    bridge, _events, _saved, _tts = make_bridge(tmp_path)
    bridge.handle("voiceStartCall", {"micConsent": True, "settings": {"call_mode": "hands-free"}}, "call-2")
    assert wait_for(lambda: bridge.handle("voiceStatus", {})["state"] == "listening")
    with pytest.raises(ValueError, match="hands-free"):
        bridge.handle("voicePushToTalk", {"down": True})
    bridge.close()


def test_read_aloud_speaks_the_spoken_version_sentence_by_sentence(tmp_path):
    bridge, events, _saved, tts = make_bridge(tmp_path)
    reply = "## Done\n\nYour shop **works** now.\n\n```lua\nprint('hi')\n```\n\nWell done, love!"
    result = bridge.handle("voiceSpeak", {"text": reply}, "say-1")
    assert result["speaking"] is True and result["voiceId"] == STAR_VOICE_ID
    assert wait_for(lambda: "speak_done" in types(events, "say-1"))
    assert tts.spoken == ["Done.", "Your shop works now.", CODE_POINTER, "Well done, love!"]
    kinds = types(events, "say-1")
    assert kinds[0] == "speak_started" and kinds[-1] == "speak_done"
    done = [d for r, d in events if r == "say-1" and d["type"] == "speak_done"][0]
    assert done["stopped"] is False and done["first_audio_seconds"] is not None
    assert bridge.handle("voiceStatus", {})["speaking"] is False
    with pytest.raises(ValueError, match="nothing"):
        bridge.handle("voiceSpeak", {"text": "```\ncode only is fine\n```"[:0]}, "say-2")


def test_stop_speaking_and_a_new_read_aloud_cut_the_old_one_short(tmp_path):
    slow = FakeTTS(seconds_per_word=0.3)
    bridge, events, _saved, _tts = make_bridge(tmp_path, tts=slow)
    long_reply = " ".join(f"Sentence {i} is here and it is long enough." for i in range(30))
    bridge.handle("voiceSpeak", {"text": long_reply}, "say-1")
    assert wait_for(lambda: "speak_started" in types(events, "say-1"))
    bridge.handle("voiceSpeak", {"text": "Hello again."}, "say-2")          # replaces the first
    assert wait_for(lambda: "speak_done" in types(events, "say-1"))
    first = [d for r, d in events if r == "say-1" and d["type"] == "speak_done"][0]
    assert first["stopped"] is True
    assert wait_for(lambda: "speak_done" in types(events, "say-2"))
    bridge.handle("voiceSpeak", {"text": long_reply}, "say-3")
    assert wait_for(lambda: "speak_started" in types(events, "say-3"))
    assert bridge.handle("voiceStopSpeaking", {}) == {"stopped": True}
    assert [d for r, d in events if r == "say-3" and d["type"] == "speak_done"][0]["stopped"] is True
    assert bridge.handle("voiceStopSpeaking", {}) == {"stopped": False}
    assert len(slow.spoken) < 30


def test_starting_a_call_stops_read_aloud_and_read_aloud_waits_during_a_call(tmp_path):
    slow = FakeTTS(seconds_per_word=0.3)
    bridge, events, _saved, _tts = make_bridge(tmp_path, tts=slow)
    bridge.handle("voiceSpeak", {"text": "One. " * 40}, "say-1")
    assert wait_for(lambda: "speak_started" in types(events, "say-1"))
    bridge.handle("voiceStartCall", {"micConsent": True}, "call-3")
    assert "speak_done" in types(events, "say-1")
    with pytest.raises(RuntimeError, match="on a call"):
        bridge.handle("voiceSpeak", {"text": "Hello."}, "say-2")
    bridge.close()


def test_file_driven_push_to_talk_call_holds_the_key_per_line_and_measures_from_release(tmp_path):
    from star.voice.filecall import FileCall, write_wav
    write_wav(tmp_path / "u1.wav", b"".join(speech(1, 18)), 16000)
    write_wav(tmp_path / "u3.wav", b"".join(speech(3, 16)), 16000)
    long = "Oh, of course, love. " + "Once upon a time there was a little star who loved to help. " * 6
    brain = FakeBrain([long, "Okay, a story it is."], delay=0.005)

    def make(speaker, on_event):
        config = CallConfig(turn=TurnConfig(), partial_transcripts=False, push_to_talk=True)
        return CallSession(vad=FakeVAD(), asr=FakeASR(TEXTS), brain=brain, tts=FakeTTS(seconds_per_word=0.03),
                           speaker=speaker, config=config, on_event=on_event)

    scenario = {"steps": [{"say": "u1.wav"}, {"wait": "speaking", "then_seconds": 0.4},
                          {"say": "u3.wav"}, {"wait": "reply_done", "then_seconds": 0.1}]}
    result = FileCall(make, base_dir=tmp_path, step_timeout=20).run(scenario)
    assert not result.timed_out
    first, second = result.turns
    assert first.end_reason == second.end_reason == "push_to_talk"
    assert first.interrupted and first.interrupt_reason == "push_to_talk"     # pressing the key cut her off
    assert second.user_text == TEXTS[3] and second.reply_text == "Okay, a story it is."
    assert all(m.stages()["endpoint"] < 0.3 for m in result.turns)            # only the 160 ms release tail


def test_read_aloud_is_held_to_the_chosen_voice_place_like_calls_and_previews():
    # A voice set to run elsewhere in Settings is refused for read-aloud too, never spoken on the PC instead.
    from star.react_shell import VOICE_PLACE_ACTIONS
    assert {"voiceStartCall", "voicePreviewVoice", "voiceSpeak"} <= VOICE_PLACE_ACTIONS <= VOICE_ACTIONS
