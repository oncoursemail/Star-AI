"""Check the selected model server and prime its prompt cache, in the background.

A CPU model server reads a new prompt slowly, so the first message after STAR
starts used to pay for the whole static start of the request (the rules, the
project memory and the earlier turns of the open chat). `warm_up` sends that
exact start once, asking for a single token, so the server already holds it
when the owner presses Send.

It is deliberately harmless:

  * own hardware only: it returns at once for a cloud provider, without any
    network call, so it can never spend a hosted provider's quota;
  * it reads the conversation and checkpoint databases and writes nothing: no
    message, no run record, no analytics row, so it is never a user turn;
  * it is cancellable at any moment through `cancel_event` (the app sets it
    as soon as a real request starts) and never raises;
  * for STAR Server it first runs the cheap reachability/key/model check, so
    the status light is truthful before the first message.
"""
from __future__ import annotations
import asyncio
import sqlite3
import threading
from pathlib import Path
from time import perf_counter

from .agent import make_system_message
from .brain_router import select_route
from .context_layout import assemble
from .desktop_core import (Settings, app_data, chat_history, memory_scope_for, stable_memory)
from .model_health import note_server_result, probe_server
from .providers import llama_request_fields, open_client, provider_kind

# The priming turn. It is the last message of the request, so nothing after the
# cached start depends on it; the single generated token is thrown away.
PRIME_TEXT = "."


def _checkpoint(home: Path, scope: str) -> str:
    """Read the compacted checkpoint without creating or changing the database."""
    file = home / 'checkpoints.sqlite3'
    if not file.is_file():
        return ''
    try:
        connection = sqlite3.connect(f'{file.as_uri()}?mode=ro', uri=True)
        try:
            row = connection.execute('SELECT summary FROM checkpoints WHERE project=?', (scope,)).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return ''
    return row[0] if row and isinstance(row[0], str) else ''


def prefix_request(settings: Settings, home: Path, chat_id: str | None) -> dict:
    """The request whose start equals the start of the next plain-chat message.

    Built with the same functions a real turn uses (`make_system_message`,
    `chat_history`, `llama_request_fields`), so the bytes match by construction.
    """
    history = chat_history(settings, home, chat_id)[0] if (home / 'conversations.sqlite3').is_file() else []
    scope = memory_scope_for(settings, chat_id)
    system = make_system_message(stable_memory(settings, _checkpoint(home, scope)), tools_attached=False)
    messages, _ = assemble(system, history, {'role': 'user', 'content': [{'type': 'text', 'text': PRIME_TEXT}]})
    return {'model': select_route(settings, 'hello', mode='fast').model, 'messages': messages,
            'extras': llama_request_fields(settings, conversation=scope, tools=False)}


async def _prime(settings: Settings, request: dict, cancel_event, timeout: float | None) -> dict:
    """Send the one-token request; stop the moment `cancel_event` is set."""
    async with open_client(settings, request_timeout=timeout) as client:
        async def send(extras):
            stream = await client.chat.completions.create(
                model=request['model'], messages=request['messages'], max_tokens=1, temperature=0,
                stream=True, **({'extra_body': extras} if extras else {}))
            timings = None
            if hasattr(stream, '__aiter__'):
                async for chunk in stream:
                    timings = getattr(chunk, 'timings', None) or timings
            return timings

        async def call():
            try:
                return await send(request['extras'])
            except Exception as exc:
                # A server that is not llama.cpp may refuse the cache fields.
                if not request['extras'] or getattr(exc, 'status_code', None) not in (400, 422):
                    raise
                return await send(None)

        job = asyncio.create_task(call())
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    return {'primed': False, 'cancelled': True}
                done, _ = await asyncio.wait({job}, timeout=0.1)
                if done:
                    timings = job.result()
                    found = {'primed': True}
                    if isinstance(timings, dict):
                        for key, name in (('prompt_n', 'prompt_tokens_read'), ('cache_n', 'prompt_tokens_cached')):
                            if type(timings.get(key)) is int:
                                found[name] = timings[key]
                    return found
        finally:
            if not job.done():
                job.cancel()   # closes the HTTP stream; the server drops the request
                await asyncio.gather(job, return_exceptions=True)


