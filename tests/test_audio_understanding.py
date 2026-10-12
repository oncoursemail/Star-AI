"""Offline waveform/provenance contracts, not a model-comprehension benchmark."""
import asyncio
import base64
import hashlib
import io
import json
import math
import struct
import threading
import wave

import pytest

from star import audio_understanding as audio


def wav(pcm=None, *, frames=16000, rate=16000, channels=1):
    pcm = pcm if pcm is not None else struct.pack('<h', 1234) * frames * channels
    out = io.BytesIO()
    with wave.open(out, 'wb') as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm)
    return out.getvalue()


def decoded(raw):
    with wave.open(io.BytesIO(raw), 'rb') as stream:
        return stream.readframes(stream.getnframes()), stream.getframerate(), stream.getnchannels()


def source(**kwargs):
    return audio.AudioSource('attached_1', wav(**kwargs))


def backend(reply=None, **capability):
    requests = []

    async def analyze(request):
        requests.append(request)
        return reply(request) if callable(reply) else (reply if reply is not None else {'complete': True, 'observations': []})

    return audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True, **capability), analyze), requests


def run(src=None, question='Describe the sounds', registered=None, **kwargs):
    registered = registered if registered is not None else backend()[0]
    return asyncio.run(audio.inspect_audio(src or source(), question, registered, **kwargs))


def event(start=0, end=100, text='Unverified fixture observation', score=None):
    return {'start_frame': start, 'end_frame': end, 'text': text, 'score': score}


def test_same_transcript_different_waveforms_remain_different_native_inputs():
    def tone(hz):
        return b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * hz * i / 16000))) for i in range(16000))
    first, second = audio.AudioSource('tone_1', wav(tone(220))), audio.AudioSource('tone_2', wav(tone(880)))
    registered, requests = backend()
    results = [run(s, registered=registered, transcript_reference='The same fake ASR words.') for s in (first, second)]
    assert requests[0].transcript_reference == requests[1].transcript_reference
    assert requests[0].audio != requests[1].audio
    assert requests[0].clip_waveform_sha256 != requests[1].clip_waveform_sha256
    for s, request, result in zip((first, second), requests, results):
        assert decoded(request.audio) == (s.pcm, s.sample_rate, s.channels)
        assert result['source_sha256'] == hashlib.sha256(s.wav).hexdigest()
        assert result['waveform_sha256'] == hashlib.sha256(s.pcm).hexdigest()
        assert result['method'] == 'native_waveform_submitted' and result['reference_data_only']
        assert base64.b64encode(s.pcm).decode() not in json.dumps(result)
        assert not result['observations'] and result['unreported_ranges'] == [[0, s.frames]]
        assert 'not proof of comprehension' in result['coverage_meaning']


def test_stereo_exact_windows_tail_hash_and_source_timeline():
    pcm = struct.pack('<hh', 3000, -6000) * 40003
    src = audio.AudioSource('stereo', wav(pcm, channels=2, rate=8000), timeline_origin_frames=40000)
    registered, requests = backend(lambda r: {'complete': True, 'observations': [event(r.end_frame-r.start_frame-1, r.end_frame-r.start_frame)]},
                                    sample_rates=(8000,), max_clip_seconds=2)
    result = run(src, registered=registered, start_frame=7, end_frame=40003)
    assert [(r.start_frame, r.end_frame) for r in requests] == [(7, 16007), (16007, 32007), (32007, 40003)]
    assert b''.join(decoded(r.audio)[0] for r in requests) == pcm[7 * 4:40003 * 4]
    assert all(decoded(r.audio)[1:] == (8000, 2) for r in requests)
    assert result['unsubmitted_ranges'] == [[0, 7]]
    assert result['observations'][-1]['timeline_end_frames'] == 80003
    assert result['observations'][-1]['end_frame'] == 40003
    for r, span in zip(requests, result['submitted_ranges']):
        assert span['submitted_sha256'] == hashlib.sha256(r.audio).hexdigest()
        assert span['waveform_sha256'] == hashlib.sha256(decoded(r.audio)[0]).hexdigest()


