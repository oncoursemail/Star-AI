"""Offline coverage, provenance and atomicity for complete dialogue prefixes."""
import asyncio
import copy
import json
import re
import threading
from types import SimpleNamespace

import pytest

from star import conversation_memory as cm
from star import memory
from star.desktop_core import Conversations


class Models:
    def __init__(self, responder=None):
        self.requests = []
        self.responder = responder or marker_summary

    async def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        value = self.responder(request)
        if isinstance(value, BaseException):
            raise value
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
            message=SimpleNamespace(content=value))])


def marker_summary(request):
    markers = list(dict.fromkeys(re.findall(r'EVIDENCE_[A-Z0-9_]+', request['messages'][1]['content'])))
    return 'Unverified checkpoint: ' + ' '.join(markers)


def client(models):
    return SimpleNamespace(chat=SimpleNamespace(completions=models))


@pytest.fixture
def dialogue(tmp_path):
    store = Conversations(tmp_path / 'conversations.sqlite3')
    chat = store.new_chat('P')
    yield store, chat
    store.close()


def add_exchange(store, chat, index, *, width=200):
    user = f'EVIDENCE_USER_{index} '.ljust(width, 'u')
    answer = f'EVIDENCE_ANSWER_{index} '.ljust(width, 'a')
    store.add('P', 'user', user, chat_id=chat)
    store.add('P', 'assistant', answer, chat_id=chat)


def prepare(store, chat, models, budget=1000, **kwargs):
    records = store.raw_history_records('P', chat)
    window = cm.select_window(records, budget)
    return asyncio.run(cm.prepare(client(models), 'offline', store_path(store),
                                  'P', chat, records, window, **kwargs))


def store_path(store):
    from pathlib import Path
    return Path(store.connection.execute('PRAGMA database_list').fetchone()[2])


def test_raw_reads_are_full_id_bearing_and_none_means_exact_legacy(dialogue):
    store, chat = dialogue
    original = 'EARLY ' + 'long ' * 4000 + ' COMPLETE_TAIL'
    identity = store.add('P', 'user', original, chat_id=chat)
    store.add('P', 'assistant', 'answer', chat_id=chat)
    store.add('P', 'user', 'legacy owner')
    other = store.new_chat('OTHER')
    store.add('OTHER', 'user', 'private other project', chat_id=other)
    records = store.raw_history_records('P', chat)
    assert records[0]['id'] == identity and records[0]['body'] == original
    assert set(records[0]) == {'id', 'role', 'body', 'created', 'status', 'reply_to'}
    assert [record['body'] for record in store.raw_history_records('P', None)] == ['legacy owner']


def test_selection_never_clips_complete_messages_or_recaps_current_question(dialogue):
    store, chat = dialogue
    original = 'EVIDENCE_EARLY ' + 'word ' * 4000 + ' EVIDENCE_END'
    store.add('P', 'user', original, chat_id=chat)
    answer_id = store.add('P', 'assistant', 'Earlier answer.', chat_id=chat)
    store.add('P', 'user', 'ACTIVE_CURRENT_QUESTION', chat_id=chat)
    records = store.raw_history_records('P', chat)
    before = copy.deepcopy(records)
    window = cm.select_window(records, 1000, current_text='ACTIVE_CURRENT_QUESTION')
    assert window.through_id == answer_id and window.messages == []
    assert window.omitted[0]['body'] == original
    assert all(record['body'] != 'ACTIVE_CURRENT_QUESTION' for record in window.omitted)
    models = Models()
    asyncio.run(cm.prepare(client(models), 'offline', store_path(store), 'P', chat, records, window))
    leaves = [request['messages'][1]['content'].split('REDACTED SOURCE TEXT:\n', 1)[1]
              for request in models.requests if 'REDACTED SOURCE TEXT:\n' in request['messages'][1]['content']]
    covered = ''.join(leaves)
    assert original in json.loads(covered.split('NEW TRANSCRIPT (redacted source):\n', 1)[1])[0]['content']
    assert 'ACTIVE_CURRENT_QUESTION' not in covered
    assert records == before