def warm_up(settings: Settings, *, home: Path | None = None, chat_id: str | None = None,
            cancel_event=None, on_checked=None, check: bool = True, transport=None) -> dict:
    """Check the server (STAR Server only) and prime the cache. Never raises.

    Returns a small nonsecret report: `skipped` (why nothing was done), or
    `ok`/`code` from the check and `primed` plus the token counts the server
    reported. `on_checked(report)` is called as soon as the check is finished,
    before the slower priming request, so the interface can show the result.
    """
    began = perf_counter()
    def done(**fields) -> dict:
        return {'primed': False, **fields, 'ms': int((perf_counter() - began) * 1000)}
    try:
        settings.validate()
        kind = provider_kind(settings)
    except Exception:
        return done(skipped='settings')
    if kind == 'cloud':
        return done(skipped='cloud')
    if not settings.model.strip():
        return done(skipped='no_model')
    cancelled = lambda: cancel_event is not None and cancel_event.is_set()
    report = None
    if kind == 'lan':
        if check:
            try:
                report = probe_server(settings, transport=transport, chat=False)
            except Exception:
                return done(skipped='check_failed')
            if on_checked is not None:
                try:
                    on_checked(report)
                except Exception:
                    pass
            if not report.get('ok'):
                return done(ok=False, code=str(report.get('code', '')))
    if cancelled():
        return done(cancelled=True, **({'ok': True, 'code': 'ok'} if report else {}))
    checked = {'ok': True, 'code': 'ok'} if report else {}
    try:
        request = prefix_request(settings, home or app_data(), chat_id)
    except Exception as exc:
        # Nothing was sent: a chat database or setting that cannot be read is a
        # local problem and says nothing about the server.
        return done(skipped='no_request', error=type(exc).__name__, **checked)
    try:
        result = asyncio.run(_prime(settings, request, cancel_event, None))
    except Exception as exc:
        status = getattr(exc, 'status_code', None)
        if kind == 'lan' and (status is None or status in (401, 403, 503)):
            # Unreachable, timed out, wrong key or loading: the light must not say "ready".
            note_server_result(settings, False, 'request_failed')
        return done(error=type(exc).__name__, **({'ok': False, 'code': 'request_failed'} if kind == 'lan' else {}))
    if report:
        result.update(ok=True, code='ok')
    result['history_messages'] = len(request['messages']) - 2
    return done(**result)


class Warmer:
    """Runs at most one warm-up at a time, each on a daemon thread of its own.

    Starting a new one cancels the one before it. `cancel()` returns at once;
    the running request is dropped within a tenth of a second.
    """

    def __init__(self, run=warm_up):
        self._run = run
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self.thread: threading.Thread | None = None

    def cancel(self) -> None:
        with self._lock:
            self._cancel.set()

    def start(self, load, *, check: bool = True, on_checked=None, on_done=None) -> threading.Thread:
        """`load()` returns (settings, home, chat_id). It runs on the new thread, so
        the caller (the UI thread) never touches a file or the network."""
        with self._lock:
            self._cancel.set()
            cancel = self._cancel = threading.Event()

        def task():
            report = {'primed': False, 'skipped': 'error'}
            try:
                settings, home, chat_id = load()
                report = self._run(settings, home=home, chat_id=chat_id, cancel_event=cancel,
                                   on_checked=on_checked, check=check)
            except Exception:
                pass
            finally:
                if on_done is not None:
                    try:
                        on_done(report)
                    except Exception:
                        pass

        thread = threading.Thread(target=task, name='star-warm-up', daemon=True)
        self.thread = thread
        thread.start()
        return thread