def test_total_job_is_30_seconds_with_at_most_30_windows_and_explicit_tail():
    src = source(rate=8000, frames=8000 * 35)
    registered, requests = backend(sample_rates=(8000,), max_clip_seconds=1)
    result = run(src, registered=registered)
    assert len(requests) == 30 and requests[-1].end_frame == 8000 * 30
    assert result['unsubmitted_ranges'] == [[8000 * 30, 8000 * 35]]
    with pytest.raises(ValueError, match='30 seconds'):
        run(src, registered=registered, end_frame=src.frames)
    assert len(requests) == 30  # refused before a second job was dispatched


def test_packed_pcm_preserves_silence_and_nonspeech_without_asr():
    src = audio.AudioSource('quiet', wav(b'\0\0' * 16000))
    registered, requests = backend(input_format='pcm16_le')
    result = run(src, registered=registered)
    assert requests[0].audio == src.pcm and requests[0].input_format == 'pcm16_le'
    assert result['unreported_ranges'] == [[0, 16000]]


def test_overlapping_sound_events_are_valid_but_coverage_is_nonoverlapping():
    observations = [event(200, 600, 'Alarm', 0.7), event(0, 1000, 'Music'), event(700, 900, 'Voice')]
    result = run(registered=backend({'complete': True, 'observations': observations})[0])
    assert [x['text'] for x in result['observations']] == ['Music', 'Alarm', 'Voice']
    assert result['unreported_ranges'] == [[1000, 16000]]
    assert result['observations'][1]['score_status'] == 'uncalibrated'
    assert result['observations'][0]['score_status'] == 'not_reported'
    assert 'not a probability' in result['score_meaning']


def altered(raw, offset, value, fmt='<I'):
    result = bytearray(raw)
    struct.pack_into(fmt, result, offset, value)
    return bytes(result)


@pytest.mark.parametrize('raw', [
    b'not WAV', bytearray(wav()), wav()[:-1], wav() + b'extra',
    altered(wav(), 4, 4000000), altered(wav(), 40, 4000000),
    altered(wav(), 20, 3, '<H'), altered(wav(), 22, 3, '<H'),
    altered(wav(), 24, 44101), altered(wav(), 28, 1),
    altered(wav(), 32, 1, '<H'), altered(wav(), 34, 32, '<H'),
    wav(b'\0', channels=1), wav(frames=0),
], ids=lambda _: 'invalid_wav')
def test_malformed_headers_encodings_and_advertised_frame_lengths_are_rejected(raw):
    with pytest.raises(ValueError):
        audio.AudioSource('bad', raw)


def test_source_size_duration_duplicate_and_metadata_chunk_bounds():
    with pytest.raises(ValueError, match='8 MiB'):
        audio.AudioSource('big', b'x' * (audio.MAX_SOURCE_BYTES + 1))
    with pytest.raises(ValueError, match='120 seconds'):
        source(rate=8000, frames=8000 * 120 + 1)
    valid = wav()
    for chunks in (valid[12:36] + valid[12:36] + valid[36:], valid[12:] + valid[36:]):
        raw = b'RIFF' + struct.pack('<I', 4 + len(chunks)) + b'WAVE' + chunks
        with pytest.raises(ValueError, match='duplicate'):
            audio.AudioSource('duplicate', raw)
    chunks = b'JUNK\0\0\0\0' * 129 + valid[12:]
    with pytest.raises(ValueError, match='Too many WAV chunks'):
        audio.AudioSource('many', b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks)
    chunks = b'JUNK\1\0\0\0x\0' + valid[12:]
    raw = b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks
    assert audio.AudioSource('metadata', raw).pcm == audio.AudioSource('plain', valid).pcm


@pytest.mark.parametrize('value', [None, False, object()])
def test_absent_unknown_or_asr_only_backend_is_unavailable(value):
    if value is False:
        value = audio.RegisteredAudioBackend(audio.AudioCapability('asr', 'fake_asr'), lambda _: None)
    with pytest.raises(audio.AudioUnavailable, match='host-registered native'):
        asyncio.run(audio.inspect_audio(source(), 'Sounds?', value))


