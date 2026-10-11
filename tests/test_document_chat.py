"""Offline desktop integration: actual parsing, scoped retrieval and calculations."""
import json
import re
from types import SimpleNamespace

import pytest

from star import desktop_core as core
from star.documents import DocumentStore


def reply(text=None, calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=calls))])


class Models:
    def __init__(self, responder):
        self.responder, self.requests = responder, []

    async def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return self.responder(len(self.requests), kwargs)


class Client:
    def __init__(self, models):
        self.chat = SimpleNamespace(completions=models)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def desktop(tmp_path, monkeypatch, responder):
    home = tmp_path / 'private-app'
    monkeypatch.setattr(core, 'app_data', lambda: home)
    models = Models(responder)
    monkeypatch.setattr(core, 'open_client', lambda *_args, **_kwargs: Client(models))
    return home, models, core.Settings(model='offline-fixture')


def test_fast_attachment_calculates_exactly_and_never_opens_unrelated_tools(tmp_path, monkeypatch):
    source = tmp_path / 'precise.csv'
    source.write_text('name,amount\nAda,123456789.123456789123456789\nBo,0.000000000000000001\n', encoding='utf-8')

    def respond(number, request):
        if number == 1:
            definitions = {item['function']['name']: item['function'] for item in request['tools']}
            assert set(definitions) == {'star_document_search', 'star_data_analyze'}
            identifier = re.search(r'data_[0-9a-f]{24}', definitions['star_data_analyze']['description']).group()
            arguments = {'dataset_id': identifier, 'operation': 'sum', 'column': 'amount'}
            tool = SimpleNamespace(id='sum-call', function=SimpleNamespace(name='star_data_analyze', arguments=json.dumps(arguments)))
            return reply(calls=[tool])
        envelope = json.loads(request['messages'][-1]['content'])
        assert envelope['isError'] is False
        result = json.loads(envelope['output'])
        assert result['value'] == '123456789.12345678912345679'
        assert result['exact'] is True
        assert result['row_evidence']['locations'] == ['precise.csv, line 2', 'precise.csv, line 3']
        return reply('The calculated total is 123456789.12345678912345679.')

    home, models, settings = desktop(tmp_path, monkeypatch, respond)
    events = []
    answer = core.run_task(settings, 'What is the total amount?', mode='fast', chat_id='one',
                           documents=[source], on_event=events.append)
    assert '123456789.12345678912345679' in answer
    assert len(models.requests) == 2
    assert {'documents_started', 'documents_ready'} <= {event['event'] for event in events}
    with DocumentStore(home, settings.project, 'one') as store:
        assert store.datasets()[0]['rows'][0][1] == '123456789.123456789123456789'


def test_follow_up_retrieves_tail_after_restart_and_never_crosses_scope(tmp_path, monkeypatch):
    home, models, settings = desktop(tmp_path, monkeypatch, lambda *_: reply('Fixture answer.'))
    source = tmp_path / 'long.txt'
    source.write_text(('Ordinary source material.\n' * 4000) + 'CYANITE final milestone: ship in April.\n', encoding='utf-8')
    core.run_task(settings, 'Give me an overview.', mode='fast', chat_id='one', documents=[source])
    core.run_task(settings, 'What is the CYANITE milestone?', mode='fast', chat_id='one')
    follow = models.requests[-1]
    assert 'ship in April' in json.dumps(follow['messages'])
    assert 'line 4001' in json.dumps(follow['messages'])
    core.run_task(settings, 'What is the CYANITE milestone?', mode='fast', chat_id='two')
    assert 'ship in April' not in json.dumps(models.requests[-1]['messages'])
    assert not models.requests[-1].get('tools')
    other = core.Settings(model='offline-fixture', project='OTHER')
    core.run_task(other, 'What is the CYANITE milestone?', mode='fast', chat_id='one')
    assert 'ship in April' not in json.dumps(models.requests[-1]['messages'])


def test_invalid_selection_fails_before_model_dispatch(tmp_path, monkeypatch):
    home, models, settings = desktop(tmp_path, monkeypatch, lambda *_: reply('Must not run.'))
    source = tmp_path / 'unknown.exe'
    source.write_bytes(b'not a document')
    with pytest.raises(ValueError, match='Unsupported|supported'):
        core.run_task(settings, 'Read this.', chat_id='one', documents=[source])
    assert models.requests == []
    with DocumentStore(home, settings.project, 'one') as store:
        assert store.context('anything') == ''


def test_no_attachment_keeps_ordinary_chat_without_document_database(tmp_path, monkeypatch):
    home, models, settings = desktop(tmp_path, monkeypatch, lambda *_: reply('Hello.'))
    assert core.run_task(settings, 'Hello.', mode='fast') == 'Hello.'
    assert not (home / 'documents.sqlite3').exists()
    assert not models.requests[0].get('tools')


@pytest.mark.parametrize('checkpoint_length,fits', [(4200, True), (7000, False)])
def test_desktop_preserves_full_checkpoint_or_fails_before_dispatch(tmp_path, monkeypatch, checkpoint_length, fits):
    home, models, settings = desktop(tmp_path, monkeypatch, lambda *_: reply('Fixture answer.'))
    settings.context_chars = 6000
    checkpoint = ('EARLIER CONSTRAINT: preserve the approved design.\n' +
                  'reference ' * checkpoint_length)[:checkpoint_length]
    scope = core.memory_scope_for(settings, 'one')
    memory = core.Memory(home / 'checkpoints.sqlite3')
    try:
        memory.put(scope, checkpoint)
    finally:
        memory.close()
    if fits:
        assert core.run_task(settings, 'Continue.', mode='fast', chat_id='one') == 'Fixture answer.'
        assert len(models.requests) == 1
        assert checkpoint in models.requests[0]['messages'][0]['content']
    else:
        with pytest.raises(RuntimeError, match='original request alone.*system context were not shortened'):
            core.run_task(settings, 'Continue.', mode='fast', chat_id='one')
        assert models.requests == []
    memory = core.Memory(home / 'checkpoints.sqlite3')
    try:
        assert memory.get(scope) == checkpoint
    finally:
        memory.close()


@pytest.mark.parametrize('extension,source_text', [
    ('.csv', 'amount\n0.123456789123456789123456789\n0.000000000000000000000000001\n'),
    ('.json', '[{"amount":0.123456789123456789123456789},{"amount":0.000000000000000000000000001}]'),
])
def test_parse_to_calculation_retains_original_decimal_precision(tmp_path, extension, source_text):
    from star.data_analysis import analyze
    source = tmp_path / ('precision' + extension)
    source.write_text(source_text, encoding='utf-8')
    with DocumentStore(tmp_path / 'home', 'P', 'C') as store:
        store.ingest([source])
        datasets = store.datasets()
        result = analyze(datasets, {'dataset_id': datasets[0]['id'], 'operation': 'sum', 'column': 'amount'})
        assert result['value'] == '0.12345678912345678912345679'
        assert result['exact'] is True
