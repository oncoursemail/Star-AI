"""Measured, bounded deadlines and partial streaming for read-only STAR specialists.

Rates are per provider endpoint and model, held only in process memory. No
model output, private address, credentials or metrics are written to disk.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import math
from time import monotonic


@dataclass(frozen=True)
class DeadlinePolicy:
    min_seconds: float = 30.0
    max_seconds: float = 900.0
    first_token_seconds: float = 20.0
    safety_factor: float = 1.5
    fallback_tps: float = 5.0

    def __post_init__(self):
        numbers = (self.min_seconds, self.max_seconds, self.first_token_seconds,
                   self.safety_factor, self.fallback_tps)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in numbers):
            raise ValueError("Team deadline settings must be finite numbers")
        if not (0.1 <= self.min_seconds <= self.max_seconds <= 1800
                and 0 <= self.first_token_seconds <= 120
                and 1 <= self.safety_factor <= 4 and 0.1 <= self.fallback_tps <= 200):
            raise ValueError("Team deadline settings are outside safe bounds")

    def stage_seconds(self, token_budget: int, measured_tps: float | None = None) -> float:
        if type(token_budget) is not int or not 1 <= token_budget <= 4096:
            raise ValueError("Invalid specialist token budget")
        rate = measured_tps
        if (type(rate) not in (int, float) or not math.isfinite(rate)
                or rate <= 0):
            rate = self.fallback_tps
        seconds = self.first_token_seconds + token_budget / rate * self.safety_factor
        return max(self.min_seconds, min(self.max_seconds, seconds))

    def overall_seconds(self, specialist_tokens: int, synthesis_tokens: int,
                        parallel: int, measured_tps: float | None = None) -> float:
        if parallel not in (1, 2):
            raise ValueError("Teams supports only one or two simultaneous requests")
        # Three specialists occupy two or three batches; synthesis follows all three.
        batches = (3 + parallel - 1) // parallel
        duration = (batches * self.stage_seconds(specialist_tokens, measured_tps)
                    + self.stage_seconds(synthesis_tokens, measured_tps) + 30)
        return min(3600.0, duration)


class ProviderSpeeds:
    """Conservative rolling observed *per-request* output speed, not a benchmark."""

    def __init__(self, *, clock=monotonic):
        self.clock = clock
        self._rates: dict[tuple[str, ...], float] = {}

    def get(self, key: tuple[str, ...]) -> float | None:
        return self._rates.get(key)

    def observe(self, key: tuple[str, ...], tokens: int, generation_seconds: float) -> None:
        if (type(tokens) is not int or tokens < 16
                or type(generation_seconds) not in (int, float)
                or not math.isfinite(generation_seconds) or generation_seconds < 0.2):
            return
        measured = tokens / generation_seconds
        if not 0.1 <= measured <= 1000:
            return
        previous = self._rates.get(key)
        if key not in self._rates and len(self._rates) >= 64:
            self._rates.pop(next(iter(self._rates)))
        self._rates[key] = measured if previous is None else 0.7 * previous + 0.3 * measured


SPEEDS = ProviderSpeeds()


async def collect_text(client, *, model: str, messages: list[dict], max_tokens: int,
                       speeds: ProviderSpeeds, speed_key: tuple[str, ...],
                       on_partial=None, forbid_tools: bool = False,
                       max_chars: int = 12000) -> str:
    """Collect a streaming model answer, exposing text before cancellation.

    Completion token usage is preferred; when unavailable, approximate tokens
    conservatively from generated characters. Non-streaming test transports are
    accepted but cannot provide a trustworthy generation-speed sample.
    """
    response = await client.chat.completions.create(
        model=model, messages=messages, temperature=0, max_tokens=max_tokens,
        stream=True, stream_options={"include_usage": True},
    )
    if not hasattr(response, "__aiter__"):
        if not getattr(response, "choices", None):
            raise RuntimeError("The model returned no completion choices")
        message = response.choices[0].message
        if forbid_tools and getattr(message, "tool_calls", None):
            raise ValueError("Read-only specialist returned unexpected tool calls")
        return str(getattr(message, "content", "") or "")[:max_chars]

    pieces = []
    size = 0
    first_visible = None
    usage_tokens = None
    try:
        async for packet in response:
            usage = getattr(packet, "usage", None)
            token_count = getattr(usage, "completion_tokens", None)
            if type(token_count) is int and token_count > 0:
                usage_tokens = token_count
            for choice in getattr(packet, "choices", ()) or ():
                delta = getattr(choice, "delta", None)
                if forbid_tools and getattr(delta, "tool_calls", None):
                    raise ValueError("Read-only specialist returned unexpected tool calls")
                part = getattr(delta, "content", None)
                if not isinstance(part, str) or not part:
                    continue
                if first_visible is None:
                    first_visible = speeds.clock()
                if size < max_chars:
                    part = part[:max_chars - size]
                    pieces.append(part)
                    size += len(part)
                    if on_partial:
                        on_partial("".join(pieces))
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result
    answer = "".join(pieces)
    if answer and first_visible is not None:
        tokens = usage_tokens or max(1, len(answer) // 4)
        speeds.observe(speed_key, tokens, speeds.clock() - first_visible)
    return answer
