"""Parsing of the teachers' replies."""
from __future__ import annotations

import re

_FENCE = re.compile(r"```[ \t]*(?:luau|lua|Luau|Lua)?[ \t]*\n(.*?)```", re.DOTALL)
_ANY_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_PROMPT_HEAD = re.compile(r"^#{2,4}[ \t]*PROMPT[ \t]*:?[ \t]*$", re.I | re.M)
_TESTS_HEAD = re.compile(r"^#{2,4}[ \t]*TESTS?[ \t]*:?[ \t]*$", re.I | re.M)


def luau_blocks(text: str) -> list[str]:
    blocks = [b.strip("\n") for b in _FENCE.findall(text)]
    return blocks or [b.strip("\n") for b in _ANY_FENCE.findall(text)]


def parse_task(reply: str) -> tuple[str, str, str]:
    """(prompt, tests, problem). `problem` is "" when both parts were found."""
    p = _PROMPT_HEAD.search(reply)
    t = _TESTS_HEAD.search(reply)
    if not p or not t or t.start() < p.end():
        return "", "", "reply lacks the PROMPT and TESTS sections"
    prompt = reply[p.end():t.start()].strip()
    prompt = re.sub(r"^```[^\n]*\n|\n```$", "", prompt).strip()
    blocks = luau_blocks(reply[t.end():])
    if not blocks:
        return prompt, "", "TESTS section has no code block"
    return prompt, max(blocks, key=len), ""


def parse_solution(reply: str) -> tuple[str, str]:
    """(code, problem): the longest fenced code block of the reply."""
    blocks = luau_blocks(reply)
    if not blocks:
        return "", "reply has no code block"
    return max(blocks, key=len).strip("\n") + "\n", ""


def parse_ideas(reply: str, limit: int = 8) -> list[str]:
    ideas = []
    for line in reply.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip().strip("\"'")
        if 20 <= len(line) <= 260 and not line.endswith(":"):
            ideas.append(line)
    return ideas[:limit]
