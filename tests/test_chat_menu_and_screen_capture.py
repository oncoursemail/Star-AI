"""Sidebar chat rename/delete and the consent-gated "Look at my screen" capture (wave 2026-10-13)."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from star.desktop_core import Conversations
from star import screen_capture
from star.react_shell import ALLOWED_ACTIONS, WARM_UP_STOPPERS

ROOT = Path(__file__).resolve().parents[1]
PNG = screen_capture.PNG_SIGNATURE + b'\x00' * 32


def make(tmp_path):
    return Conversations(tmp_path / 'conversations.sqlite3')


def test_rename_chat_trims_limits_and_stays_in_its_project(tmp_path):
    chats = make(tmp_path)
    try:
        first = chats.new_chat('Game')
        chats.add('Game', 'user', 'Make an inventory', chat_id=first)
        assert chats.rename_chat('Game', first, '   Inventory   UI  ') == 'Inventory UI'
        assert chats.list_chats('Game')[0]['title'] == 'Inventory UI'
        long = chats.rename_chat('Game', first, 'x' * 200)
        assert len(long) == 80 and long.endswith('…')
        with pytest.raises(ValueError):
            chats.rename_chat('Game', first, '   ')
        with pytest.raises(ValueError):
            chats.rename_chat('Other project', first, 'Stolen')
        with pytest.raises(ValueError):
            chats.rename_chat('Game', first, 'bad\x07name')
    finally:
        chats.close()


def test_a_later_first_message_does_not_overwrite_a_chosen_name(tmp_path):
    chats = make(tmp_path)
    try:
        chat = chats.new_chat('Game')
        chats.rename_chat('Game', chat, 'Named by me')
        chats.add('Game', 'user', 'First message', chat_id=chat)
        assert chats.list_chats('Game')[0]['title'] == 'Named by me'
    finally:
        chats.close()


def test_delete_chat_removes_only_that_chat_and_opens_the_newest_other(tmp_path):
    chats = make(tmp_path)
    try:
        keep = chats.new_chat('Game')
        chats.add('Game', 'user', 'keep me', chat_id=keep)
        answer = chats.add('Game', 'assistant', 'kept answer', chat_id=keep)
        gone = chats.new_chat('Game')
        chats.add('Game', 'user', 'delete me', chat_id=gone)
        rated = chats.add('Game', 'assistant', 'answer to delete', chat_id=gone)
        chats.set_feedback('Game', rated, 'up')
        chats.set_feedback('Game', answer, 'down')
        other = chats.new_chat('Elsewhere')
        chats.add('Elsewhere', 'user', 'other project', chat_id=other)
        assert chats.active_chat('Game') == gone
        opened = chats.delete_chat('Game', gone)
        assert opened == keep
        assert [c['id'] for c in chats.list_chats('Game')] == [keep]
        bodies = [r[1] for r in chats.connection.execute('SELECT role, body FROM messages')]
        assert 'delete me' not in bodies and 'answer to delete' not in bodies
        assert 'keep me' in bodies and 'other project' in bodies
        thumbs = [r[0] for r in chats.connection.execute('SELECT message_id FROM message_feedback')]
        assert thumbs == [answer]
        with pytest.raises(ValueError):
            chats.delete_chat('Game', gone)
        with pytest.raises(ValueError):
            chats.delete_chat('Game', other)  # a chat of another project cannot be reached
    finally:
        chats.close()


def test_deleting_the_last_chat_leaves_a_blank_one_open(tmp_path):
    chats = make(tmp_path)
    try:
        only = chats.new_chat('Game')
        chats.add('Game', 'user', 'hello', chat_id=only)
        opened = chats.delete_chat('Game', only)
        assert opened != only
        listed = chats.list_chats('Game')
        assert [c['id'] for c in listed] == [opened] and listed[0]['title'] == 'New chat'
    finally:
        chats.close()


def test_delete_also_drops_the_chat_context_checkpoint(tmp_path):
    chats = make(tmp_path)
    try:
        chat = chats.new_chat('Game')
        chats.add('Game', 'user', 'hello', chat_id=chat)
        chats.connection.execute(
            'CREATE TABLE IF NOT EXISTS conversation_checkpoints (project TEXT NOT NULL, chat TEXT NOT NULL, '
            'through_id INTEGER NOT NULL, source_digest TEXT NOT NULL, summary TEXT NOT NULL, '
            'summary_digest TEXT NOT NULL, version INTEGER NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(project,chat))')
        chats.connection.execute("INSERT INTO conversation_checkpoints VALUES ('Game', ?, 1, 'd', 's', 'sd', 1, 'now')", (chat,))
        chats.connection.commit()
        chats.delete_chat('Game', chat)
        assert chats.connection.execute('SELECT COUNT(*) FROM conversation_checkpoints').fetchone()[0] == 0
    finally:
        chats.close()


def test_actions_are_allowed_but_no_bulk_delete_exists():
    assert {'renameChat', 'deleteChat', 'captureScreen'} <= ALLOWED_ACTIONS
    assert 'deleteAllChats' not in ALLOWED_ACTIONS
    assert 'deleteChat' in WARM_UP_STOPPERS


@pytest.mark.parametrize('body', [{}, {'consent': 'true'}, {'consent': 1}, {'consent': False}, None, [], 'yes'])
def test_screen_capture_needs_an_explicit_boolean_yes(body):
    with pytest.raises(screen_capture.ConsentRequired):
        screen_capture.require_consent(body)


def test_screen_capture_accepts_the_explicit_yes():
    screen_capture.require_consent({'consent': True})


def test_store_capture_writes_png_under_the_data_folder_and_never_overwrites(tmp_path):
    now = datetime(2026, 10, 13, 14, 25, 1, tzinfo=timezone.utc)
    first = screen_capture.store_capture(PNG, tmp_path, now)
    second = screen_capture.store_capture(PNG, tmp_path, now)
    assert first.parent == (tmp_path / 'screen-captures').resolve()
    assert first.name == 'screen-20261013-142501.png'
    assert second.name == 'screen-20261013-142501-2.png'
    assert first.read_bytes() == PNG


@pytest.mark.parametrize('data', [b'', b'GIF89a....', 'text', None])
def test_store_capture_refuses_anything_that_is_not_a_png(tmp_path, data):
    with pytest.raises(ValueError):
        screen_capture.store_capture(data, tmp_path)
    assert not (tmp_path / 'screen-captures').exists() or not any((tmp_path / 'screen-captures').iterdir())


def test_old_captures_are_pruned_but_other_files_are_left_alone(tmp_path):
    folder = tmp_path / 'screen-captures'
    folder.mkdir()
    for index in range(5):
        (folder / f'screen-2026101{index}-000000.png').write_bytes(PNG)
    (folder / 'notes.txt').write_text('mine')
    removed = screen_capture.prune(tmp_path, keep=2)
    assert [p.name for p in removed] == ['screen-20261010-000000.png', 'screen-20261011-000000.png',
                                         'screen-20261012-000000.png']
    assert sorted(p.name for p in folder.iterdir()) == ['notes.txt', 'screen-20261013-000000.png',
                                                        'screen-20261014-000000.png']


def test_describe_returns_only_the_path_size_and_a_safe_thumbnail(tmp_path):
    thumb = screen_capture.preview_url(b'\xff\xd8jpeg', 'image/jpeg')
    assert thumb.startswith('data:image/jpeg;base64,')
    info = screen_capture.describe(tmp_path / 'screen-x.png', 1920, 1080, thumb)
    assert info == {'path': str(tmp_path / 'screen-x.png'), 'name': 'screen-x.png', 'width': 1920,
                    'height': 1080, 'preview': thumb}
    assert screen_capture.describe(tmp_path / 'a.png', 1, 1, 'javascript:alert(1)')['preview'] == ''
    with pytest.raises(ValueError):
        screen_capture.preview_url(b'x', 'text/html')


def test_shell_checks_consent_before_grabbing_and_the_model_cannot_reach_it():
    shell = (ROOT / 'star' / 'react_shell.py').read_text(encoding='utf-8')
    branch = shell[shell.index("if action=='captureScreen':"):]
    branch = branch[:branch.index('if action in LESSON_ACTIONS')]
    assert branch.index('require_screen_consent(body)') < branch.index('self._capture_screen()')
    # No agent or tool module imports the capture: only the owner's click in the interface can start it.
    for path in (ROOT / 'star').rglob('*.py'):
        if path.name in {'react_shell.py', 'screen_capture.py'}:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        # (Roblox Studio's own MCP tool is also called "screen_capture"; only imports of this module count.)
        for needle in ('.screen_capture import', 'import screen_capture', 'star.screen_capture', 'captureScreen'):
            assert needle not in text, (path, needle)
