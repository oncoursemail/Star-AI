"""Opt-in, bounded recovery of code answers cut off by a model token limit.

This repairs Markdown fences, not Luau semantics. A complete answer is returned
byte-for-byte. A reply that cannot be completed is labelled unsafe to copy.
No server-specific grammar or response format is required.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Awaitable, Callable

ENV_VAR = "STAR_COMPLETE_CODE_ANSWERS"
CONTINUATION_TOKENS = 900
MAX_CONTINUATIONS = 2
FENCE = chr(96) * 3
INCOMPLETE_CODE = (
    "\n\n*(STAR could not finish this code. The code block above is incomplete; "
    "do not run it as-is.)*"
)
INCOMPLETE_TEXT = "\n\n*(STAR could not finish this answer; its ending is incomplete.)*"
_FENCE_LINE = re.compile(r"^[ ]{0,3}(?P<run>(?:\x60{3,}|~{3,}))(?P<rest>[^\r\n]*)$", re.M)


def enabled(environ: dict[str, str] | None = None) -> bool:
    """Only an exact opt-in turns recovery on for the app's regular provider path."""
    source = os.environ if environ is None else environ
    return source.get(ENV_VAR, "").strip().lower() == "on"


def open_fence(answer: str) -> tuple[str, int, int] | None:
    """Return (marker, length, offset) of the last unclosed Markdown code fence."""
    active: tuple[str, int, int] | None = None
    for found in _FENCE_LINE.finditer(answer):
        run, rest = found["run"], found["rest"]
        if active is None:
            if run[0] == FENCE[0] and FENCE[0] in rest:
                continue  # backtick info strings cannot contain a backtick
            active = (run[0], len(run), found.start())
        elif run[0] == active[0] and len(run) >= active[1] and not rest.strip():
            active = None
    return active


def needs_continuation(answer: str, finish_reason: str | None) -> bool:
    return finish_reason == "length" or open_fence(answer) is not None


def _next_request(answer: str) -> tuple[str, str]:
    fence = open_fence(answer)
    if fence is None:
        return answer, (
            "Your preceding answer was cut off by the token limit. Continue exactly "
            "from where it stopped. Do not repeat any existing text. Close any new code "
            "fences and finish the original answer."
        )
    # A token cap can split a Luau string, identifier, or keyword. Replace the
    # entire last line to avoid joining 'pri' to 'print' or half-quoted strings.
    kept = answer if answer.endswith("\n") else answer[:answer.rfind("\n") + 1]
    cut_line = answer[len(kept):]
    last_lines = [line.strip() for line in kept.splitlines() if line.strip()]
    last = last_lines[-1] if last_lines else ""
    instruction = (
        "Your preceding answer ended inside an OPEN Markdown code fence. "
        "Supply ONLY the remaining code lines, beginning with a FULL replacement "
        "for the unfinished final line if there is one. Do not repeat completed "
        "lines or start the script again. Close all open Luau constructs, then "
        "close the existing Markdown fence. Do not put prose before the code.\n"
        + (f"Last completed line: {last[:160]}\n" if last else "")
        + (f"Cut-off line (REPLACE, do not append): {cut_line[:160]}\n" if cut_line else "")
    )
    return kept, instruction


def _continued_body(reply: str) -> str:
    """Remove a newly opened fence or leading prose from a model continuation."""
    text = reply.lstrip("\r\n")
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    first = _FENCE_LINE.fullmatch(lines[0].rstrip("\r\n"))
    if first and (first["rest"].strip() or len(lines) > 1):
        return "".join(lines[1:])
    # Some models put explanation or sources *before* their fenced continuation.
    matches = list(_FENCE_LINE.finditer(text))
    if len(matches) >= 2 and matches[0].start() > 0:
        return text[matches[0].end():].lstrip("\r\n")
    return text


def splice(kept: str, reply: str) -> str:
    """Join continuation lines inside the original fence without a second opener."""
    body = _continued_body(reply)
    fence = open_fence(kept)
    if fence is not None and "\n" in kept[fence[2]:]:
        existing_code = kept[fence[2]:].split("\n", 1)[1]
        head = [line.strip() for line in existing_code.splitlines() if line.strip()][:2]
        beginning = [line.strip() for line in body.splitlines() if line.strip()][:2]
        if len(head) == 2 and head == beginning:
            return kept[:fence[2]] + kept[fence[2]:].split("\n", 1)[0] + "\n" + body
    left = kept.splitlines()
    right = body.splitlines(keepends=True)
    overlap = 0
    for count in range(min(5, len(left), len(right)), 0, -1):
        if ([line.strip() for line in left[-count:]] ==
                [line.strip() for line in right[:count]] and
                any(line.strip() for line in right[:count])):
            overlap = count
            break
    return kept + "".join(right[overlap:])


def _failed(answer: str) -> str:
    fence = open_fence(answer)
    if fence is not None:
        return answer.rstrip("\r\n") + "\n" + fence[0] * fence[1] + INCOMPLETE_CODE
    return answer + INCOMPLETE_TEXT


async def complete(
    answer: str,
    finish_reason: str | None,
    *,
    history: list[dict],
    send: Callable[[list[dict], int], Awaitable[object]],
    event: Callable[[dict], None],
) -> str:
    """At most two tool-free provider continuations, never silently discarding code."""
    if not needs_continuation(answer, finish_reason):
        return answer
    for _ in range(MAX_CONTINUATIONS):
        kept, instruction = _next_request(answer)
        continuation_messages = [
            *history,
            {"role": "assistant", "content": kept},
            {"role": "user", "content": instruction},
        ]
        event({"event": "answer_continuing"})
        try:
            response = await send(continuation_messages, CONTINUATION_TOKENS)
            choice = response.choices[0]
            text = choice.message.content
            if not isinstance(text, str) or not text.strip() or getattr(choice.message, "tool_calls", None):
                break
        except asyncio.CancelledError:
            raise
        except Exception:
            break
        answer = splice(kept, text) if open_fence(kept) else kept + text
        finish_reason = getattr(choice, "finish_reason", None)
        if not needs_continuation(answer, finish_reason):
            return answer
    return _failed(answer)
