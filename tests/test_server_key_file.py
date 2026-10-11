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


def _stored(tmp_path, monkeypatch, content, *, binary=False):
    root = tmp_path / '.star'
    root.mkdir(exist_ok=True)
    target = root / 'server_api_key'
    target.write_bytes(content) if binary else target.write_text(content, encoding='utf-8')
    stored = []
    monkeypatch.setattr(server_key_file, 'save_api_key', lambda provider, token: stored.append(token))
    return stored


@pytest.mark.parametrize(('content', 'expected'), [
    ('abcdefgh=ijklmnop', 'abcdefgh=ijklmnop'),                # a key that contains '=' is not NAME=value
    ('QUJDREVGR0hJSktM==\n', 'QUJDREVGR0hJSktM=='),           # base64 padding
    ('ABCDEFGH12345678==', 'ABCDEFGH12345678=='),              # upper-case key with padding
    ('plain-key-without-equals\nsecond line', 'plain-key-without-equals'),
    ('STAR_SERVER_API_KEY=' + 'value-' * 3 + 'x\n', 'value-' * 3 + 'x'),
    ('export STAR_KEY = "' + 'quoted-' * 2 + 'x"', 'quoted-' * 2 + 'x'),
    ('STAR_KEY=' + 'with=inside=' + 'x' * 6, 'with=inside=' + 'x' * 6),   # only the first '=' separates
])
def test_a_key_is_stored_whole_and_only_an_environment_style_name_is_stripped(tmp_path, monkeypatch, content, expected):
    stored = _stored(tmp_path, monkeypatch, content)
    assert server_key_file.import_key_file(tmp_path) == {'connected': True}
    assert stored == [expected]


def test_a_byte_order_mark_is_not_part_of_the_key(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch, b'\xef\xbb\xbf' + b'plain-key-without-equals\r\n', binary=True)
    server_key_file.import_key_file(tmp_path)
    assert stored == ['plain-key-without-equals']


@pytest.mark.parametrize('content', [
    'NAME=' + ' ' * 4090 + 'k' * 40,          # the first line is cut off inside the key
    ' ' * 4000 + 'k' * 400,
    'k' * 5000,
])
def test_a_first_line_that_does_not_fit_is_refused_and_nothing_is_stored(tmp_path, monkeypatch, content):
    stored = _stored(tmp_path, monkeypatch, content)
    with pytest.raises(ValueError, match='invalid'):
        server_key_file.import_key_file(tmp_path)
    assert stored == []


def test_a_folder_in_place_of_the_key_file_is_not_found_and_not_read(tmp_path, monkeypatch):
    (tmp_path / '.star' / 'server_api_key').mkdir(parents=True)
    monkeypatch.setattr(server_key_file, 'save_api_key', lambda provider, token: pytest.fail('nothing to store'))
    assert server_key_file.key_file_status(tmp_path) == {'found': False}
    with pytest.raises(ValueError, match='unreadable'):
        server_key_file.import_key_file(tmp_path)
