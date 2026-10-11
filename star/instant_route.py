"""Conservative, loaded-only quick answers from the PC's loopback model.

Eligibility is pure. The I/O helpers never start, download, or switch models;
a failed local attempt is discarded before the ordinary STAR Server path runs.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
import time

import httpx

from .brain_router import _CODING, _DEEP, deep_request, grounding_plan, is_roblox_dev_prompt, is_roblox_task


_COMPLEX = re.compile(
    r"\b(?:current|latest|today|tomorrow|yesterday|news|weather|price|"
    r"search|look\s?up|browse|cite|sources?|documentation|docs|research|compare|"
    r"write|build|create|make|generate|edit|analy[sz]e|implement|"
    r"explain\s+in\s+detail|step.by.step)\b",
    re.IGNORECASE,
)
_REFERENTIAL = re.compile(
    r"\b(?:it|this|that|same|again|those|these|them|instead|previous|earlier)\b"
    r"|^\s*(?:and|but|what about|how about)\b", re.IGNORECASE,
)
_LOOPBACK = re.compile(r"^http://(?:127\.0\.0\.1|localhost):\d{2,5}/v1/?$")


@dataclass(frozen=True)
class InstantDecision:
    use_local: bool
    reason: str


@dataclass(frozen=True)
class InstantAnswer:
    text: str
    model: str
    first_token_ms: int
    tokens_per_second: float
    estimated_tokens: bool


def decide_instant_route(
    prompt: str, *, mode: str, provider: str, enabled: bool,
    installed: bool, loaded_model: str, attachments: int = 0, tools: bool = False,
    research: bool = False, documentation: bool = False, deep: bool = False,
    followup: bool = False,
) -> InstantDecision:
    """A zero-I/O, fail-closed route table. Model readiness is supplied by the caller."""
    if provider != "lan":
        return InstantDecision(False, "provider")
    if not enabled or not installed or not loaded_model:
        return InstantDecision(False, "not-ready")
    if mode not in ("fast", "auto"):
        return InstantDecision(False, "mode")
    if attachments or tools or research or documentation or deep or followup:
        return InstantDecision(False, "needs-capability")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 180:
        return InstantDecision(False, "length")
    if len(prompt.split()) > 30 or "\n" in prompt or "`" in prompt:
        return InstantDecision(False, "complex")
    requested_deep, _ = deep_request(prompt)
    if (requested_deep or is_roblox_task(prompt) or is_roblox_dev_prompt(prompt)
            or _CODING.search(prompt) or _DEEP.search(prompt) or _COMPLEX.search(prompt)
            or _REFERENTIAL.search(prompt)):
        return InstantDecision(False, "complex")
    if grounding_plan(prompt, mode=mode).retrieve != "none":
        return InstantDecision(False, "documentation")
    return InstantDecision(True, "instant")


def loaded_model_from_listing(listed) -> str:
    """Only a resident text model. An unmarked single-model server is already loaded."""
    if not isinstance(listed, list):
        return ""
    candidates = []
    unmarked = []
    for item in listed[:50]:
        if not isinstance(item, dict):
            continue
        model = item.get("id")
        if not isinstance(model, str) or not re.fullmatch(r"[^\s\x00-\x1f\x7f]{1,180}", model):
            continue
        architecture = item.get("architecture")
        modalities = architecture.get("input_modalities") if isinstance(architecture, dict) else None
        if isinstance(modalities, list) and "text" not in modalities:
            continue
        status = item.get("status")
        if isinstance(status, dict):
            if status.get("value") == "loaded" and not status.get("failed"):
                candidates.append(model)
        elif status is None:
            unmarked.append(model)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates and len(unmarked) == 1 and len(listed) == 1:
        return unmarked[0]
    return ""


async def loaded_local_model(endpoint: str, *, client=None) -> str:
    """Ask only loopback /models; listing never starts an unloaded router model."""
    if not isinstance(endpoint, str) or not _LOOPBACK.fullmatch(endpoint):
        return ""
    if client is None:
        async with httpx.AsyncClient(timeout=0.7, trust_env=False, follow_redirects=False) as local:
            return await loaded_local_model(endpoint, client=local)
    try:
        response = await client.get(endpoint.rstrip("/") + "/models")
        response.raise_for_status()
        return loaded_model_from_listing(response.json().get("data"))
    except (httpx.HTTPError, OSError, ValueError, TypeError, AttributeError):
        return ""


async def complete_instant(client, model: str, prompt: str, *,
                           clock=time.monotonic, first_token_deadline: float = 1.75,
                           total_deadline: float = 12.0) -> InstantAnswer:
    """Buffer the entire response: partial local output must never leak into fallback."""
    if not model or not prompt:
        raise ValueError("Instant model and prompt are required")
    pieces: list[str] = []
    first_at = last_at = None
    observed = reported = 0
    stream = None
    started = clock()

    def accept(chunk):
        nonlocal first_at, last_at, observed, reported
        usage = getattr(chunk, "usage", None)
        counted = getattr(usage, "completion_tokens", None)
        if type(counted) is int and counted > 0:
            reported = counted
        choices = getattr(chunk, "choices", None)
        if not choices:
            return
        delta = getattr(choices[0], "delta", None)
        part = getattr(delta, "content", None)
        if not isinstance(part, str) or not part:
            return
        if first_at is None:
            first_at = clock()
        last_at = clock()
        pieces.append(part)
        observed += 1

    try:
        async with asyncio.timeout(total_deadline):
            async with asyncio.timeout(first_token_deadline):
                stream = await client.chat.completions.create(
                    model=model, messages=[{"role": "system", "content":
                        "Answer the user's simple question briefly and accurately."},
                        {"role": "user", "content": prompt}],
                    temperature=0, max_tokens=160, stream=True)
                if not hasattr(stream, "__aiter__"):
                    raise RuntimeError("Instant model did not stream")
                async for chunk in stream:
                    accept(chunk)
                    if first_at is not None:
                        break
                if first_at is None:
                    raise RuntimeError("Instant model returned no text")
            async for chunk in stream:
                accept(chunk)
    finally:
        if stream is not None and callable(getattr(stream, "aclose", None)):
            await stream.aclose()
    answer = "".join(pieces)
    if not answer.strip() or first_at is None or last_at is None:
        raise RuntimeError("Instant model returned no answer")
    duration = max(0.001, last_at - first_at)
    tokens = reported or observed
    return InstantAnswer(answer, model, max(0, int((first_at - started) * 1000)),
                         round(max(0, tokens - 1) / duration, 1), not bool(reported))


async def answer_on_pc(endpoint: str, model: str, prompt: str):
    """Single restricted loopback completion; no system proxy or cloud fallback."""
    if not _LOOPBACK.fullmatch(endpoint):
        raise ValueError("Instant model must use the on-device loopback endpoint")
    from openai import AsyncOpenAI
    async with httpx.AsyncClient(timeout=12, trust_env=False, follow_redirects=False) as transport:
        client = AsyncOpenAI(base_url=endpoint, api_key="local-only", http_client=transport, max_retries=0)
        try:
            return await complete_instant(client, model, prompt)
        finally:
            await client.close()
