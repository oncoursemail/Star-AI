"""File-driven calls: the scripted caller, the virtual speaker, and the loudspeaker-echo simulation."""
import json
import time

import pytest

from star.voice.call import CallConfig, CallSession
from star.voice.filecall import FileCall, VirtualSpeaker, nearest_resample, read_wav, write_wav
from star.voice.pcm import rms
from star.voice.turn import TurnConfig
from voice_fakes import FakeASR, FakeBrain, FakeTTS, FakeVAD, speech

TEXTS = {1: "tell me a long story", 2: "stop please"}
SCENARIO = {"steps": [
    {"say": "u1.wav"}, {"wait": "reply_done", "then_seconds": 0.1},
    {"say": "u1.wav"}, {"wait": "speaking", "then_seconds": 0.4},
    {"say": "u2.wav"}, {"wait": "reply_done", "then_seconds": 0.1},
]}
LONG = "Oh, of course. " + "Once upon a time there was a little star who loved to help. " * 6


def write_inputs(folder):
    write_wav(folder / "u1.wav", b"".join(speech(1, 18)), 16000)
    write_wav(folder / "u2.wav", b"".join(speech(2, 16)), 16000)


def run(tmp_path, *, echo_db=None, gate=False, replies=(LONG, LONG, "Okay, I'll stop.")):
    write_inputs(tmp_path)
    brain = FakeBrain(list(replies), delay=0.005)

    def make(speaker, on_event):
        config = CallConfig(turn=TurnConfig(), partial_transcripts=False, use_echo_gate=gate)
        return CallSession(vad=FakeVAD(), asr=FakeASR(TEXTS), brain=brain, tts=FakeTTS(seconds_per_word=0.03),
                           speaker=speaker, config=config, on_event=on_event)

    call = FileCall(make, echo_db=echo_db, base_dir=tmp_path, step_timeout=20)
    return call.run(SCENARIO), brain


def test_scripted_call_runs_turns_and_a_barge_in_and_saves_everything(tmp_path):
    result, brain = run(tmp_path)
    assert not result.timed_out
    assert [m.user_text for m in result.turns] == [TEXTS[1], TEXTS[1], TEXTS[2]]
    first, second, third = result.turns
    assert not first.interrupted and second.interrupted and second.interrupt_reason == "barge_in"
    assert 0.3 < second.heard_seconds < second.audio_seconds          # cut while speaking, not before or after
    assert third.reply_text == "Okay, I'll stop." and not third.interrupted
    assert all(m.stages()["total"] is not None and m.stages()["total"] < 2.0 for m in result.turns)
    assert [name for name, _at in result.said] == ["u1.wav", "u1.wav", "u2.wav"]

    result.save(tmp_path / "out")
    saved = json.loads((tmp_path / "out" / "turns.json").read_text(encoding="utf-8"))
    assert len(saved["turns"]) == 3 and saved["turns"][1]["interrupted"] is True
    assert any(e["type"] == "interrupted" for e in saved["events"])
    assert "TOTAL" in (tmp_path / "out" / "latency.txt").read_text(encoding="utf-8")
    user_pcm, user_rate = read_wav(tmp_path / "out" / "user.wav")
    star_pcm, star_rate = read_wav(tmp_path / "out" / "star.wav")
    assert user_rate == 16000 and star_rate == 16000 and len(user_pcm) > 16000 and len(star_pcm) > 16000
    # The recording holds what was audible: the interrupted reply was cut, so less sound than was synthesised.
    audible = sum(1 for i in range(0, len(star_pcm), 2) if star_pcm[i:i + 2] != b"\x00\x00") / star_rate
    synthesised = sum(m.audio_seconds for m in result.turns)
    assert audible < synthesised - 0.2
    assert abs(audible - sum(m.heard_seconds if m.interrupted else m.audio_seconds for m in result.turns)) < 0.25


