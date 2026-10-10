"""Turn-taking logic for voice calls: speech probabilities in, turn events out.

Each 32 ms microphone frame comes with a speech probability from the voice-activity detector. This
module decides when the user started talking, when they paused, when their turn is over, and when
speech during the assistant's reply is a real interruption (barge-in) rather than a cough or the
loudspeaker's own echo.

End of turn uses two layers, the way current voice agents do:
1. a short pause (pause_ms) triggers an optional end-of-turn model that listens to *how* the sentence
   ended (falling pitch, finished phrase) and can end the turn immediately;
2. plain silence ends the turn anyway: end_silence_ms without a model, max_silence_ms when the model
   said "they are not finished".

Pure Python and deterministic (time comes from the caller), so the unit tests need no audio stack.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol

from .pcm import FRAME_MS


@dataclass
class TurnConfig:
    start_threshold: float = 0.5       # speech probability that counts as "talking"
    end_threshold: float = 0.35        # below this the frame counts as silence (hysteresis)
    min_speech_ms: int = 96            # voiced time needed to open a turn
    pre_roll_ms: int = 320             # audio kept from before the turn opened, so first words are not clipped
    pause_ms: int = 256                # silence that counts as a pause: speculative transcript + end-of-turn model
    end_silence_ms: int = 640          # silence that ends the turn when there is no end-of-turn model
    max_silence_ms: int = 2000         # silence that ends the turn even if the model says "not finished"
    complete_threshold: float = 0.5    # end-of-turn model probability that ends the turn at the pause
    resume_ms: int = 64                # voiced time that turns a pause back into speech
    barge_in_ms: int = 288             # voiced time needed to interrupt the assistant
    barge_in_threshold: float = 0.6    # stricter probability while the assistant is audible
    min_turn_ms: int = 160             # turns with less voiced audio than this are dropped as noise
    max_turn_ms: int = 30000           # safety cap on one user turn


class Endpointer(Protocol):
    """Optional end-of-turn model: probability (0..1) that the speaker has finished their turn."""

    def complete_probability(self, pcm: bytes) -> float: ...


@dataclass
class TurnEvent:
    kind: str                  # speech_start | pause | resume | turn_end | discard
    at: float                  # caller's clock when the event fired
    audio: bytes = b""         # pause / turn_end: the user's audio so far (PCM16, 16 kHz, mono)
    barge_in: bool = False     # speech_start: the assistant was audible when the user began
    speech_end: float = 0.0    # pause / turn_end: clock time of the last voiced frame
    complete_probability: float | None = None   # what the end-of-turn model said, if one ran
    reason: str = ""           # turn_end: model | silence | max_silence | max_turn


class TurnDetector:
    IDLE, SPEECH, PAUSE = "idle", "speech", "pause"

    def __init__(self, config: TurnConfig | None = None, endpointer: Endpointer | None = None) -> None:
        self.config = config or TurnConfig()
        self.endpointer = endpointer
        self.state = self.IDLE
        self._pre_roll: deque[bytes] = deque(maxlen=max(1, self.config.pre_roll_ms // FRAME_MS))
        self._frames: list[bytes] = []
        self._run_ms = 0           # voiced run while idle / paused
        self._silence_ms = 0
        self._voiced_ms = 0
        self._turn_ms = 0
        self._last_voiced = 0.0
        self._model_says_open = False

    # -- public API -------------------------------------------------------------------------
    def process(self, frame: bytes, probability: float, now: float, *, assistant_active: bool = False,
                gate_open: bool = True) -> list[TurnEvent]:
        """Feed one frame. gate_open=False vetoes barge-in (e.g. the echo gate says "that is our own audio")."""
        if self.state == self.IDLE:
            return self._idle(frame, probability, now, assistant_active, gate_open)
        if self.state == self.SPEECH:
            return self._speech(frame, probability, now)
        return self._pause(frame, probability, now)

    def reset(self) -> None:
        self.state = self.IDLE
        self._pre_roll.clear()
        self._frames = []
        self._run_ms = self._silence_ms = self._voiced_ms = self._turn_ms = 0
        self._model_says_open = False

    @property
    def audio(self) -> bytes:
        """The current turn's audio so far (empty while idle)."""
        return b"".join(self._frames)

    # -- states -----------------------------------------------------------------------------
    def _idle(self, frame, probability, now, assistant_active, gate_open) -> list[TurnEvent]:
        cfg = self.config
        self._pre_roll.append(frame)
        threshold = cfg.barge_in_threshold if assistant_active else cfg.start_threshold
        voiced = probability >= threshold and (gate_open or not assistant_active)
        # A missed frame costs one frame of credit instead of resetting, so natural gaps
        # inside a word do not stop a real interruption from being recognised.
        self._run_ms = self._run_ms + FRAME_MS if voiced else max(0, self._run_ms - FRAME_MS)
        needed = cfg.barge_in_ms if assistant_active else cfg.min_speech_ms
        if self._run_ms < needed:
            return []
        self.state = self.SPEECH
        self._frames = list(self._pre_roll)
        self._pre_roll.clear()
        self._voiced_ms = self._run_ms
        self._turn_ms = len(self._frames) * FRAME_MS
        self._run_ms = self._silence_ms = 0
        self._last_voiced = now
        self._model_says_open = False
        return [TurnEvent("speech_start", now, barge_in=assistant_active)]

    def _speech(self, frame, probability, now) -> list[TurnEvent]:
        cfg = self.config
        self._frames.append(frame)
        self._turn_ms += FRAME_MS
        if probability >= cfg.end_threshold:
            self._silence_ms = 0
            self._voiced_ms += FRAME_MS
            self._last_voiced = now
        else:
            self._silence_ms += FRAME_MS
        if self._turn_ms >= cfg.max_turn_ms:
            return [self._end(now, "max_turn", None)]
        if self._silence_ms < cfg.pause_ms:
            return []
        self.state = self.PAUSE
        self._run_ms = 0
        events = [TurnEvent("pause", now, audio=self.audio, speech_end=self._last_voiced)]
        probability_complete = None
        if self.endpointer is not None:
            try:
                probability_complete = float(self.endpointer.complete_probability(self.audio))
            except Exception:
                probability_complete = None        # a broken model must never block the call: fall back to silence
        events[0].complete_probability = probability_complete
        if probability_complete is None:
            self._model_says_open = False
        elif probability_complete >= cfg.complete_threshold:
            events.append(self._end(now, "model", probability_complete))
        else:
            self._model_says_open = True
        return events

    def _pause(self, frame, probability, now) -> list[TurnEvent]:
        cfg = self.config
        self._frames.append(frame)
        self._turn_ms += FRAME_MS
        if probability >= cfg.start_threshold:
            self._run_ms += FRAME_MS
            if self._run_ms >= cfg.resume_ms:
                self.state = self.SPEECH
                self._voiced_ms += self._run_ms
                self._silence_ms = self._run_ms = 0
                self._last_voiced = now
                return [TurnEvent("resume", now)]
            return []
        self._run_ms = 0
        self._silence_ms += FRAME_MS
        limit = cfg.max_silence_ms if self._model_says_open else cfg.end_silence_ms
        if self._silence_ms >= limit:
            return [self._end(now, "max_silence" if self._model_says_open else "silence", None)]
        return []

    def _end(self, now: float, reason: str, probability_complete: float | None) -> TurnEvent:
        audio, voiced, last = self.audio, self._voiced_ms, self._last_voiced
        self.reset()
        if voiced < self.config.min_turn_ms:
            return TurnEvent("discard", now, speech_end=last, reason="too_short")
        return TurnEvent("turn_end", now, audio=audio, speech_end=last,
                         complete_probability=probability_complete, reason=reason)


