"""Regression tests for strict-template Qwen / llama.cpp readiness checks."""
import asyncio
from types import SimpleNamespace
import pytest

from star.desktop_core import Settings, recent_context
from star.model_health import probe_chat_endpoint, explain_model_failure


class FakeChat:
    def __init__(self, response='STAR is ready.'):
        self.response = response
        self.requests = []
    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content=self.response))])


def test_probe_really_calls_chat_completion(monkeypatch):
    import openai
    fake = FakeChat()
    class FakeOpenAI:
        def __init__(self, **kwargs):
            assert kwargs['base_url'] == 'http://127.0.0.1:8080/v1'
            self.chat = SimpleNamespace(completions=fake)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(openai, 'AsyncOpenAI', FakeOpenAI)
    settings = Settings(endpoint='http://127.0.0.1:8080/v1',model='local-test')
    result = asyncio.run(probe_chat_endpoint(settings))
    assert result['ok'] is True
    assert 'ready' in result['sample']
    messages = fake.requests[0]['messages']
    assert [i for i,x in enumerate(messages) if x['role']=='system'] == [0]
    assert messages[1]['role']=='user'
    assert fake.requests[0]['max_tokens'] > 0


def test_probe_rejects_blank_output(monkeypatch):
    import openai
    fake = FakeChat(response='')
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=fake)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(openai,'AsyncOpenAI',FakeOpenAI)
    with pytest.raises(RuntimeError,match='no visible text'):
        asyncio.run(probe_chat_endpoint(Settings(endpoint='http://127.0.0.1:8080/v1',
                                                  model='blank-model')))


def test_friendly_server_failure_does_not_expose_jinja_source():
    message=explain_model_failure(RuntimeError(
        "Error code: 500 ... raise_exception('System message must be at the beginning.')"))
    assert 'chat template' in message
    assert 'raise_exception' not in message
    assert 'Update STAR' in message
    assert 'HTTP 500' in explain_model_failure(RuntimeError('Error code: 500 - internal'))


def test_recent_context_excludes_only_duplicate_current_turn():
    recent=[('user','hello','t1'),('assistant','hi','t2'),('user','new prompt','t3')]
    context=recent_context(recent,'new prompt')
    assert 'hello' in context and 'hi' in context and 'new prompt' not in context
    assert 'new prompt' in recent_context(recent,'different prompt')
    assert recent[-1][1]=='new prompt'  # Non-mutating