def test_loudspeaker_echo_makes_star_interrupt_herself_unless_the_echo_gate_is_on(tmp_path):
    # Without the gate the fake VAD hears Star's own voice in the microphone and "barges in" on her.
    plain, _ = run(tmp_path, echo_db=-12.0, gate=False)
    assert plain.turns[0].interrupted

    gated, _ = run(tmp_path, echo_db=-12.0, gate=True)
    assert not gated.timed_out
    assert [m.user_text for m in gated.turns] == [TEXTS[1], TEXTS[1], TEXTS[2]]
    assert not gated.turns[0].interrupted                             # her own echo no longer interrupts her
    assert gated.turns[1].interrupted and gated.turns[1].interrupt_reason == "barge_in"   # a real voice still does


class _ManualClock:
    """A clock that only moves when the test says so."""
    def __init__(self, start: float = 100.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


LOW = bytes([0x10, 0x00])                           # one PCM16 sample of a quiet tone
HIGH = bytes([0x20, 0x00])
SILENCE = bytes([0x00, 0x00])


def test_virtual_speaker_plays_in_real_time_and_stop_cuts_the_recording():
    # A manual clock instead of time.sleep: the old wall-clock version failed when a busy
    # machine overslept the 0.25 s pause past the 0.45 s upper bound.
    clock = _ManualClock()
    speaker = VirtualSpeaker(clock=clock)
    origin = clock()
    tone = LOW * 8000                               # 0.5 s at 16 kHz
    speaker.play(tone, 16000)
    speaker.play(tone, 16000)                       # queued behind the first, not mixed over it
    assert speaker.pending_seconds() == pytest.approx(1.0) and speaker.played_seconds() == 0
    clock.now += 0.25
    assert speaker.level() > 0
    assert rms(speaker.audible(clock(), 0.032, 16000)) > 0
    assert speaker.played_seconds() == pytest.approx(0.25)
    speaker.stop()
    assert speaker.pending_seconds() == 0 and speaker.played_seconds() == pytest.approx(0.25)
    recording, rate = speaker.recording(origin)
    assert rate == 16000 and len(recording) == 2 * 4000   # only the 0.25 s heard before the stop
    clock.now += 0.5                                       # past the 0.4 s level hold
    assert speaker.level() == 0 and rms(speaker.audible(clock(), 0.032, 16000)) == 0
    speaker.reset()
    assert speaker.played_seconds() == 0


def test_virtual_speaker_keeps_real_gaps_between_separate_utterances():
    # Durations are binary fractions (1/8 s, 3/8 s) so the sample arithmetic is exact.
    clock = _ManualClock()
    speaker = VirtualSpeaker(clock=clock)
    origin = clock()
    speaker.play(LOW * 2000, 16000)                 # 0.125 s
    clock.now += 0.375                              # 0.25 s of silence after it finished
    speaker.play(HIGH * 2000, 16000)
    clock.now += 0.125
    recording, rate = speaker.recording(origin)
    assert rate == 16000 and len(recording) == 2 * 8000
    assert recording[:2 * 2000] == LOW * 2000
    assert recording[2 * 2000:2 * 6000] == SILENCE * 4000
    assert recording[2 * 6000:] == HIGH * 2000
    assert speaker.pending_seconds() == 0 and speaker.played_seconds() == pytest.approx(0.25)


def test_stopping_before_queued_audio_starts_drops_it_from_the_recording():
    clock = _ManualClock()
    speaker = VirtualSpeaker(clock=clock)
    origin = clock()
    speaker.play(LOW * 2000, 16000)                 # plays 0 to 0.125 s
    speaker.play(HIGH * 2000, 16000)                # queued for 0.125 to 0.25 s
    clock.now += 0.0625
    speaker.stop()
    recording, _ = speaker.recording(origin)
    assert recording == LOW * 1000                  # half of the first clip, none of the second
    assert speaker.played_seconds() == pytest.approx(0.0625)


def test_wav_helpers_round_trip_and_resample(tmp_path):
    pcm = b"".join(speech(3, 4))
    write_wav(tmp_path / "a.wav", pcm, 16000)
    assert read_wav(tmp_path / "a.wav") == (pcm, 16000)
    assert len(nearest_resample(pcm, 16000, 8000)) == len(pcm) // 2
    assert len(nearest_resample(pcm, 24000, 16000)) == len(pcm) * 2 // 3 // 2 * 2
