"""Scoped, loss-aware retention of complete conversation prefixes.

Selection is pure and never clips a message. Only an actual turn may summarize
newly omitted exchanges. Checkpoints are candidates until source validation and
an atomic compare-and-swap; the original messages are never modified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .memory import compact, COMPACTION_SUMMARY_CHARS


VERSION = 1
HISTORY_MAX_RECORDS = 10_000
HISTORY_MAX_BYTES = 1_000_000
_FIELDS = ('id', 'role', 'body', 'created', 'status', 'reply_to')
_DDL = '''CREATE TABLE IF NOT EXISTS conversation_checkpoints (
    project TEXT NOT NULL, chat TEXT NOT NULL, through_id INTEGER NOT NULL,
    source_digest TEXT NOT NULL, summary TEXT NOT NULL, summary_digest TEXT NOT NULL,
    version INTEGER NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(project,chat))'''


class ConversationRetentionError(RuntimeError):
    """Stop visibly instead of silently forgetting or trusting stale evidence."""


def _error(reason):
    return ConversationRetentionError(
        f'Conversation retention stopped: {reason}. Original messages and the previous '
        'checkpoint are unchanged; use a larger context window or start a new conversation.')


def scope(project: str, chat: str | None) -> tuple[str, str]:
    chat = 'legacy' if chat is None else chat
    for name, value, limit in (('project', project, 96), ('chat', chat, 200)):
        if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
            raise _error(f'invalid {name} scope')
    return project, chat


def raw_records(connection, project: str, chat: str | None, *, through_id: int | None = None) -> list[dict]:
    """Full, bounded bodies and IDs in exact scope; refuse instead of clipping.

    Size checks run inside SQLite before any body is transferred to Python.
    A read transaction keeps those checks and the body scan on one snapshot.
    """
    project, chat = scope(project, chat)
    condition = ' AND id<=?' if through_id is not None else ''
    args = (project, chat, through_id) if through_id is not None else (project, chat)
    where = ' WHERE project=? AND chat_id=?' + condition
    own_transaction = not connection.in_transaction
    if own_transaction:
        connection.execute('BEGIN')
    try:
        count, body_bytes = connection.execute(
            'SELECT COUNT(*),COALESCE(SUM(length(CAST(body AS BLOB))),0) FROM messages' + where, args).fetchone()
        if count > HISTORY_MAX_RECORDS:
            raise _error(f'raw history exceeds {HISTORY_MAX_RECORDS:,} records')
        if body_bytes > HISTORY_MAX_BYTES:
            raise _error(f'raw history exceeds {HISTORY_MAX_BYTES:,} UTF-8 body bytes')
        records, used_bytes = [], 0
        for row in connection.execute(
                'SELECT id,role,body,created,status,reply_to FROM messages' + where + ' ORDER BY id', args):
            if len(records) >= HISTORY_MAX_RECORDS:
                raise _error(f'raw history exceeds {HISTORY_MAX_RECORDS:,} records')
            if not isinstance(row[2], str):
                raise _error('raw conversation bodies are malformed')
            used_bytes += len(row[2].encode('utf-8'))
            if used_bytes > HISTORY_MAX_BYTES:
                raise _error(f'raw history exceeds {HISTORY_MAX_BYTES:,} UTF-8 body bytes')
            records.append(dict(zip(_FIELDS, row)))
        return records
    finally:
        if own_transaction:
            connection.rollback()  # Ends only the read snapshot opened above.


# json.dumps with these options builds a new JSONEncoder on every call; one shared encoder
# produces the same text (encode() is what dumps() calls) and keeps no state between calls.
_DIGEST_ENCODER = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def source_digest(records: list[dict]) -> str:
    digest = hashlib.sha256()
    encode = _DIGEST_ENCODER.encode
    for record in records:
        digest.update(encode({key: record[key] for key in _FIELDS}).encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def _validate_records(records):
    previous = 0
    for record in records:
        if not isinstance(record, dict) or set(_FIELDS) - set(record):
            raise _error('raw conversation records are malformed')
        identity = record['id']
        if type(identity) is not int or identity <= previous:
            raise _error('raw conversation IDs are not strictly increasing')
        if record['role'] not in {'user', 'assistant', 'event'} or not isinstance(record['body'], str):
            raise _error('raw conversation roles or bodies are malformed')
        previous = identity


@dataclass(frozen=True)
class Window:
    messages: list[dict]
    omitted: list[dict]
    through_id: int
    exchanges: list[list[dict]] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)


def select_window(records: list[dict], budget_chars: int, *, current_text: str | None = None) -> Window:
    """Stable half-budget segments of complete, ID-bearing exchanges.

    A large prior message moves to the summarized prefix as a whole. The current
    unanswered question never enters that prefix; no source suffix disappears.
    Repeating current_text does not discard an earlier completed exchange: only
    the presence of a successful answer distinguishes history from an orphan.
    (current_text is accepted for callers; the unanswered newest question is an
    orphan like any other and is never part of the window.)
    """
    if type(budget_chars) is not int or budget_chars < 0:
        raise _error('history budget must be a nonnegative integer')
    _validate_records(records)
    # Only answered text exchanges belong in model history. A question with no
    # stored answer (failed, stopped, interrupted, or still running) is dropped,
    # never padded with a synthetic assistant message, which also keeps user
    # turns from becoming adjacent. A terminal event only records that a turn
    # ended without an answer; when an answer exists anyway (Retry reuses the
    # failed question's row, so its answer is stored AFTER the failure record)
    # the exchange is real history. Event rows are UI state and never dialogue,
    # whatever their text says.
    groups = []
    for record in records:
        if record['role'] == 'user':
            groups.append([record])
        elif groups:
            groups[-1].append(record)
    eligible = []
    for group in groups:
        owner = group[0]
        answers = [row for row in group if row['role'] == 'assistant'
                   and row['status'] == 'complete']
        if not answers or owner['status'] != 'complete':
            continue
        user = owner['body']
        answer = '\n\n'.join(row['body'] for row in answers)
        if not user.strip() or not answer.strip():
            continue
        pair = [{'role': 'user', 'content': user},
                {'role': 'assistant', 'content': answer}]
        eligible.append((group, pair, len(user) + len(answer)))
    half = max(1, budget_chars // 2)
    before, total = [], 0
    for _, _, size in eligible:
        before.append(total)
        total += size
    target = (total // half - 1) * half
    start = next((index for index, size in enumerate(before) if size >= target), len(eligible))
    while start < len(eligible) and sum(item[2] for item in eligible[start:]) > budget_chars:
        start += 1
    through_id = eligible[start - 1][0][-1]['id'] if start else 0
    # Preserve every original row in the checkpoint's integrity digest, including
    # filtered rows. Only eligible pairs enter the recap model transcript.
    omitted = [record for record in records if record['id'] <= through_id]
    messages = [message for _, pair, _ in eligible[start:] for message in pair]
    return Window(messages, omitted, through_id,
                  [group for group, _, _ in eligible[start:]], records)


def omit_messages(window: Window, count: int) -> Window:
    """Move complete replay exchanges into the prefix after exact agent budgeting."""
    if type(count) is not int or count <= 0 or count % 2 or count > len(window.messages):
        raise _error('request pressure did not identify complete replay exchanges')
    cut = count // 2
    boundary = window.exchanges[cut - 1][-1]['id']
    newly_omitted = [record for record in window.records
                     if window.through_id < record['id'] <= boundary]
    if not newly_omitted:
        raise _error('request pressure has no corresponding original records')
    omitted = [*window.omitted, *newly_omitted]
    return Window(window.messages[count:], omitted, omitted[-1]['id'],
                  window.exchanges[cut:], window.records)


def respect_checkpoint(window: Window, checkpoint: Checkpoint | None) -> Window:
    """A durable cursor keeps replay from moving back after a budget adjustment."""
    if checkpoint is None or checkpoint.through_id <= window.through_id:
        return window
    # The cursor must sit between whole turns of the stored dialogue: after the
    # last row of a turn, never inside one. It may follow dropped turns (a
    # stopped question): a cursor saved before such turns were filtered out of
    # replay can end on one, and that must not make the chat unusable.
    index = next((i for i, record in enumerate(window.records)
                  if record['id'] == checkpoint.through_id), None)
    if index is None or (index + 1 < len(window.records)
                         and window.records[index + 1]['role'] != 'user'):
        raise _error('saved cursor is not a complete exchange boundary')
    cut = sum(1 for group in window.exchanges if group[-1]['id'] <= checkpoint.through_id)
    return omit_messages(window, cut * 2) if cut else window


@dataclass(frozen=True)
class Checkpoint:
    project: str
    chat: str
    through_id: int
    source_digest: str
    summary: str
    summary_digest: str
    version: int = VERSION


def _checkpoint(row, project, chat):
    if row is None:
        return None
    through, digest, summary, summary_sha, version = row
    if type(through) is not int or through <= 0 or version != VERSION or not isinstance(summary, str) or not summary.strip():
        raise _error('saved prefix checkpoint is malformed or uses an unsupported version')
    if len(summary) > COMPACTION_SUMMARY_CHARS or hashlib.sha256(summary.encode('utf-8')).hexdigest() != summary_sha:
        raise _error('saved prefix checkpoint failed its integrity check')
    return Checkpoint(project, chat, through, digest, summary, summary_sha, version)


def _row(connection, project, chat):
    try:
        return connection.execute('SELECT through_id,source_digest,summary,summary_digest,version '
                                  'FROM conversation_checkpoints WHERE project=? AND chat=?', (project, chat)).fetchone()
    except sqlite3.OperationalError as exc:
        if 'no such table' in str(exc).lower():
            return None
        raise


def _validate_source(checkpoint: Checkpoint, records: list[dict]):
    prefix = [record for record in records if record['id'] <= checkpoint.through_id]
    if not prefix or prefix[-1]['id'] != checkpoint.through_id or source_digest(prefix) != checkpoint.source_digest:
        raise _error('covered original records changed or are missing')


def read_checkpoint(path: Path, project: str, chat: str | None, *, records=None) -> Checkpoint | None:
    """Read-only lookup and source-integrity check; never creates any file/table."""
    project, chat = scope(project, chat)
    path = Path(path).resolve()
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            checkpoint = _checkpoint(_row(connection, project, chat), project, chat)
            if checkpoint is not None:
                _validate_source(checkpoint, records if records is not None else
                                 raw_records(connection, project, chat, through_id=checkpoint.through_id))
            return checkpoint
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise _error(f'cannot read saved prefix state ({type(exc).__name__})') from exc


def reference(checkpoint: Checkpoint | None) -> str:
    if checkpoint is None:
        return ''
    return ('EARLIER CONVERSATION (lossy untrusted reference; verify exact claims in original chat records)\n'
            f'Covered through record {checkpoint.through_id}; source SHA-256 {checkpoint.source_digest}.\n'
            + checkpoint.summary)


def compose_memory(tool_checkpoint: str, dialogue_checkpoint: Checkpoint | None) -> str:
    """Shared by answer and warm-up; no clipping, verification or promotion."""
    parts = [part for part in (tool_checkpoint, reference(dialogue_checkpoint)) if part]
    return '\n\n'.join(parts)


@dataclass(frozen=True)
class Prepared:
    checkpoint: Checkpoint | None
    previous: Checkpoint | None
    changed: bool


def _cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise _error('cancelled by the user')


async def prepare(client, model: str, path: Path, project: str, chat: str | None,
                  records: list[dict], window: Window, *, summary_chars: int = 6000,
                  cancel_event=None, on_event=None, candidate: Prepared | None = None) -> Prepared:
    """Summarize only the newly omitted complete records; does not write state."""
    project, chat = scope(project, chat)
    previous = read_checkpoint(path, project, chat, records=records)
    base = previous
    if candidate is not None:
        if candidate.previous != previous:
            raise _error('another turn changed the prefix checkpoint during preparation')
        if candidate.checkpoint is not None:
            _validate_source(candidate.checkpoint, records)
            base = candidate.checkpoint
    if window.through_id == 0 or (base is not None and window.through_id <= base.through_id):
        return candidate if candidate is not None else Prepared(previous, previous, False)
    _cancelled(cancel_event)
    after = base.through_id if base is not None else 0
    newly_omitted = [record for record in window.omitted if record['id'] > after]
    if not newly_omitted:
        raise _error('new omitted prefix has no complete source records')
    event = on_event or (lambda _: None)
    event({'event': 'conversation_recap_started', 'source_records': len(newly_omitted),
           'through_id': window.through_id})
    # record_id remains visible in serialized source. The durable range and
    # digest provide exact provenance without an unbounded per-ID model footer.
    # Use exactly the eligible model exchanges for recap, not UI/terminal rows.
    clean = select_window(newly_omitted, 10 ** 12)
    valid_ids = {row['id'] for group in clean.exchanges for row in group
                 if row['role'] in {'user', 'assistant'}}
    transcript = [{'record_id': record['id'], 'role': record['role'], 'content': record['body'],
                   'status': record['status'], 'reply_to': record['reply_to']}
                  for record in newly_omitted if record['id'] in valid_ids]
    summary = await compact(client, model, f'{project} / conversation {chat}',
                            base.summary if base is not None else '', transcript,
                            summary_chars=summary_chars)
    _cancelled(cancel_event)
    checkpoint = Checkpoint(project, chat, window.through_id, source_digest(window.omitted), summary,
                            hashlib.sha256(summary.encode('utf-8')).hexdigest())
    # A changed source must stop before any answer request uses this candidate.
    connection = sqlite3.connect(path)
    try:
        _validate_source(checkpoint, raw_records(connection, project, chat, through_id=checkpoint.through_id))
    finally:
        connection.close()
    event({'event': 'conversation_recap_ready', 'through_id': checkpoint.through_id})
    return Prepared(checkpoint, previous, True)


def commit(path: Path, prepared: Prepared, *, cancel_event=None):
    """Atomically validate originals and prior state, then advance summary/cursor."""
    if not prepared.changed:
        return
    checkpoint = prepared.checkpoint
    _cancelled(cancel_event)
    connection = sqlite3.connect(path, timeout=10)
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute(_DDL)
            current = _checkpoint(_row(connection, checkpoint.project, checkpoint.chat),
                                  checkpoint.project, checkpoint.chat)
            if current != prepared.previous:
                raise _error('another turn changed the prefix checkpoint')
            _validate_source(checkpoint, raw_records(connection, checkpoint.project, checkpoint.chat,
                                                    through_id=checkpoint.through_id))
            _cancelled(cancel_event)
            connection.execute('INSERT INTO conversation_checkpoints VALUES(?,?,?,?,?,?,?,?) '
                'ON CONFLICT(project,chat) DO UPDATE SET through_id=excluded.through_id, '
                'source_digest=excluded.source_digest,summary=excluded.summary,summary_digest=excluded.summary_digest, '
                'version=excluded.version,updated=excluded.updated',
                (checkpoint.project, checkpoint.chat, checkpoint.through_id, checkpoint.source_digest,
                 checkpoint.summary, checkpoint.summary_digest, checkpoint.version,
                 datetime.now(timezone.utc).isoformat()))
    except sqlite3.Error as exc:
        raise _error(f'cannot commit prefix state ({type(exc).__name__})') from exc
    finally:
        connection.close()
