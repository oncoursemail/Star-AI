"""Offline checks for native-only server key import."""
import json
import logging

import pytest

from star import server_key_file
from star.desktop_core import Settings


def test_import_never_returns_or_persists_key(tmp_path, monkeypatch, caplog):
    secret = 'server-secret-test-placeholder-1234'
    root = tmp_path / '.star'
    root.mkdir()
    (root / 'server_api_key').write_text('STAR_SERVER_API_KEY=' + secret + '\nignored', encoding='utf-8')
    stored = []
    monkeypatch.setattr(server_key_file, 'save_api_key', lambda provider, token: stored.append((provider, token)))
    with caplog.at_level(logging.DEBUG):
        assert server_key_file.key_file_status(tmp_path) == {'found': True}
        outcome = server_key_file.import_key_file(tmp_path)
    settings = tmp_path / 'settings.json'
    Settings().save(settings)
    assert stored == [('star_server', secret)]
    assert outcome == {'connected': True}
    assert secret not in json.dumps(outcome)
    assert secret not in settings.read_text()
    assert secret not in caplog.text


def test_missing_and_unreadable_key_file(tmp_path):
    assert server_key_file.key_file_status(tmp_path) == {'found': False}
    with pytest.raises(ValueError, match='unreadable'):
        server_key_file.import_key_file(tmp_path)
    root = tmp_path / '.star'
    root.mkdir()
    (root / 'server_api_key').write_bytes(b'\xff')
    with pytest.raises(ValueError, match='unreadable'):
        server_key_file.import_key_file(tmp_path)


def test_invalid_key_never_echoed(tmp_path, monkeypatch):
    root = tmp_path / '.star'
    root.mkdir()
    (root / 'server_api_key').write_text('INVALID=short', encoding='utf-8')
    monkeypatch.setattr(server_key_file, 'save_api_key', lambda provider, token: (_ for _ in ()).throw(ValueError('bad key')))
    with pytest.raises(ValueError, match='invalid') as raised:
        server_key_file.import_key_file(tmp_path)
    assert 'short' not in str(raised.value)
