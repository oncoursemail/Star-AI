"""Drive real extraction, immutable storage, retrieval and budgets for Roblox attachments."""
import json
from pathlib import Path
import threading
from unittest.mock import Mock

import pytest

from star import documents, rbx_xml
from star.documents import DocumentCancelled, DocumentError, DocumentStore

FIXTURES = Path(__file__).parent / 'fixtures' / 'rbx_xml'


def test_xml_ingest_outline_first_script_budgets_and_restart(tmp_path):
    path = tmp_path / 'model.RBXMX'
    path.write_bytes((FIXTURES / 'model.rbxmx').read_bytes())
    home = tmp_path / 'home'
    with DocumentStore(home, 'project', 'chat') as store:
        manifest = store.ingest([path])[0]
        assert manifest['tables'] == 0 and manifest['chunks'] > 3
        assert store.knowledge.artifact('project', manifest['digest']).read_bytes() == path.read_bytes()
        context = store.context('local storage FireClient onRequest', 6000)
        assert context.index('Roblox XML outline:') < context.index('local storage =')
        assert context.index('Roblox script index') < context.index('local storage =')
        assert 'lines 1-8, Script, path /Demo/Logic/Server' in context
        assert 'RunContext' in context and 'SHOULD_NOT_BE_EXTRACTED' not in context
        assert 'untrusted source' in context and 'Coverage:' in context
        assert 'lexical' in context
        small = store.context('local storage FireClient onRequest', 1000)
        assert 'Roblox XML outline:' in small
        assert 'local storage =' not in small
        for budget in (0, 1, 20, 100, 700, 1300, 4000, 10000):
            assert len(store.context('FireClient', budget)) <= budget
        assert store.context('FireClient') == store.context('FireClient')
        assert store.datasets() == []
        payload = json.loads(store.db.execute('SELECT payload FROM document_payloads').fetchone()[0])
        assert payload['chunks'][0]['kind'] == 'rbx_outline'
        assert any(c['kind'] == 'rbx_source' and 'local storage =' in c['text'] for c in payload['chunks'])
        saved = store.context('FireClient')
    with DocumentStore(home, 'project', 'chat') as store:
        assert store.context('FireClient') == saved
    with DocumentStore(home, 'project', 'another-chat') as store:
        assert store.context('FireClient') == ''
    with DocumentStore(home, 'another-project', 'chat') as store:
        assert store.context('FireClient') == ''


def test_outline_fragments_stay_in_order_despite_body_relevance(tmp_path, monkeypatch):
    monkeypatch.setattr(documents, 'CHUNK_CHARS', 100)
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        store.ingest([FIXTURES / 'model.rbxmx'])
        context = store.context('Client', 10000)
        positions = [context.index(f'Roblox outline, chars {start}-') for start in (1, 101, 201, 301)]
        assert positions == sorted(positions)
        assert positions[-1] < context.index('remote:FireServer')


def test_mixed_text_keeps_tail_retrieval_and_xml_place_outline(tmp_path):
    text = tmp_path / 'notes.txt'
    text.write_text('\n'.join(['ordinary'] * 299 + ['ULTRAMARINE tail evidence']))
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        store.ingest([text, FIXTURES / 'place.rbxlx'])
        context = store.context('ULTRAMARINE', 2400)
        assert 'Roblox XML outline: 4 instances; 0 scripts' in context
        assert 'ULTRAMARINE tail evidence' in context and 'line 300' in context


@pytest.mark.parametrize('suffix', ['.rbxm', '.rbxl'])
def test_binary_attachments_are_documents_with_actionable_refusals(tmp_path, suffix):
    path = tmp_path / ('fixture' + suffix)
    path.write_bytes(b'<roblox!\x89\xff')
    assert suffix in documents.DOCUMENT_EXTENSIONS
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        with pytest.raises(DocumentError, match='Binary Roblox.*export as XML'):
            store.ingest([path])
        assert store.context('anything') == ''
    with pytest.raises(DocumentError, match='Binary Roblox'):
        documents._extract(path, suffix)


def test_unsafe_xml_batch_is_atomic_and_preserves_specific_error(tmp_path):
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        with pytest.raises(DocumentError, match='DTDs, entities'):
            store.ingest([FIXTURES / 'model.rbxmx', FIXTURES / 'billion_laughs.rbxmx'])
        assert store.context('anything') == ''


def test_oversized_xml_is_refused_before_artifact_copy(tmp_path, monkeypatch):
    path = tmp_path / 'oversized.rbxlx'
    path.write_bytes(b'x' * 129)
    monkeypatch.setattr(rbx_xml, 'MAX_FILE_BYTES', 128)
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        copy = Mock(side_effect=AssertionError('oversized input must not be copied'))
        monkeypatch.setattr(store.knowledge, 'ingest_artifact', copy)
        with pytest.raises(DocumentError, match='file-size'):
            store.ingest([path])
        copy.assert_not_called()
        assert store.context('anything') == ''


def test_xml_cancellation_reaches_real_parser_and_remains_atomic(tmp_path):
    class DuringParsing:
        calls = 0
        def is_set(self):
            self.calls += 1
            return self.calls == 15
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        with pytest.raises(DocumentCancelled):
            store.ingest([FIXTURES / 'model.rbxmx'], DuringParsing())
        assert store.context('anything') == ''
        event = threading.Event()
        event.set()
        with pytest.raises(DocumentCancelled):
            documents._extract(FIXTURES / 'model.rbxmx', '.rbxmx', event)


def test_empty_xml_is_a_valid_outline_not_a_scanned_document_error(tmp_path):
    path = tmp_path / 'empty.rbxmx'
    path.write_text('<roblox/>')
    with DocumentStore(tmp_path / 'home', 'project', 'chat') as store:
        store.ingest([path])
        assert '0 instances; 0 scripts' in store.context('overview')
