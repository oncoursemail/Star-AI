"""Offline regression for per-request answer statistics after a tool step."""
import asyncio
from types import SimpleNamespace

import pytest

import star.agent as agent


def chunk(text='', *, tool=False, tokens=None):
    parts = [SimpleNamespace(index=0, id='read-1', function=SimpleNamespace(
        name='test_read', arguments='{}'))] if tool else []
    choices = [SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=parts))]
    if tokens is not None:
        choices = []
    return SimpleNamespace(choices=choices, model='reported-model',
                           usage=SimpleNamespace(completion_tokens=tokens))


class TimedStream:
    def __init__(self, clock, chunks):
        self.clock = clock
        self.chunks = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            when, value = next(self.chunks)
        except StopIteration:
            raise StopAsyncIteration
        self.clock.now = when
        return value


class ReadTool:
    def __init__(self):
        self.calls = []

    def definitions(self, prompt):
        return [{'name': 'test_read', 'description': 'Read fixture data.',
                 'inputSchema': {'type': 'object', 'properties': {},
                                 'additionalProperties': False}}]

    def owns(self, name):
        return name == 'test_read'

    def call(self, name, args, *, enabled):
        assert name in enabled and args == {}
        self.calls.append(name)
        return {'value': 'fixture data'}


@pytest.mark.parametrize('final_kind', ['estimated', 'reported', 'nonstream'])
def test_model_answered_uses_only_the_final_step(monkeypatch, final_kind):
    clock = SimpleNamespace(now=10.0)
    monkeypatch.setattr(agent, 'monotonic', lambda: clock.now)
    events = []
    requests = []
    tool = ReadTool()

    def on_event(event):
        events.append(event)
        if event['event'] == 'model_turn':
            # Set the clock before the real execute() captures request start.
            clock.now = 10.0 * event['step']

    class Completions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            assert kwargs['stream'] is True
            if len(requests) == 1:
                return TimedStream(clock, [
                    (10.125, chunk('A long preliminary observation. ' * 20)),
                    (10.25, chunk(tool=True)),
                    (10.5, chunk(tokens=400)),
                ])
            assert len(requests) == 2
            if final_kind == 'nonstream':
                return SimpleNamespace(model='reported-model', choices=[SimpleNamespace(
                    message=SimpleNamespace(content='Fourteen', tool_calls=None))])
            chunks = [(20.25, chunk('Four')), (20.5, chunk('teen'))]
            if final_kind == 'reported':
                chunks.append((20.5, chunk(tokens=4)))
            return TimedStream(clock, chunks)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    answer, messages, archive = asyncio.run(agent.execute(
        client=client, model='requested-model', prompt='Read the fixture.',
        image_paths=[], intelligence=tool, stream_tokens=True, max_calls=2,
        on_event=on_event))

    assert answer == 'Fourteen'
    assert len(requests) == 2
    assert tool.calls == ['test_read']
    assert sum(message['role'] == 'tool' for message in messages) == 1
    assert archive == []
    assert any(event['event'] == 'tool_finished' and not event['is_error'] for event in events)
    finished = [event for event in events if event['event'] == 'model_answered']
    assert len(finished) == 1
    assert finished[0]['model'] == 'reported-model'
    assert finished[0]['requested'] == 'requested-model'
    if final_kind == 'nonstream':
        # No stream observation exists for this final request. Do not reuse the
        # first request's text timestamps or provider-reported token count.
        assert 'first_token_ms' not in finished[0]
        assert 'tokens_per_second' not in finished[0]
        assert 'estimated_tokens' not in finished[0]
    else:
        assert finished[0]['first_token_ms'] == 250
        assert finished[0]['tokens_per_second'] == (8.0 if final_kind == 'reported' else 4.0)
        assert finished[0]['estimated_tokens'] is (final_kind == 'estimated')
    assert events[-1] == {'event': 'finished', 'model_calls': 2, 'tool_calls': 1}
