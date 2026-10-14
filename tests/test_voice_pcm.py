"""PCM16 conversion, padding and duration edge cases with no audio drivers."""
import struct

import pytest

from star.voice import pcm


def test_samples_decode_signed_little_endian_values_and_ignore_trailing_byte():
    payload = struct.pack("<hhhh", -32768, -1, 0, 32767)
    assert pcm.samples(payload).tolist() == [-32768, -1, 0, 32767]
    assert pcm.samples(payload + b"\xff").tolist() == [-32768, -1, 0, 32767]
    assert pcm.samples(b"").tolist() == []


def test_rms_uses_full_scale_pcm16_and_handles_empty_or_odd_data():
    assert pcm.rms(b"") == 0.0
    assert pcm.rms(b"\x00") == 0.0
    assert pcm.rms(struct.pack("<h", -32768)) == pytest.approx(1.0)
    assert pcm.rms(struct.pack("<hh", 32767, -32768)) == pytest.approx(
        ((32767 ** 2 + 32768 ** 2) / 2) ** 0.5 / 32768
    )
    assert pcm.rms(b"\x00\x00\xff") == 0.0


def test_seconds_counts_pcm_samples_and_rejects_zero_sample_rate():
    assert pcm.seconds(b"", pcm.SAMPLE_RATE) == 0.0
    assert pcm.seconds(b"\x00\x00" * pcm.SAMPLE_RATE, pcm.SAMPLE_RATE) == 1.0
    assert pcm.seconds(b"\x00", pcm.SAMPLE_RATE) == pytest.approx(0.5 / pcm.SAMPLE_RATE)
    with pytest.raises(ZeroDivisionError):
        pcm.seconds(b"\x00\x00", 0)


def test_silence_is_zero_pcm_at_requested_rate_and_duration():
    assert pcm.silence(0) == b""
    assert pcm.silence(-1) == b""
    assert pcm.silence(0.032) == b"\x00" * pcm.FRAME_BYTES
    assert len(pcm.silence(2, sample_rate=8000)) == 32000


def test_frames_pad_only_final_chunk_and_preserve_order():
    assert list(pcm.frames(b"", frame_bytes=4)) == []
    assert list(pcm.frames(b"abcd", frame_bytes=4)) == [b"abcd"]
    assert list(pcm.frames(b"abcdef", frame_bytes=4)) == [b"abcd", b"ef\x00\x00"]
    assert len(list(pcm.frames(b"\x01" * (pcm.FRAME_BYTES + 1)))) == 2


def test_frames_reject_zero_frame_size_instead_of_looping():
    with pytest.raises(ValueError):
        list(pcm.frames(b"abc", frame_bytes=0))


def test_samples_reject_non_bytes_input():
    with pytest.raises(TypeError):
        pcm.samples("not PCM bytes")
