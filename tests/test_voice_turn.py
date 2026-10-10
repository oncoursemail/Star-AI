"""Turn-taking: when a turn opens, pauses, ends, and when speech counts as an interruption."""
from star.voice.pcm import FRAME_BYTES, FRAME_MS
from star.voice.turn import EchoGate, TurnConfig, TurnDetector

FRAME = b"\x01\x00" * (FRAME_BYTES // 2)


class Feeder:
    """Feeds frames with a fake clock that advances one frame (32 ms) at a time."""

    def __init__(self, detector):
        self.detector, self.now, self.events = detector, 0.0, []

    def feed(self, probability, frames=1, **kwargs):
        new = []
        for _ in range(frames):
            self.now += FRAME_MS / 1000
            new += self.detector.process(FRAME, probability, self.now, **kwargs)
        self.events += new
        return new

    def kinds(self):
        return [e.kind for e in self.events]


def ms(value):
    return value // FRAME_MS


def test_turn_opens_after_enough_speech_and_keeps_the_pre_roll():
    f = Feeder(TurnDetector(TurnConfig(min_speech_ms=96, pre_roll_ms=320)))
    f.feed(0.0, 20)
    assert f.feed(0.9, 2) == []                       # 64 ms is not enough yet
    opened = f.feed(0.9, 1)
    assert [e.kind for e in opened] == ["speech_start"] and opened[0].barge_in is False
    assert len(f.detector.audio) == 10 * FRAME_BYTES  # 320 ms of pre-roll, including the 3 voiced frames


def test_silence_ends_the_turn_and_reports_when_speech_really_stopped():
    cfg = TurnConfig(pause_ms=256, end_silence_ms=640)
    f = Feeder(TurnDetector(cfg))
    f.feed(0.9, 20)
    speech_stopped_at = f.now
    assert f.feed(0.0, ms(256) - 1) == []
    pause = f.feed(0.0, 1)
    assert [e.kind for e in pause] == ["pause"] and pause[0].audio
    assert abs(pause[0].speech_end - speech_stopped_at) < 1e-9
    assert f.feed(0.0, ms(640) - ms(256) - 1) == []
    end = f.feed(0.0, 1)
    assert [e.kind for e in end] == ["turn_end"] and end[0].reason == "silence"
    assert abs(end[0].speech_end - speech_stopped_at) < 1e-9
    assert abs((end[0].at - end[0].speech_end) - 0.640) < 1e-6      # end_silence_ms counts from the last speech
    assert f.detector.state == TurnDetector.IDLE


def test_a_pause_in_the_middle_of_a_thought_does_not_end_the_turn():
    f = Feeder(TurnDetector(TurnConfig(pause_ms=256, end_silence_ms=640)))
    f.feed(0.9, 15)
    f.feed(0.0, ms(256) + 5)              # paused, but not for long enough
    f.feed(0.9, 3)                        # ...and carries on
    f.feed(0.9, 10)
    f.feed(0.0, ms(256) + ms(640))
    assert f.kinds() == ["speech_start", "pause", "resume", "pause", "turn_end"]
    turn = f.events[-1]
    assert len(turn.audio) > 40 * FRAME_BYTES       # both halves are in one turn


class Model:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), 0

    def complete_probability(self, pcm):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_end_of_turn_model_can_end_the_turn_at_the_pause():
    model = Model([0.93])
    f = Feeder(TurnDetector(TurnConfig(pause_ms=256), model))
    f.feed(0.9, 20)
    events = f.feed(0.0, ms(256))
    assert [e.kind for e in events] == ["pause", "turn_end"]
    assert events[1].reason == "model" and events[1].complete_probability == 0.93
    assert events[1].at - events[1].speech_end < 0.3          # far sooner than a fixed silence timer


