"""Cooperative user cancellation for bounded, read-only STAR Teams.

Cancellation is distinct from a timeout and never produces a success record.
When the supervising task is cancelled, run_plan's finally block cancels its
active specialist model requests.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def run_until_cancelled(
    operation: Awaitable[T], *,
    is_cancelled: Callable[[], bool],
    poll_seconds: float = 0.1,
) -> T:
    """Cancel an async team operation when the user presses Stop.

    Caller owns the independent, per-run cancellation event. This helper never
    spawns background threads and never retries model requests after Stop.
    """
    if not callable(is_cancelled) or not 0.01 <= poll_seconds <= 1.0:
        # Fail before scheduling any worker; explicitly close a raw coroutine
        # to avoid leaving a ResourceWarning in an otherwise green test suite.
        if asyncio.iscoroutine(operation):
            operation.close()
        if not callable(is_cancelled):
            raise TypeError("Cancellation probe must be callable")
        raise ValueError("Polling interval outside supported bounds")
    job = asyncio.ensure_future(operation)
    try:
        while True:
            if is_cancelled():
                raise RuntimeError("STAR Teams request cancelled by user")
            done, _ = await asyncio.wait({job}, timeout=poll_seconds)
            if done:
                return await job
    finally:
        if not job.done():
            job.cancel()
            await asyncio.gather(job, return_exceptions=True)
