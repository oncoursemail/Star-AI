"""On-device, measured local inference benchmarking (never fabricated metrics).

Run explicitly against an already-started loopback model, or with `server=True`
against the owner's STAR Server on the LAN. Benchmark requests contain no chats,
project data or tool calls; nothing leaves the owner's machines.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from statistics import median
from time import monotonic

from .desktop_core import Settings


@dataclass(frozen=True)
class Probe:
    elapsed_ms: int
    output_tokens: int | None
    ok: bool


def summarize_probes(samples: list[Probe], wall_ms: int, *, parallel: int) -> dict:
    if not samples or wall_ms <= 0 or not 1 <= parallel <= 4:
        raise ValueError("No valid measurements")
    succeeded = [x for x in samples if x.ok]
    durations = sorted(s.elapsed_ms for s in succeeded)
    # Partial usage metadata would undercount output and mislead comparisons.
    tokens = [x.output_tokens for x in succeeded] if all(
        x.output_tokens is not None for x in succeeded
    ) and succeeded else []
    p95 = durations[max(0, (len(durations) * 95 + 99) // 100 - 1)] if durations else None
    return {
        "requests": len(samples),
        "successful": len(succeeded),
        "failed": len(samples) - len(succeeded),
        "parallel_limit": parallel,
        "wall_ms": wall_ms,
        "median_request_ms": round(median(durations), 1) if durations else None,
        "p95_request_ms": p95,
        "requests_per_second": round(len(succeeded) * 1000 / wall_ms, 3),
        "output_tokens": sum(tokens) if tokens else None,
        "output_tokens_per_second": round(sum(tokens) * 1000 / wall_ms, 2) if tokens else None,
        "note": "Measured requests to the owner's own model only. No GPU speedup or model-quality claim is implied.",
    }


async def benchmark_local_model(
    endpoint: str,
    model: str,
    *,
    requests: int = 4,
    parallel: int = 1,
    client=None,
    server: bool = False,
) -> dict:
    """Measure real requests. `server=True` treats `endpoint` as the STAR Server address."""
    if server:
        # Same private-IP validation and keyring key as normal STAR Server chat.
        config = Settings(provider="star_server", server_endpoint=endpoint, model=model)
    else:
        config = Settings(endpoint=endpoint, model=model)
    config.validate()
    if not model.strip() or not 1 <= requests <= 12 or not 1 <= parallel <= 4:
        raise ValueError("Benchmark requires a model, 1..12 requests and 1..4 slots")
    own = client is None
    if own:
        from .providers import open_client
        client = open_client(config, request_timeout=None if server else 90.0)
    sem = asyncio.Semaphore(parallel)

    async def one() -> Probe:
        async with sem:
            began = monotonic()
            try:
                result = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a local model benchmark. Reply briefly."},
                        {"role": "user", "content": "Describe a simple geometric square in one sentence."},
                    ],
                    max_tokens=96, temperature=0,
                )
                output = str(result.choices[0].message.content or "").strip()
                if not output:
                    raise RuntimeError("Empty model output")
                usage = getattr(result, "usage", None)
                count = getattr(usage, "completion_tokens", None) if usage else None
                if not isinstance(count, int) or count < 0:
                    count = None
                return Probe(int((monotonic()-began)*1000),count,True)
            except Exception:
                return Probe(int((monotonic()-began)*1000),None,False)

    started = monotonic()
    try:
        samples = await asyncio.gather(*(one() for _ in range(requests)))
        wall = max(1,int((monotonic() - started)*1000))
        return summarize_probes(samples,wall,parallel=parallel)
    finally:
        if own:
            await client.close()
