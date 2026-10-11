from pathlib import Path

import pytest

from star.desktop_core import Conversations


def test_interrupted_turn_reuses_original_row(tmp_path: Path):
    chats = Conversations(tmp_path / 'conversations.sqlite3')
    chat = chats.new_chat('STAR')
    mid = chats.add('STAR', 'user', 'make a lobby', chat_id=chat)
    chats.close()
    reopened = Conversations(tmp_path / 'conversations.sqlite3')
    state = reopened.retry_state('STAR', chat)
    assert state['status'] == 'interrupted'
    assert state['message_id'] == mid
    assert reopened.recover_turn('STAR', chat, mid, 'make a lobby') == mid
    assert len(reopened.recent_records('STAR', chat_id=chat)) == 1
    with pytest.raises(ValueError):
        reopened.recover_turn('STAR', chat, mid, 'different')
    reopened.close()


def test_finished_chat_never_offers_interrupted_retry(tmp_path: Path):
    chats = Conversations(tmp_path / 'conversations.sqlite3')
    chat = chats.new_chat('STAR')
    mid = chats.add('STAR', 'user', 'hello', chat_id=chat)
    chats.add('STAR', 'assistant', 'Hi!', chat_id=chat)
    assert chats.retry_state('STAR', chat) is None
    with pytest.raises(ValueError):
        chats.recover_turn('STAR', chat, mid, 'hello')
    chats.close()


def test_active_turn_is_not_interrupted(tmp_path: Path):
    chats = Conversations(tmp_path / 'conversations.sqlite3')
    chat = chats.new_chat('STAR')
    chats.add('STAR', 'user', 'working', chat_id=chat)
    assert chats.retry_state('STAR', chat, busy=True) is None
    chats.close()