@pytest.mark.parametrize('kwargs', [
    {'start_frame': -1}, {'start_frame': True}, {'start_frame': float('nan')},
    {'end_frame': 0}, {'end_frame': 16001}, {'end_frame': float('inf')},
    {'timeout_seconds': float('nan')}, {'timeout_seconds': True}, {'timeout_seconds': 121},
    {'transcript_reference': 'x' * 3001},
])
def test_invalid_request_bounds_do_not_dispatch(kwargs):
    registered, requests = backend()
    with pytest.raises(ValueError):
        run(registered=registered, **kwargs)
    assert not requests


def test_backend_constraints_never_silently_resample_or_downmix():
    for src, kwargs in ((source(rate=8000), {}), (source(channels=2), {'channels': (1,)})):
        registered, requests = backend(**kwargs)
        with pytest.raises(audio.AudioUnavailable, match='rate or channel'):
            run(src, registered=registered)
        assert not requests
    for kwargs in ({'input_format': 'mp3'}, {'max_clip_seconds': 0}, {'sample_rates': (True,)}, {'channels': (3,)}):
        with pytest.raises(ValueError):
            backend(**kwargs)


@pytest.mark.parametrize('reply', [
    {'complete': False, 'observations': []}, {'observations': []},
    {'complete': True, 'observations': [], 'extra': 'unbounded'},
    {'complete': True, 'observations': 'wrong'},
    {'complete': True, 'observations': [event()] * 31},
    *[{'complete': True, 'observations': [item]} for item in (
        event(-1, 10), event(1, 1), event(0, 16001), event(float('nan'), 10),
        event(0, float('inf')), event(True, 10), event(text=''), event(text='x' * 501),
        event(score=float('nan')), event(score=float('inf')), event(score=True), event(score=1.1),
        {'start_frame': 0, 'end_frame': 10, 'text': 'x', 'source_id': 'forged'},
    )],
])
def test_truncated_malformed_or_unbounded_backend_output_is_not_accepted(reply):
    with pytest.raises(audio.AudioUnavailable):
        run(registered=backend(reply)[0])


def test_aggregate_output_bound_and_no_automatic_replay_after_failure():
    registered, requests = backend(lambda _: {'complete': True, 'observations': [event(text='x' * 500)] * 30})
    with pytest.raises(audio.AudioUnavailable, match='output bound'):
        run(registered=registered)
    assert len(requests) == 1
    registered, requests = backend(lambda r: {'complete': r.start_frame == 0, 'observations': []}, max_clip_seconds=1)
    with pytest.raises(audio.AudioUnavailable, match='incomplete'):
        run(source(frames=16000 * 3), registered=registered)
    assert [(r.start_frame, r.end_frame) for r in requests] == [(0, 16000), (16000, 32000)]


@pytest.mark.parametrize('exception', [ValueError('Sensitive fixture diagnostic'), audio.AudioUnavailable('Sensitive fixture diagnostic')])
def test_backend_diagnostics_are_generic_and_no_retry(exception):
    calls = []
    async def failing(request):
        calls.append(request)
        raise exception
    registered = audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True), failing)
    with pytest.raises(audio.AudioUnavailable) as result:
        run(registered=registered)
    assert str(result.value) == 'Native audio backend failed' and len(calls) == 1


def test_cancellation_before_and_after_dispatch_remains_cancellation():
    flag = threading.Event()
    flag.set()
    registered, requests = backend()
    with pytest.raises(asyncio.CancelledError):
        run(registered=registered, cancel_event=flag)
    assert not requests
    flag.clear()
    def cancel_reply(_):
        flag.set()
        return {'complete': True, 'observations': []}
    registered, requests = backend(cancel_reply)
    with pytest.raises(asyncio.CancelledError):
        run(registered=registered, cancel_event=flag)
    assert len(requests) == 1


