"""Offline coverage, provenance and atomicity for complete dialogue prefixes."""
import asyncio
import copy
import hashlib
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


@pytest.mark.parametrize('scenario', [
    'stopped_then_failed_image',
    'cancelled',
    'failed',
    'interrupted',
    'orphan_between',
    'event_between',
])
def test_history_shaping_excludes_bad_turns_and_keeps_pairs(dialogue, scenario):
    store, chat = dialogue
    store.add('P', 'user', 'Stable question', chat_id=chat)
    store.add('P', 'assistant', 'Stable answer', chat_id=chat)
    if scenario == 'stopped_then_failed_image':
        stopped = store.add('P', 'user', 'stopped request', chat_id=chat)
        store.add_terminal('P', chat, stopped, 'cancelled', 'Stopped by owner')
        image = store.add('P', 'user', 'generate image', chat_id=chat)
        store.add_terminal('P', chat, image, 'failed', 'Image generation failed')
    elif scenario in ('cancelled', 'failed'):
        owner = store.add('P', 'user', 'bad request', chat_id=chat)
        store.add_terminal('P', chat, owner, scenario, 'failed')
    elif scenario in ('interrupted', 'orphan_between'):
        store.add('P', 'user', 'orphan request', chat_id=chat)
    else:
        store.add('P', 'event', 'UI notification', chat_id=chat)
    store.add('P', 'user', 'what is 2+2?', chat_id=chat)
    records = store.raw_history_records('P', chat)
    window = cm.select_window(records, 10000, current_text='what is 2+2?')
    assert window.messages == [{'role': 'user', 'content': 'Stable question'},
                               {'role': 'assistant', 'content': 'Stable answer'}]
    assert len(window.messages) % 2 == 0
    assert window.through_id == 0


@pytest.mark.parametrize('current_text', [None, 'what is 2+2?', 'A different question'])
def test_completed_exchange_survives_repeated_current_text(dialogue, current_text):
    store, chat = dialogue
    store.add('P', 'user', 'what is 2+2?', chat_id=chat)
    store.add('P', 'assistant', '4', chat_id=chat)
    records = store.raw_history_records('P', chat)
    expected = [{'role': 'user', 'content': 'what is 2+2?'},
                {'role': 'assistant', 'content': '4'}]
    idle = cm.select_window(records, 10000)
    active = cm.select_window(records, 10000, current_text=current_text)
    assert active == idle and active.messages == expected
    # Saving an identical new question must not rewrite the completed prefix.
    store.add('P', 'user', 'what is 2+2?', chat_id=chat)
    busy = cm.select_window(store.raw_history_records('P', chat), 10000, current_text='what is 2+2?')
    assert busy.messages == expected and busy.omitted == []
    assert store.raw_history_records('P', chat)[:len(records)] == records


def test_multi_row_answer_joins_with_paragraph_newlines(dialogue):
    store, chat = dialogue
    store.add('P', 'user', 'Explain in two parts.', chat_id=chat)
    store.add('P', 'assistant', 'First part.', chat_id=chat)
    store.add('P', 'assistant', 'Second part.', chat_id=chat)
    records = store.raw_history_records('P', chat)
    window = cm.select_window(records, 10000)
    assert window.messages == [{'role': 'user', 'content': 'Explain in two parts.'},
                               {'role': 'assistant', 'content': 'First part.\n\nSecond part.'}]
    assert window.exchanges == [records]
    assert store.raw_history_records('P', chat) == records


@pytest.mark.parametrize('selection', ['window', 'pressure'])
@pytest.mark.parametrize('status', ['cancelled', 'failed'])
def test_filtered_rows_cannot_enter_recaps_and_checkpoint_prefix_is_stable(dialogue, selection, status):
    store, chat = dialogue
    for index in range(4):
        add_exchange(store, chat, index)
    owner = store.add('P', 'user', 'EVIDENCE_CANCELLED_SHOULD_NOT_LEAK', chat_id=chat)
    event = store.add_terminal('P', chat, owner, status, 'EVIDENCE_EVENT_SHOULD_NOT_LEAK')
    orphan = store.add('P', 'user', 'EVIDENCE_INTERRUPTED_SHOULD_NOT_LEAK', chat_id=chat)
    # Force the excluded rows INTO the omitted prefix, not beyond the recap boundary.
    for index in range(4, 8):
        add_exchange(store, chat, index)
    records = store.raw_history_records('P', chat)
    window = cm.select_window(records, 1000)
    if selection == 'pressure':
        window = cm.omit_messages(cm.select_window(records, 10000), 14)
    excluded = {owner, event, orphan}
    assert excluded <= {row['id'] for row in window.omitted}
    assert window.omitted == [row for row in records if row['id'] <= window.through_id]
    models = Models()
    candidate = asyncio.run(cm.prepare(client(models), 'offline', store_path(store),
                                      'P', chat, records, window))
    assert candidate.changed and candidate.checkpoint.through_id == window.through_id
    source = json.loads(models.requests[0]['messages'][1]['content'].split(
        'NEW TRANSCRIPT (redacted source):\n', 1)[1])
    assert [row['record_id'] for row in source] == [row['id'] for row in window.omitted
                                                  if row['id'] not in excluded]
    assert [row['role'] for row in source] == ['user', 'assistant'] * 7
    assert 'EVIDENCE_USER_0' in candidate.checkpoint.summary
    assert 'EVIDENCE_USER_6' in candidate.checkpoint.summary
    serialized = json.dumps(models.requests) + candidate.checkpoint.summary
    assert 'EVIDENCE_CANCELLED_SHOULD_NOT_LEAK' not in serialized
    assert 'EVIDENCE_EVENT_SHOULD_NOT_LEAK' not in serialized
    assert 'EVIDENCE_INTERRUPTED_SHOULD_NOT_LEAK' not in serialized
    cm.commit(store_path(store), candidate)
    assert cm.read_checkpoint(store_path(store), 'P', chat) == candidate.checkpoint
    assert store.raw_history_records('P', chat) == records
    unchanged_models = Models()
    unchanged = prepare(store, chat, unchanged_models)
    assert unchanged.checkpoint == candidate.checkpoint and not unchanged.changed
    assert unchanged_models.requests == []
    # Exclusion from model input must NOT exclude a stored row from source integrity.
    with store.connection:
        store.connection.execute("UPDATE messages SET body='changed event' WHERE id=?", (event,))
    with pytest.raises(cm.ConversationRetentionError, match='changed or are missing'):
        cm.read_checkpoint(store_path(store), 'P', chat)


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


