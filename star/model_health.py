"""Actual chat-completion diagnostics (not just a /models availability probe).

Qwen3.5/llama.cpp strict templates reject second or later system messages.
Keep a single first system role in both the normal agent and this smoke test.

`probe_server` checks an owner-configured STAR Server on the LAN step by step
and explains each failure in words the owner can act on. No report, message or
exception text produced here ever contains the server key.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from . import server_roles
from .desktop_core import Settings
from .providers import (STAR_SERVER, call_limits, get_api_key, open_client, provider_kind,
                        remember_server_limits, uses_star_server, validate_lan_endpoint)


SERVER_FAILURES = {
    'no_key': 'STAR Server needs its API key. Paste it in Settings → STAR Server and save it.',
    'unreachable': ('Cannot reach STAR Server. Check that the server is switched on, that this PC is on '
                    'the same network, and that the address and port are right.'),
    'timeout': ('STAR Server did not answer in time. It may be busy with another request or still '
                'loading its model. Try again, or raise the server timeout in Settings.'),
    'wrong_key': 'STAR Server refused the API key (401). Paste the correct server key in Settings → STAR Server.',
    'loading': 'STAR Server is reachable but still loading its model (503). Wait a minute, then test again.',
    'unknown_model': ('STAR Server is reachable, but it does not offer this model ID. '
                      'Choose one of the models the server lists.'),
    'no_model': 'STAR Server is reachable and the key works. Choose one of its models to finish setup.',
    'not_compatible': ('This address answered, but not as an OpenAI-compatible /v1 server. '
                       'Check the address and port.'),
    'busy': 'STAR Server is busy (429). Wait for the current request to finish, then try again.',
    'http_error': 'STAR Server returned an unexpected error. Check the server logs.',
    'empty_reply': ('STAR Server answered without any visible text. Check the model\'s chat template '
                    'and reasoning settings on the server.'),
}


def _status_of(error: Exception):
    status = getattr(error, 'status_code', None)
    if status is None:
        status = getattr(getattr(error, 'response', None), 'status_code', None)
    return status if isinstance(status, int) else None


def server_failure_code(status: int | None, body: str = '') -> str:
    """Classify one HTTP answer from a LAN llama.cpp / OpenAI-compatible server."""
    text = body.lower()
    if status in (401, 403):
        return 'wrong_key'
    if status == 503 or 'loading model' in text:
        return 'loading'
    # llama.cpp's router answers 400 "model '...' not found"; others answer 404.
    if status == 404 or (status == 400 and 'not found' in text):
        return 'unknown_model'
    if status == 429:
        return 'busy'
    return 'http_error'


def _explain_server_failure(error: Exception) -> str:
    # httpx errors often carry an empty message, so the class name is evidence too.
    message = (str(error) + ' ' + type(error).__name__).lower()
    status = _status_of(error)
    if 'cancelled by user' in message:
        return 'Request stopped. The draft answer has not been saved as a completed result.'
    if 'task budget' in message or 'task time limit' in message:
        return ('STAR reached its request time limit. Try Fast mode or a shorter prompt, '
                'or raise the STAR Server timeout in Settings.')
    for marker in (401, 403, 503, 404, 429):
        if status is None and f'error code: {marker}' in message:
            status = marker
    if status is None and 'error code: 400' in message:
        status = 400
    if status in (401, 403, 503, 404, 429) or (status == 400 and 'not found' in message):
        return SERVER_FAILURES[server_failure_code(status, message)]
    if any(term in message for term in ('connection error', 'connection refused', 'connecterror',
                                        'connecttimeout', 'apiconnectionerror', 'networkerror')):
        return SERVER_FAILURES['unreachable']
    if 'timed out' in message or 'timeout' in message:
        return SERVER_FAILURES['timeout']
    if 'context' in message and any(term in message for term in ('limit', 'exceed', 'size', 'length')):
        return ('STAR Server ran out of context space. Start a new chat, or raise the model context '
                'on the server and in Settings.')
    if 'system message must be at the beginning' in message:
        return ('STAR Server rejected the chat template because a system instruction appeared '
                'after the first message. Update STAR, then try again.')
    if status == 500 or 'error code: 500' in message or 'internal server error' in message:
        return 'STAR Server returned HTTP 500. Check the server logs, then run Test server in Settings.'
    if status == 400:
        return 'STAR Server rejected the request format (HTTP 400). Check the selected model and its chat template.'
    return f'STAR Server request failed ({type(error).__name__}). Run Test server in Settings.'


def explain_model_failure(error: Exception, provider_kind: str | None = None) -> str:
    """Return a short actionable message without leaking raw server/Jinja internals.

    `provider_kind='lan'` gives STAR Server wording; a server on the network is
    never fixed by starting the on-device brain.
    """
    if provider_kind == 'lan':
        return _explain_server_failure(error)
    message = str(error).lower()
    status = getattr(error, 'status_code', None)
    if status in (401, 403) or 'error code: 401' in message or 'error code: 403' in message:
        return 'Your selected model provider denied access. Check its API key, model access and account limits in Settings.'
    if status == 429 or 'error code: 429' in message or 'rate limit' in message:
        return 'The AI provider reached its rate limit. Free tiers are limited; try again when your quota resets, or switch provider in Settings.'
    if status == 404 or 'error code: 404' in message:
        return 'The selected model is not available on this provider. Choose a valid model ID and run Test actual response.'
    if 'cancelled by user' in message:
        return 'Request stopped. The draft answer has not been saved as a completed result.'
    if 'task budget' in message or 'task time limit' in message:
        return 'STAR reached its request time limit. Try Fast mode or select a faster provider.'
    if 'system message must be at the beginning' in message:
        return ('The local AI rejected the chat template because a system instruction '
                'appeared after the first message. Update STAR to the fixed version '
                'and restart STAR Brain, then try again.')
    if 'connection error' in message or 'connection refused' in message or 'connecterror' in message:
        return 'Cannot reach STAR Brain. Start it on the Model page, then test the connection again.'
    if 'timed out' in message or 'timeout' in message:
        return ('STAR Brain did not respond in time. The model may still be loading '
                'or your machine may be low on memory.')
    if 'context' in message and any(term in message for term in ('limit', 'exceed', 'size', 'length')):
        return 'STAR Brain ran out of context space. Try a shorter conversation or lower the context budget.'
    if 'error code: 500' in message or 'internal server error' in message:
        return ('STAR Brain returned HTTP 500. Restart the local engine, try Test response '
                'in STAR Brain, and check the local STAR logs for further detail.')
    if 'error code: 400' in message:
        return 'STAR Brain rejected the request format (HTTP 400). Check the selected model and its chat template.'
    return f'Local model request failed ({type(error).__name__}). Check STAR Brain and the engine logs.'


def missing_model_message(settings, *, teams: bool = False) -> str:
    """What to do when no model ID is saved. A server user is never sent to a download."""
    if uses_star_server(settings):
        return ('No STAR Server model is selected. Open Settings → STAR Server, run Test server, '
                'and choose one of the models it lists.')
    if teams:
        return 'Start STAR Brain before running a specialist team'
    return 'STAR Brain is offline. Go to STAR Brain and start your model.'


async def probe_chat_endpoint(settings: Settings, timeout: float | None = None) -> dict:
    """Issue a real completion to the configured model and inspect its text.

    A successful GET /models alone does not prove the chat template can render.
    This is a tiny, read-only health check; it performs no Studio/tool operations.
    """
    settings.validate()
    if not settings.model.strip():
        raise ValueError('Select a model before testing its response')
    lan = provider_kind(settings) == 'lan'
    if timeout is None:
        timeout = call_limits(settings).request_timeout if lan else 120.0
    name = 'STAR Server' if lan else 'STAR Brain'
    async with open_client(settings, request_timeout=timeout) as client:
        completion = await client.chat.completions.create(
            model=settings.model,
            messages=[
                {'role':'system','content':'You are STAR. Reply briefly and plainly.'},
                {'role':'user','content':'Reply with the exact words: STAR is ready.'},
            ],
            max_tokens=256,
            temperature=0,
        )
        if not completion.choices:
            raise RuntimeError(f'{name} returned no completion choices')
        response = str(completion.choices[0].message.content or '').strip()
        if not response:
            raise RuntimeError(f'{name} returned no visible text. Check the model template and reasoning settings.')
        return {'ok': True, 'model': settings.model, 'sample': response[:180]}


# The outcome of the newest server check, for a status light in the app. It is
# process memory only and holds no address, key, prompt or model output.
_LAST_SERVER_CHECK: dict = {}


def note_server_result(settings, ok: bool, code: str = '') -> None:
    """Remember whether the selected server last answered (after a probe or a chat)."""
    # One update call with every key: a reader on another thread never sees half a record.
    _LAST_SERVER_CHECK.update({
        'target': (str(getattr(settings, 'server_endpoint', '')).rstrip('/'), str(getattr(settings, 'model', ''))),
        'ok': bool(ok), 'code': str(code)[:40],
        'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    })


def server_status(settings) -> dict:
    """Nonsecret STAR Server summary for the interface. Makes no network call."""
    endpoint = str(getattr(settings, 'server_endpoint', ''))
    last = dict(_LAST_SERVER_CHECK)  # snapshot: worker threads update the original
    current = last.get('target') == (endpoint.rstrip('/'), str(getattr(settings, 'model', '')))
    return {
        'selected': uses_star_server(settings),  # never raises on a hand-edited settings file
        'configured': bool(endpoint),
        'key_present': bool(get_api_key(STAR_SERVER)),
        'model_selected': bool(str(getattr(settings, 'model', '')).strip()),
        'ok': last.get('ok') if current else None,   # None = not checked yet
        'code': last.get('code', '') if current else '',
        'checked_at': last.get('checked_at', '') if current else '',
        # Which model does which job on this server; [] for other providers.
        'roles': server_roles.role_report(settings) if uses_star_server(settings) else [],
    }


def probe_server(settings, *, transport=None, chat: bool = True) -> dict:
    """Check STAR Server in four timed steps and say exactly which one failed.

    health (is the box up) -> /v1/models with the key (is the key right, which
    models exist) -> /props (context and slots; informational) -> one tiny real
    chat completion. It uses the saved server address and the keyring key even
    when another provider is selected, so the owner can test before switching.
    A failed step is a normal result (`ok: False` plus a message), not an error.
    `chat=False` stops after the limits step: the cheap check STAR runs at start,
    which is followed by its own one-token request (see star/warmup.py).
    """
    import httpx
    from .brain_benchmark import parse_sse_data
    from .brain_router import validate_alias

    steps: list[dict] = []
    model = str(getattr(settings, 'model', '') or '')
    report = {'ok': False, 'code': '', 'message': '', 'steps': steps, 'models': [], 'model': model,
              'context_tokens': None, 'slots': None, 'first_token_ms': None, 'sample': '', 'roles': []}
    key = ''

    def step(name: str, status: str, began: float, detail: str) -> None:
        steps.append({'name': name, 'status': status, 'ms': int((perf_counter() - began) * 1000),
                      'detail': detail[:200]})

    def finish(code: str, message: str | None = None) -> dict:
        report['code'] = code
        report['ok'] = code == 'ok'
        text = message or SERVER_FAILURES[code]
        report['message'] = text.replace(key, '[key hidden]') if key else text
        if code not in ('bad_address', 'bad_model', 'no_key'):
            note_server_result(settings, report['ok'], code)
        return report

    try:
        endpoint = validate_lan_endpoint(getattr(settings, 'server_endpoint', ''),
                                         allow_cgnat=getattr(settings, 'allow_cgnat', False))
    except ValueError as exc:
        return finish('bad_address', str(exc))
    try:
        validate_alias(model)
    except ValueError as exc:
        return finish('bad_model', str(exc))
    key = get_api_key(STAR_SERVER) or ''
    if not key:
        return finish('no_key')
    root = endpoint[:-len('/v1')]
    auth = {'Authorization': f'Bearer {key}'}
    quick = httpx.Timeout(10.0, connect=5.0)
    limit = getattr(settings, 'server_timeout', 600)
    patient = httpx.Timeout(float(limit if type(limit) is int and 30 <= limit <= 1800 else 600), connect=5.0)

    # trust_env=False: a system proxy must never see LAN traffic or the key.
    with httpx.Client(timeout=quick, trust_env=False, follow_redirects=False, transport=transport) as client:
        # 1. Is the server process up? llama.cpp answers /health without a key.
        began = perf_counter()
        try:
            answer = client.get(root + '/health')
        except httpx.TimeoutException:
            step('health', 'failed', began, 'No answer')
            return finish('unreachable')
        except httpx.HTTPError:
            step('health', 'failed', began, 'Connection failed')
            return finish('unreachable')
        if answer.status_code == 503:
            step('health', 'failed', began, 'Loading its model')
            return finish('loading')
        if answer.status_code == 200:
            step('health', 'ok', began, 'Server is up')
        else:
            step('health', 'skipped', began, f'No health page (HTTP {answer.status_code})')

        # 2. Does the key work, and which models does the server offer?
        began = perf_counter()
        try:
            answer = client.get(endpoint + '/models', headers=auth)
        except httpx.TimeoutException:
            step('models', 'failed', began, 'No answer')
            return finish('timeout')
        except httpx.HTTPError:
            step('models', 'failed', began, 'Connection failed')
            return finish('unreachable')
        if answer.status_code != 200:
            code = 'not_compatible' if answer.status_code == 404 else server_failure_code(answer.status_code)
            step('models', 'failed', began, f'HTTP {answer.status_code}')
            return finish(code)
        try:
            listed = [item for item in answer.json().get('data', []) if isinstance(item, dict) and item.get('id')]
        except (ValueError, AttributeError):
            step('models', 'failed', began, 'Unreadable model list')
            return finish('not_compatible')
        offered = [str(item['id'])[:180] for item in listed][:100]
        known = set(offered)
        for item in listed:
            known.update(str(alias) for alias in item.get('aliases') or [] if isinstance(alias, str))
        report['models'] = offered
        # Which of the offered models does which job (star/server_roles.py). Read from the
        # list that was just fetched: no further request, and nothing is written to Settings.
        server_roles.remember_models(endpoint, listed)
        report['roles'] = server_roles.role_report(settings)
        step('models', 'ok', began, f'Key accepted, {len(offered)} model(s) offered')
        if not model:
            return finish('no_model')
        if known and model not in known:  # an empty list proves nothing: let the chat step decide
            return finish('unknown_model')

        # 3. Context size and slots. Informational: never fails the whole check.
        began = perf_counter()
        try:
            answer = client.get(root + '/props', params={'model': model}, headers=auth)
            facts = answer.json() if answer.status_code == 200 else {}
            context = (facts.get('default_generation_settings') or {}).get('n_ctx')
            slots = facts.get('total_slots')
        except (httpx.HTTPError, ValueError, AttributeError):
            context = slots = None
        if type(context) is int and context > 0:
            slots = slots if type(slots) is int and slots > 0 else 1
            report['context_tokens'], report['slots'] = context, slots
            remember_server_limits(endpoint, model, context, slots)
            step('limits', 'ok', began, f'{context} context tokens per request, {slots} parallel slot(s)')
        else:
            step('limits', 'skipped', began, 'Server did not report its limits')
        # Slots and context of the other role models, loaded ones only: on a llama.cpp
        # router, asking about a model that is not loaded would load it.
        server_roles.read_limits(client, root, endpoint, auth, skip=model)

        if not chat:
            return finish('ok', f'STAR Server is reachable, the key works and it offers {model}.')

        # 4. One tiny real completion, streamed so the first-token delay is measured.
        began = perf_counter()
        first = None
        text = ''
        body = {'model': model, 'stream': True, 'temperature': 0, 'max_tokens': 48, 'messages': [
            {'role': 'system', 'content': 'You are STAR. Reply briefly and plainly.'},
            {'role': 'user', 'content': 'Reply with the exact words: STAR is ready.'}]}
        try:
            with client.stream('POST', endpoint + '/chat/completions', json=body, headers=auth,
                               timeout=patient) as answer:
                if answer.status_code != 200:
                    detail = answer.read()[:2000].decode('utf-8', 'replace')
                    step('chat', 'failed', began, f'HTTP {answer.status_code}')
                    return finish(server_failure_code(answer.status_code, detail))
                if 'text/event-stream' in answer.headers.get('content-type', ''):
                    for line in answer.iter_lines():
                        item = parse_sse_data(line)
                        choices = item.get('choices') if item else None
                        delta = choices[0].get('delta') if isinstance(choices, list) and choices \
                            and isinstance(choices[0], dict) else None
                        piece = delta.get('content') if isinstance(delta, dict) else None
                        if isinstance(piece, str) and piece:
                            first = first if first is not None else perf_counter()
                            text += piece
                            if len(text) > 400:
                                break
                else:  # a server that ignored `stream` and sent one JSON body
                    choices = answer.read() and answer.json().get('choices')
                    if isinstance(choices, list) and choices:
                        text = str((choices[0].get('message') or {}).get('content') or '')
                        first = perf_counter()
        except httpx.TimeoutException:
            step('chat', 'failed', began, 'No answer in time')
            return finish('timeout')
        except (httpx.HTTPError, ValueError, AttributeError):
            step('chat', 'failed', began, 'Connection failed')
            return finish('unreachable')
        sample = text.strip().replace(key, '[key hidden]')[:180]
        if not sample:
            step('chat', 'failed', began, 'No visible text')
            return finish('empty_reply')
        report['sample'] = sample
        report['first_token_ms'] = int(((first or perf_counter()) - began) * 1000)
        step('chat', 'ok', began, f'First words after {report["first_token_ms"]} ms')
        return finish('ok', f'STAR Server is ready. {model} answered a real test prompt.')