def test_model_saying_not_finished_waits_longer_but_never_forever():
    model = Model([0.1, 0.2])
    cfg = TurnConfig(pause_ms=256, end_silence_ms=640, max_silence_ms=2000)
    f = Feeder(TurnDetector(cfg, model))
    f.feed(0.9, 20)
    f.feed(0.0, ms(256) + ms(640) + 5)                         # a fixed timer would have cut in here
    assert f.kinds() == ["speech_start", "pause"]
    f.feed(0.9, 10)                                            # the user finishes the thought
    f.feed(0.0, ms(256) + ms(2000))
    assert f.kinds() == ["speech_start", "pause", "resume", "pause", "turn_end"]
    assert f.events[-1].reason == "max_silence" and model.calls == 2


def test_a_broken_end_of_turn_model_falls_back_to_plain_silence():
    f = Feeder(TurnDetector(TurnConfig(pause_ms=256, end_silence_ms=640), Model([RuntimeError("boom")])))
    f.feed(0.9, 20)
    f.feed(0.0, ms(256) + ms(640))
    assert f.kinds() == ["speech_start", "pause", "turn_end"] and f.events[-1].reason == "silence"


def test_interrupting_the_assistant_needs_longer_and_clearer_speech():
    cfg = TurnConfig(min_speech_ms=96, barge_in_ms=288, barge_in_threshold=0.6)
    f = Feeder(TurnDetector(cfg))
    assert f.feed(0.9, 5, assistant_active=True) == []        # a cough: 160 ms
    f.feed(0.0, 10, assistant_active=True)
    assert f.feed(0.55, 20, assistant_active=True) == []      # speech-like but below the stricter threshold
    f.feed(0.0, 10, assistant_active=True)
    events = f.feed(0.9, ms(288), assistant_active=True)
    assert [e.kind for e in events] == ["speech_start"] and events[0].barge_in is True


def test_one_missed_frame_does_not_reset_an_interruption():
    f = Feeder(TurnDetector(TurnConfig(barge_in_ms=288)))
    f.feed(0.9, 5, assistant_active=True)
    f.feed(0.1, 1, assistant_active=True)                     # a stop consonant
    events = f.feed(0.9, 5, assistant_active=True)
    assert [e.kind for e in events] == ["speech_start"]


def test_echo_gate_veto_blocks_barge_in_only_while_the_assistant_is_audible():
    f = Feeder(TurnDetector(TurnConfig(barge_in_ms=288)))
    assert f.feed(0.95, 30, assistant_active=True, gate_open=False) == []
    events = f.feed(0.95, 3, assistant_active=False, gate_open=False)
    assert [e.kind for e in events] == ["speech_start"]


def test_noise_blips_are_discarded_and_runaway_turns_are_capped():
    f = Feeder(TurnDetector(TurnConfig(min_speech_ms=64, min_turn_ms=200, pause_ms=256, end_silence_ms=640)))
    f.feed(0.9, 2)
    f.feed(0.0, ms(256) + ms(640))
    assert f.kinds() == ["speech_start", "pause", "discard"]
    g = Feeder(TurnDetector(TurnConfig(max_turn_ms=3200)))
    g.feed(0.9, 200)
    assert g.kinds()[:2] == ["speech_start", "turn_end"] and g.events[1].reason == "max_turn"


def test_echo_gate_learns_the_echo_level_then_lets_only_louder_speech_through():
    gate = EchoGate(margin_db=8.0, warmup_frames=8)
    speaker = 0.2
    echo = speaker * 0.1                                       # the room returns a tenth of what is played
    assert not any(gate.allows(echo, speaker) for _ in range(8))        # warming up: never open
    assert abs(gate.coupling - 0.1) < 1e-6
    assert not any(gate.allows(echo * 1.3, speaker) for _ in range(50))  # echo alone, with some wobble
    assert gate.allows(echo * 4, speaker)                                # the user speaking over it
    for _ in range(30):
        gate.allows(echo * 4, speaker)                                   # sustained user speech...
    assert gate.coupling < 0.2                                           # ...barely moves the echo estimate
    assert gate.allows(0.02, 0.0) and not gate.allows(0.001, 0.0)        # nothing playing: plain floor
