"""One direct question to the image-capable model, outside the chat history.

Used by the steps that need a short, bounded look at pictures (compare with a reference, a video's
sampled frames). The chat itself still sends attachments through `star.desktop_core.run_task`.
Images are re-encoded by `star.media.image_part` before they leave: no metadata, no file paths.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .media import image_part

MAX_IMAGES = 6          # the chat allows 4; a video question may send a few more small frames


@dataclass(frozen=True)
class Seen:
    text: str
    model: str
    seconds: float
    images: int


def vision_model(settings) -> str:
    """The model that reads images for this provider ('' when none is configured)."""
    from . import server_roles
    chosen = server_roles.effective(settings)
    return (getattr(chosen, 'vision_model', '') or getattr(chosen, 'model', '') or '').strip()


def ask(settings, question: str, images: list[Path], *, system: str = '', max_tokens: int = 500,
        timeout: float = 600.0, cancelled: Callable[[], bool] | None = None) -> Seen:
    """Ask the vision model about `images` and return its words with the time it took."""
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 12000:
        raise ValueError('Question must be 1-12,000 characters')
    if not images or len(images) > MAX_IMAGES:
        raise ValueError(f'Send 1-{MAX_IMAGES} images')
    model = vision_model(settings)
    if not model:
        raise ValueError('No image-capable model is selected. Choose a model in Settings first.')
    from .desktop_core import picture_limit
    limit = picture_limit(settings)
    parts = [{'type': 'text', 'text': question.strip()}] + [image_part(Path(image), limit) for image in images]
    messages = ([{'role': 'system', 'content': system}] if system else []) + [{'role': 'user', 'content': parts}]

    async def run() -> str:
        from .providers import open_client, provider_kind
        # llama.cpp (the STAR Server and the on-device brain): answer directly. A short factual
        # look at pictures must not spend minutes of a CPU server's time on hidden reasoning.
        own = provider_kind(settings) in ('lan', 'local')
        extra = {'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}} if own else {}
        async with open_client(settings, request_timeout=timeout) as client:
            job = asyncio.create_task(client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=0.2, **extra))
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if cancelled is not None and cancelled():
                        raise RuntimeError('STAR task cancelled by user')
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f'The image model did not answer within {int(timeout)} seconds')
                    done, _ = await asyncio.wait({job}, timeout=0.2)
                    if done:
                        reply = await job
                        return (reply.choices[0].message.content or '').strip()
            finally:
                if not job.done():
                    job.cancel()
                    await asyncio.gather(job, return_exceptions=True)

    started = time.monotonic()
    text = asyncio.run(run())
    if not text:
        raise RuntimeError('The image model returned an empty answer')
    return Seen(text=text, model=model, seconds=round(time.monotonic() - started, 2), images=len(images))