@pytest.mark.parametrize('timeout', [False, True])
def test_waiting_cancellation_or_deadline_cleans_up_owned_task(timeout):
    async def scenario():
        started, cleaned = asyncio.Event(), asyncio.Event()
        calls = []
        async def waiting(request):
            calls.append(request)
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        registered = audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True), waiting)
        task = asyncio.create_task(audio.inspect_audio(source(), 'Sounds?', registered, timeout_seconds=0.03 if timeout else 30))
        await started.wait()
        if not timeout:
            task.cancel()
        with pytest.raises(audio.AudioUnavailable if timeout else asyncio.CancelledError):
            await task
        assert cleaned.is_set() and len(calls) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('question', ['', '   ', None, 'x' * 2001, ' ' * 2001 + 'x'],
                         ids=['empty', 'space', 'none', 'oversize', 'padded'])
def test_question_is_bounded_before_dispatch(question):
    registered, requests = backend()
    with pytest.raises(ValueError):
        run(question=question, registered=registered)
    assert not requests


@pytest.mark.parametrize('source_id, origin', [('path/to/wav', 0), ('x' * 81, 0), ('good', -1),
                                             ('good', True), ('good', float('nan')), ('good', 16000 * 5400 + 1)])
def test_source_identity_and_timeline_are_host_bounded(source_id, origin):
    with pytest.raises(ValueError):
        audio.AudioSource(source_id, wav(), timeline_origin_frames=origin)


def test_header_metadata_does_not_change_pcm_hash_and_source_cannot_assert_hash():
    ordinary = wav()
    chunks = b'JUNK\x02\0\0\0xx' + ordinary[12:]
    changed = b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks
    first, second = audio.AudioSource('one', ordinary), audio.AudioSource('two', changed)
    assert first.source_sha256 != second.source_sha256 and first.waveform_sha256 == second.waveform_sha256
    with pytest.raises(TypeError):
        audio.AudioSource('forged', ordinary, waveform_sha256='caller assertion')
    assert 'RIFF' not in repr(first) and '\\xd2' not in repr(first)


def test_synchronous_backend_results_are_refused_without_retry():
    calls = []
    def sync(request):
        calls.append(request)
        return {'complete': True, 'observations': []}
    registered = audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True), sync)
    with pytest.raises(audio.AudioUnavailable, match='asynchronous'):
        run(registered=registered)
    assert len(calls) == 1


def test_flag_cancellation_while_waiting_cancels_backend_and_preserves_cancelled_error():
    async def scenario():
        flag, started, cleaned = threading.Event(), asyncio.Event(), asyncio.Event()
        calls = []
        async def waiting(request):
            calls.append(request)
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        registered = audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True), waiting)
        task = asyncio.create_task(audio.inspect_audio(source(frames=32000), 'Sounds?', registered, cancel_event=flag))
        await started.wait()
        flag.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set() and len(calls) == 1
    asyncio.run(scenario())


def test_deadline_uses_one_budget_for_all_windows():
    async def scenario():
        calls = []
        async def slow(request):
            calls.append(request)
            await asyncio.sleep(0.035)
            return {'complete': True, 'observations': []}
        registered = audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True, max_clip_seconds=1), slow)
        with pytest.raises(audio.AudioUnavailable, match='timed out'):
            await audio.inspect_audio(source(frames=48000), 'Sounds?', registered, timeout_seconds=0.05)
        assert len(calls) == 2
    asyncio.run(scenario())


def test_uncooperative_adapter_does_not_make_deadline_cleanup_wait_forever():
    async def scenario():
        release, cancelled, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls = []
        async def stubborn(request):
            calls.append(request)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
            finally:
                cleaned.set()
            return {'complete': True, 'observations': []}
        registered = audio.RegisteredAudioBackend(audio.AudioCapability('fixture', 'fake_native', native_audio=True), stubborn)
        task = asyncio.create_task(audio.inspect_audio(source(), 'Sounds?', registered, timeout_seconds=0.03))
        try:
            with pytest.raises(audio.AudioUnavailable, match='timed out'):
                await asyncio.wait_for(task, timeout=0.25)
            assert cancelled.is_set() and not cleaned.is_set() and len(calls) == 1
        finally:
            release.set()  # host cleanup: Python cannot forcibly terminate an injected coroutine
            await asyncio.wait_for(cleaned.wait(), timeout=0.25)
    asyncio.run(scenario())