def test_restart_reuses_checkpoint_and_next_move_summarizes_only_new_prefix(dialogue):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    first_models = Models()
    first = prepare(store, chat, first_models)
    assert first.changed and first.checkpoint.through_id == 6
    assert cm.read_checkpoint(store_path(store), 'P', chat) is None  # prepare never writes
    cm.commit(store_path(store), first)
    saved = cm.read_checkpoint(store_path(store), 'P', chat)
    unchanged_models = Models()
    unchanged = prepare(store, chat, unchanged_models)
    assert unchanged.checkpoint == saved and not unchanged.changed and not unchanged_models.requests
    for index in range(4, 6):
        add_exchange(store, chat, index)
    next_models = Models()
    advanced = prepare(store, chat, next_models)
    assert advanced.changed and advanced.checkpoint.through_id == 8
    source = next_models.requests[0]['messages'][1]['content'].split('NEW TRANSCRIPT (redacted source):\n', 1)[1]
    newly_omitted = json.loads(source)
    assert [record['record_id'] for record in newly_omitted] == [7, 8]
    assert 'EVIDENCE_USER_0' in advanced.checkpoint.summary  # prior requirement survives reduction
    assert 'EVIDENCE_USER_3' in advanced.checkpoint.summary
    cm.commit(store_path(store), advanced)
    assert cm.read_checkpoint(store_path(store), 'P', chat) == advanced.checkpoint


def test_failed_or_cancelled_prior_user_is_retained_with_outcome(dialogue):
    store, chat = dialogue
    user = store.add('P', 'user', 'EVIDENCE_KEEP_FAILED_REQUIREMENT', chat_id=chat)
    event = store.add_terminal('P', chat, user, 'cancelled', 'Owner stopped the turn.')
    for index in range(4):
        add_exchange(store, chat, index)
    models = Models()
    result = prepare(store, chat, models)
    transcript = json.loads(models.requests[0]['messages'][1]['content'].split('NEW TRANSCRIPT (redacted source):\n', 1)[1])
    assert next(record for record in transcript if record['record_id'] == event)['status'] == 'cancelled'
    assert 'EVIDENCE_KEEP_FAILED_REQUIREMENT' in result.checkpoint.summary


@pytest.mark.parametrize('status', ['failed', 'cancelled'])
def test_last_historic_failure_is_not_mistaken_for_the_active_question(dialogue, status):
    store, chat = dialogue
    user = store.add('P', 'user', 'Continue.', chat_id=chat)
    event = store.add_terminal('P', chat, user, status, 'Historic outcome.')
    records = store.raw_history_records('P', chat)
    window = cm.select_window(records, 1000, current_text='Continue.')
    assert window.messages[0]['content'] == 'Continue.'
    assert [record['id'] for record in window.exchanges[0]] == [user, event]


def test_similar_new_question_does_not_remove_an_unrelated_unanswered_record(dialogue):
    store, chat = dialogue
    user = store.add('P', 'user', 'Please', chat_id=chat)
    window = cm.select_window(store.raw_history_records('P', chat), 1000, current_text='Please continue.')
    assert window.messages[0]['content'] == 'Please'
    assert window.exchanges[0][0]['id'] == user


def test_legacy_checkpoint_matches_actual_writes_and_never_includes_other_chats(dialogue):
    store, other_chat = dialogue
    for index in range(4):
        add_exchange(store, None, index)
    store.add('P', 'user', 'OTHER_CHAT_PRIVATE', chat_id=other_chat)
    models = Models()
    candidate = prepare(store, None, models)
    cm.commit(store_path(store), candidate)
    assert cm.scope('P', None) == ('P', 'legacy')
    assert cm.read_checkpoint(store_path(store), 'P', None) == cm.read_checkpoint(store_path(store), 'P', 'legacy')
    assert 'OTHER_CHAT_PRIVATE' not in json.dumps(models.requests)


def test_raw_body_limit_is_checked_before_transferring_any_body(dialogue, monkeypatch):
    store, chat = dialogue
    store.add('P', 'user', '\u00e9\0' * 200, chat_id=chat)
    monkeypatch.setattr(cm, 'HISTORY_MAX_BYTES', 100)
    class MetadataOnly:
        @property
        def in_transaction(self):
            return store.connection.in_transaction
        def execute(self, sql, *args):
            assert 'SELECT id,role,body' not in sql
            return store.connection.execute(sql, *args)
        def rollback(self):
            return store.connection.rollback()
    with pytest.raises(cm.ConversationRetentionError, match='UTF-8 body bytes'):
        cm.raw_records(MetadataOnly(), 'P', chat)
    assert store.connection.execute('SELECT body FROM messages').fetchone()[0] == '\u00e9\0' * 200


@pytest.mark.parametrize('failure', ['', OSError('offline'), asyncio.CancelledError(), 'x' * 6001],
                         ids=['empty', 'provider-error', 'cancelled', 'oversized'])
