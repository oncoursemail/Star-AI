"""STAR's Stop button cancels multi-agent Teams, not only plain chat."""
import asyncio
from threading import Event
import pytest
from star.team_cancellation import run_until_cancelled


def test_cancel_team_cleans_up_all_inflight_tasks():
    stop = Event()
    entered = asyncio.Event()
    workers_cancelled = []
    async def slow_team():
        async def worker():
            try:
                entered.set()
                await asyncio.sleep(45)
            except asyncio.CancelledError:
                workers_cancelled.append(True)
                raise
        t = asyncio.create_task(worker())
        try:
            await t
        finally:
            if not t.done():
                t.cancel()
                await asyncio.gather(t,return_exceptions=True)
    async def scenario():
        pending = asyncio.create_task(run_until_cancelled(
            slow_team(), is_cancelled=stop.is_set, poll_seconds=.015))
        # Event-driven startup avoids a 150 ms polling race on busy CI runners.
        await asyncio.wait_for(entered.wait(), timeout=1.5)
        stop.set()
        with pytest.raises(RuntimeError,match="cancelled by user"):
            await asyncio.wait_for(pending,timeout=1.5)
    asyncio.run(scenario())
    assert workers_cancelled == [True]


def test_uncancelled_team_result_survives():
    async def work():
        return {"answer":"completed"}
    answer=asyncio.run(run_until_cancelled(work(),is_cancelled=Event().is_set))
    assert answer=={"answer":"completed"}


def test_cancel_contract_refuses_invalid_probe():
    async def operation():return 42
    with pytest.raises(TypeError):
        asyncio.run(run_until_cancelled(operation(),is_cancelled=None))