class EchoGate:
    """Tells the user's voice apart from the loudspeaker's echo by loudness, for calls without headphones.

    While the assistant is audible the microphone also hears the assistant. The gate learns how loud that
    echo is relative to what is being played (the coupling) and only lets barge-in through when the
    microphone is clearly louder than the echo alone would be. This is a simple energy gate, not echo
    cancellation: it stops the assistant from interrupting itself but needs the user to speak up over it.
    """

    def __init__(self, margin_db: float = 8.0, floor: float = 0.006, warmup_frames: int = 8) -> None:
        self.margin = 10 ** (margin_db / 20.0)
        self.floor = floor
        self.warmup_frames = warmup_frames
        self.coupling: float | None = None
        self._warm: list[float] = []

    def allows(self, mic_level: float, speaker_level: float) -> bool:
        if speaker_level <= 1e-4:                      # nothing is playing: nothing to confuse it with
            return mic_level >= self.floor
        ratio = mic_level / speaker_level
        if self.coupling is None:
            self._warm.append(ratio)
            if len(self._warm) >= self.warmup_frames:
                self.coupling = sorted(self._warm)[len(self._warm) // 2]
                self._warm = []
            return False                               # no barge-in until the echo level is known
        allowed = mic_level >= max(self.floor, self.coupling * speaker_level * self.margin)
        # Follow the echo level quickly downwards and slowly upwards, so the user's own (louder)
        # speech does not teach the gate that the echo is loud.
        rate = 0.2 if ratio < self.coupling else 0.01
        self.coupling += rate * (ratio - self.coupling)
        return allowed