def test_failed_summary_keeps_old_checkpoint_and_cursor(dialogue, failure):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    first = prepare(store, chat, Models())
    cm.commit(store_path(store), first)
    old = cm.read_checkpoint(store_path(store), 'P', chat)
    for index in range(4, 6):
        add_exchange(store, chat, index)
    with pytest.raises((RuntimeError, OSError, asyncio.CancelledError)):
        prepare(store, chat, Models(lambda _: failure))
    assert cm.read_checkpoint(store_path(store), 'P', chat) == old


def test_truncated_summary_and_small_output_budget_do_not_write_state(dialogue):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    models = Models()
    async def truncated(**request):
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='length', message=SimpleNamespace(content='partial'))])
    models.create = truncated
    with pytest.raises(memory.CompactionLimitError, match='did not complete'):
        prepare(store, chat, models)
    with pytest.raises(memory.CompactionLimitError, match='output budget'):
        prepare(store, chat, Models(lambda _: 'x' * 1000), summary_chars=700)
    assert cm.read_checkpoint(store_path(store), 'P', chat) is None


def test_source_change_and_compare_and_swap_refuse_candidate(dialogue):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    first = prepare(store, chat, Models())
    duplicate = prepare(store, chat, Models())
    cm.commit(store_path(store), first)
    with pytest.raises(cm.ConversationRetentionError, match='another turn'):
        cm.commit(store_path(store), duplicate)
    assert cm.read_checkpoint(store_path(store), 'P', chat) == first.checkpoint
    for index in range(4, 6):
        add_exchange(store, chat, index)
    advanced = prepare(store, chat, Models())
    with store.connection:
        store.connection.execute("UPDATE messages SET body='modified source' WHERE id=1")
    with pytest.raises(cm.ConversationRetentionError, match='changed or are missing'):
        cm.commit(store_path(store), advanced)
    # Inspect saved state directly: old state remains, even though its source was mutated by the fixture.
    assert store.connection.execute('SELECT through_id FROM conversation_checkpoints').fetchone()[0] == 6
    with pytest.raises(cm.ConversationRetentionError, match='changed or are missing'):
        cm.read_checkpoint(store_path(store), 'P', chat)


def test_cancellation_before_commit_and_changed_source_before_dispatch_are_atomic(dialogue):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    candidate = prepare(store, chat, Models())
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(cm.ConversationRetentionError, match='cancelled'):
        cm.commit(store_path(store), candidate, cancel_event=cancelled)
    assert cm.read_checkpoint(store_path(store), 'P', chat) is None
    def mutate(_):
        with store.connection:
            store.connection.execute("UPDATE messages SET body='new source' WHERE id=1")
        return 'candidate'
    with pytest.raises(cm.ConversationRetentionError, match='changed or are missing'):
        prepare(store, chat, Models(mutate))
    assert cm.read_checkpoint(store_path(store), 'P', chat) is None


def test_checkpoint_scope_integrity_and_no_read_only_creation(dialogue, tmp_path):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    cm.commit(store_path(store), prepare(store, chat, Models()))
    other = store.new_chat('P')
    assert cm.read_checkpoint(store_path(store), 'P', other) is None
    assert cm.read_checkpoint(store_path(store), 'OTHER', chat) is None
    assert cm.read_checkpoint(store_path(store), 'P', None) is None
    missing = tmp_path / 'must-not-create.sqlite3'
    assert cm.read_checkpoint(missing, 'P', chat) is None and not missing.exists()
    with store.connection:
        store.connection.execute("UPDATE conversation_checkpoints SET summary='tampered'")
    with pytest.raises(cm.ConversationRetentionError, match='integrity'):
        cm.read_checkpoint(store_path(store), 'P', chat)


def test_short_window_and_unchanged_boundary_add_no_provider_work(dialogue):
    store, chat = dialogue
    add_exchange(store, chat, 0, width=20)
    models = Models()
    result = prepare(store, chat, models)
    assert not result.changed and result.checkpoint is None and not models.requests
    assert store.connection.execute("SELECT name FROM sqlite_master WHERE name='conversation_checkpoints'").fetchall() == []


def test_recaps_respect_source_work_bound_without_touching_originals(dialogue, monkeypatch):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    original = store.raw_history_records('P', chat)
    monkeypatch.setattr(memory, 'COMPACTION_SOURCE_CHARS', 100)
    models = Models()
    with pytest.raises(memory.CompactionLimitError, match='source exceeds'):
        prepare(store, chat, models)
    assert not models.requests and store.raw_history_records('P', chat) == original
    assert cm.read_checkpoint(store_path(store), 'P', chat) is None