def test_retried_turn_keeps_its_answer_after_a_terminal_record(dialogue):
    """Retry reuses the failed question's row, so the answer lands AFTER the terminal event."""
    store, chat = dialogue
    asked = store.add('P', 'user', 'Please retry me', chat_id=chat)
    store.add_terminal('P', chat, asked, 'failed', 'Cannot reach STAR Brain.')
    assert cm.select_window(store.raw_history_records('P', chat), 10000).exchanges == []   # nothing answered yet
    assert store.recover_turn('P', chat, asked, 'Please retry me') == asked   # what the Retry button does
    store.add('P', 'assistant', 'Retried answer.', chat_id=chat)
    answered_then_stopped = store.add('P', 'user', 'Answer saved, then Stop arrived', chat_id=chat)
    store.add('P', 'assistant', 'Saved answer.', chat_id=chat)
    store.add_terminal('P', chat, answered_then_stopped, 'cancelled', 'Request stopped.')
    store.add('P', 'user', 'next question', chat_id=chat)
    window = cm.select_window(store.raw_history_records('P', chat), 10000, current_text='next question')
    assert window.messages == [
        {'role': 'user', 'content': 'Please retry me'}, {'role': 'assistant', 'content': 'Retried answer.'},
        {'role': 'user', 'content': 'Answer saved, then Stop arrived'},
        {'role': 'assistant', 'content': 'Saved answer.'}]
    # The terminal event text is storage and UI state; it never becomes dialogue.
    assert 'Cannot reach' not in json.dumps(window.messages) and 'Request stopped' not in json.dumps(window.messages)


def test_event_text_alone_never_drops_a_completed_exchange(dialogue):
    """A note that merely mentions "image" or "interrupted" must not erase a real answered turn."""
    store, chat = dialogue
    store.add('P', 'user', 'make a thumbnail', chat_id=chat)
    store.add('P', 'event', 'image generation interrupted note', chat_id=chat)
    store.add('P', 'assistant', 'Here is the thumbnail plan.', chat_id=chat)
    records = store.raw_history_records('P', chat)
    window = cm.select_window(records, 10000)
    assert window.messages == [{'role': 'user', 'content': 'make a thumbnail'},
                               {'role': 'assistant', 'content': 'Here is the thumbnail plan.'}]
    assert window.exchanges == [records]


def test_checkpoint_made_before_filtering_ending_on_a_dropped_turn_still_loads(dialogue):
    """A cursor saved at the end of a stopped turn (older behaviour) must not break the chat."""
    store, chat = dialogue
    for index in range(2):
        add_exchange(store, chat, index)
    stopped = store.add('P', 'user', 'EVIDENCE_STOPPED', chat_id=chat)
    end = store.add_terminal('P', chat, stopped, 'cancelled', 'Request stopped.')
    for index in range(2, 6):
        add_exchange(store, chat, index)
    records = store.raw_history_records('P', chat)
    covered = [row for row in records if row['id'] <= end]
    legacy = cm.Checkpoint('P', chat, end, cm.source_digest(covered), 'Unverified checkpoint: EVIDENCE_USER_0',
                           hashlib.sha256(b'Unverified checkpoint: EVIDENCE_USER_0').hexdigest())
    cm.commit(store_path(store), cm.Prepared(legacy, None, True))
    window = cm.select_window(records, 100000)
    assert window.through_id == 0 and len(window.messages) == 12
    resumed = cm.respect_checkpoint(window, cm.read_checkpoint(store_path(store), 'P', chat))
    assert resumed.through_id == records[3]['id']             # the two answered exchanges before the stop
    assert resumed.messages[0]['content'].startswith('EVIDENCE_USER_2')
    assert resumed.messages[1]['content'].startswith('EVIDENCE_ANSWER_2')
    # A cursor inside a replayed exchange is still refused.
    inside = cm.Checkpoint('P', chat, records[6]['id'], cm.source_digest(records[:7]), 'x', 'x')
    with pytest.raises(cm.ConversationRetentionError, match='complete exchange boundary'):
        cm.respect_checkpoint(window, inside)
