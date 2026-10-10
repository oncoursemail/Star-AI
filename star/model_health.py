"""Actual local chat-completion diagnostics (not just a /models availability probe).

Qwen3.5/llama.cpp strict templates reject second or later system messages.
Keep a single first system role in both the normal agent and this smoke test.
"""
from __future__ import annotations

from .desktop_core import Settings
from .providers import connection_for


def explain_model_failure(error: Exception) -> str:
    """Return a short actionable message without leaking raw server/Jinja internals."""
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
        return 'Cannot reach STAR Brain. Start it in the Brain tab, then test the connection again.'
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


async def probe_chat_endpoint(settings: Settings, timeout: float = 120.0) -> dict:
    """Issue a real completion to the configured loopback model and inspect text.

    A successful GET /models alone does not prove the chat template can render.
    This is a tiny, read-only health check; it performs no Studio/tool operations.
    """
    from openai import AsyncOpenAI
    settings.validate()
    if not settings.model.strip():
        raise ValueError('Select a model before testing its response')
    endpoint, key = connection_for(settings)
    async with AsyncOpenAI(base_url=endpoint, api_key=key,
                            timeout=timeout, max_retries=0) as client:
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
            raise RuntimeError('STAR Brain returned no completion choices')
        response = str(completion.choices[0].message.content or '').strip()
        if not response:
            raise RuntimeError('STAR Brain returned no visible text. Check the model template and reasoning settings.')
        return {'ok': True, 'model': settings.model, 'sample': response[:180]}
