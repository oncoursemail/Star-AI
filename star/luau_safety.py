"""Opt-in, offline Luau lifetime and scheduling checks.

These are token-based heuristics, not a Luau parser or proof of control flow.
The caller supplies trusted script_class metadata; unclassified sources are
never assumed to be server scripts. No file, network or Studio operations.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .luau_lint import Finding, _tokens


@dataclass(frozen=True)
class _Block:
    kind: str
    start: int
    end: int


_RUN_EVENTS = frozenset({
    "Heartbeat", "Stepped", "RenderStepped", "PreSimulation",
    "PostSimulation", "PreRender", "FixedHeartbeat",
})
_REWARDS = frozenset({
    "leaderstats", "coins", "cash", "money", "gold", "xp", "experience",
    "points", "score", "currency", "reward", "rewards",
})
_REWARD_CALLS = frozenset({
    "grantreward", "givereward", "awardreward", "reward", "addcoins",
    "givecoins", "addcash", "givecash", "addmoney", "givemoney",
    "addpoints", "givepoints", "addxp", "givexp", "awardcoins",
    "awardpoints",
})
_GUARDS = frozenset({
    "debounce", "cooldown", "cooldowns", "touchcooldown", "busy",
    "claimed", "collected", "processed", "rewarded", "hitonce",
    "touching", "canhit", "canclaim", "cancollect", "cangrant",
})
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_RUN_SERVICE_LITERAL = re.compile(r"""\s*(['"])RunService\1\s*\Z""")


def _close(words: list[str], start: int, opening: str = "(", closing: str = ")") -> int | None:
    if start >= len(words) or words[start] != opening:
        return None
    depth = 0
    for i in range(start, len(words)):
        if words[i] == opening:
            depth += 1
        elif words[i] == closing:
            depth -= 1
            if depth == 0:
                return i
    return None


def _blocks(words: list[str]) -> list[_Block]:
    """Match complete Lua blocks, including nested callbacks and paired loop do."""
    stack: list[tuple[str, int, bool]] = []
    result: list[_Block] = []
    for i, word in enumerate(words):
        if word in ("function", "if", "while", "for", "repeat"):
            stack.append((word, i, False))
        elif word == "do":
            if stack and stack[-1][0] in ("while", "for") and not stack[-1][2]:
                kind, start, _ = stack[-1]
                stack[-1] = (kind, start, True)
            else:
                stack.append(("do", i, True))
        elif word == "end" and stack and stack[-1][0] != "repeat":
            kind, start, _ = stack.pop()
            result.append(_Block(kind, start, i))
        elif word == "until" and stack and stack[-1][0] == "repeat":
            kind, start, _ = stack.pop()
            result.append(_Block(kind, start, i))
    return result


def _yield_in_body(words: list[str], start: int, end: int, blocks: list[_Block]) -> bool:
    """A spawned callback's wait does not yield the surrounding busy loop."""
    nested = {b.start: b.end for b in blocks if b.kind == "function" and start <= b.start < b.end < end}
    i = start
    while i < end:
        if i in nested:
            i = nested[i] + 1
            continue
        word = words[i]
        call = words[i + 1:i + 2] == ["("]
        if word == "wait" and call and (
            i == 0 or words[i - 1] not in (".", ":") or words[max(0, i - 2):i] == ["task", "."]
        ):
            return True
        if word in ("Wait", "WaitForChild") and call and i > 0 and words[i - 1] == ":":
            return True
        if word == "yield" and call and words[max(0, i - 2):i] == ["coroutine", "."]:
            return True
        i += 1
    return False


def _top_level_args(words: list[str], opening: int, closing: int) -> list[list[str]]:
    parts: list[list[str]] = [[]]
    stack: list[str] = []
    matches = {")": "(", "]": "[", "}": "{"}
    for word in words[opening + 1:closing]:
        if word in ("(", "[", "{"):
            stack.append(word)
        elif word in matches and stack and stack[-1] == matches[word]:
            stack.pop()
        if word == "," and not stack:
            parts.append([])
        else:
            parts[-1].append(word)
    return parts


def _runservice_receivers(code: str, ts: list, words: list[str]) -> tuple[set[str], dict[int, int]]:
    aliases = {"RunService"}
    inline: dict[int, int] = {}
    for i, word in enumerate(words):
        if word != "GetService" or i < 2 or words[i - 2:i] != ["game", ":"]:
            continue
        par = i + 1
        end = _close(words, par)
        if end is None:
            continue
        raw_arg = code[ts[par].offset + 1:ts[end].offset]
        if _RUN_SERVICE_LITERAL.fullmatch(raw_arg) is None:
            continue
        inline[end] = i - 2
        if i >= 4 and words[i - 3] == "=" and _IDENTIFIER.fullmatch(words[i - 4]):
            aliases.add(words[i - 4])
    return aliases, inline


def _touch_handlers(words: list[str], blocks: list[_Block]) -> list[tuple[int, _Block]]:
    funcs = [b for b in blocks if b.kind == "function"]
    out: list[tuple[int, _Block]] = []
    for i, word in enumerate(words):
        if word != "Touched" or words[i + 1:i + 4] != [":", "Connect", "("]:
            continue
        end = _close(words, i + 3)
        if end is None:
            continue
        handler = next((b for b in funcs if i + 3 < b.start < b.end < end), None)
        if handler is not None:
            out.append((i, handler))
    return out


def _assigned_name(words: list[str], receiver_start: int) -> str | None:
    if receiver_start >= 2 and words[receiver_start - 1] == "=":
        name = words[receiver_start - 2]
        return name if _IDENTIFIER.fullmatch(name) else None
    return None


def _disconnected(words: list[str], name: str | None) -> bool:
    return name is not None and any(
        words[i:i + 4] == [name, ":", "Disconnect", "("] for i in range(len(words))
    )


def _assigns(words: list[str], at: int) -> bool:
    if at >= len(words):
        return False
    if words[at] == "=":
        return words[at + 1:at + 2] != ["="]
    return words[at] in ("+", "-", "*", "/") and words[at + 1:at + 2] == ["="]


def _reward_at(words: list[str], start: int, end: int) -> int | None:
    for i in range(start, end):
        lower = words[i].lower()
        if lower in _REWARD_CALLS and words[i + 1:i + 2] == ["("] and words[i - 1:i] != ["function"]:
            return i
        if lower in _REWARDS and words[i - 1:i] != ["local"] and _assigns(words, i + 1):
            return i
        if words[i] == "Value" and words[i - 1:i] == ["."] and _assigns(words, i + 1):
            if any(part.lower() in _REWARDS for part in words[max(start, i - 8):i]):
                return i
    return None


def _guarded(words: list[str], start: int, reward: int) -> bool:
    """Require both a pre-award early exit and a pre-award state update."""
    checked: set[str] = set()
    for i in range(start, reward):
        if words[i] != "if":
            continue
        try:
            then = words.index("then", i + 1, min(reward, i + 20))
        except ValueError:
            continue
        condition = {word.lower() for word in words[i + 1:then]}
        if "return" in words[then + 1:min(reward, then + 16)]:
            checked.update(condition & _GUARDS)
    for i in range(start, reward):
        name = words[i].lower()
        if name not in checked:
            continue
        after = i + 1
        if words[after:after + 1] == ["["]:
            closing = _close(words, after, "[", "]")
            if closing is None:
                continue
            after = closing + 1
        if words[after:after + 1] != ["="]:
            continue
        value = words[after + 1:after + 2]
        if name.startswith("can") and value == ["false"]:
            return True
        if not name.startswith("can") and value not in ([], ["false"], ["nil"]):
            return True
    return False


def _server_wait_chains(words: list[str]) -> list[int]:
    reported: list[int] = []
    for i, word in enumerate(words):
        if word != "WaitForChild" or words[i - 1:i] != [":"] or words[i + 1:i + 2] != ["("]:
            continue
        par = i + 1
        end = _close(words, par)
        if end is None:
            continue
        count, missing = 1, not _timeout(words, par, end)
        pos = end + 1
        while pos < len(words):
            if words[pos:pos + 1] == ["."] and pos + 1 < len(words) and _IDENTIFIER.fullmatch(words[pos + 1]):
                pos += 2
            if words[pos:pos + 2] != [":", "WaitForChild"] or words[pos + 2:pos + 3] != ["("]:
                break
            nested = _close(words, pos + 2)
            if nested is None:
                break
            count += 1
            missing = missing or not _timeout(words, pos + 2, nested)
            pos = nested + 1
        if count >= 2 and missing:
            reported.append(i)
    return reported


def _timeout(words: list[str], par: int, end: int) -> bool:
    args = _top_level_args(words, par, end)
    return len(args) > 1 and bool(args[1]) and args[1] != ["nil"]


def _shadowed(words: list[str], blocks: list[_Block], index: int, name: str) -> bool:
    for j in range(index):
        if words[j:j + 2] in (["local", name], ["function", name]):
            return True
    for b in blocks:
        if b.kind != "function" or not b.start < index < b.end:
            continue
        par = b.start + 1
        if words[par:par + 1] != ["("]:
            # A named function has its opening paren after the name.
            par += 1
        end = _close(words, par)
        if end is not None and name in words[par + 1:end]:
            return True
    return False


def inspect_safety(code: str, *, script_class: str | None = None) -> list[Finding]:
    """Opt-in safety diagnostics, with rule id, line and actionable fix.

    script_class='Script' must come from a trusted caller, never code text.
    Unsupported dynamic control flow is ignored instead of guessing.
    """
    if not isinstance(code, str):
        raise TypeError("code must be str")
    if script_class not in (None, "Script", "LocalScript", "ModuleScript"):
        raise ValueError("script_class must be Script, LocalScript, ModuleScript or None")
    ts = _tokens(code)
    words = [token.value for token in ts]
    blocks = _blocks(words)
    found: list[Finding] = []

    def add(rule: str, index: int, message: str, fix: str, severity: str = "warning") -> None:
        found.append(Finding(rule, ts[index].line, message, fix, severity))

    for block in blocks:
        if block.kind == "while" and words[block.start + 1:block.start + 3] == ["true", "do"]:
            if not _yield_in_body(words, block.start + 3, block.end, blocks):
                add("loop-without-yield", block.start, "Infinite while loop has no direct yield.",
                    "Add task.wait() or an event:Wait() on every iteration.", "error")
        elif block.kind == "repeat" and words[block.end + 1:block.end + 2] == ["false"]:
            if not _yield_in_body(words, block.start + 1, block.end, blocks):
                add("loop-without-yield", block.start, "Repeat-until-false loop has no direct yield.",
                    "Yield with task.wait() or use a terminating condition.", "warning")

    aliases, inline = _runservice_receivers(code, ts, words)
    handlers = _touch_handlers(words, blocks)
    for i, event in enumerate(words):
        if event not in _RUN_EVENTS or words[i + 1:i + 4] != [":", "Connect", "("]:
            continue
        receiver: int | None = None
        if i >= 2 and words[i - 1] == "." and words[i - 2] in aliases:
            receiver = i - 2
        elif i >= 2 and words[i - 1] == "." and i - 2 in inline:
            receiver = inline[i - 2]
        if receiver is None:
            continue
        hazardous_scope = any(
            b.kind in ("while", "repeat", "for") and b.start < i < b.end for b in blocks
        ) or any(handler.start < i < handler.end for _, handler in handlers)
        if hazardous_scope and not _disconnected(words, _assigned_name(words, receiver)):
            add("runservice-connection-leak", i,
                "RunService connection inside a loop or touch callback has no visible Disconnect.",
                "Keep the RBXScriptConnection and call :Disconnect() when its work ends.", "review")

    for touched, handler in handlers:
        reward = _reward_at(words, handler.start + 1, handler.end)
        if reward is not None and not _guarded(words, handler.start + 1, reward):
            add("touched-reward-unguarded", touched,
                "Touched handler appears to grant a reward without a completed debounce.",
                "Check a per-player cooldown before awarding and set it before granting.", "review")

    if script_class == "Script":
        for i in _server_wait_chains(words):
            add("server-waitforchild-chain", i,
                "Server WaitForChild chain includes a call without a timeout.",
                "Pass a bounded timeout to each WaitForChild and handle nil.", "warning")

    for i, word in enumerate(words):
        if words[i:i + 4] == ["Instance", ".", "new", "("]:
            end = _close(words, i + 3)
            if end is not None and len(_top_level_args(words, i + 3, end)) > 1:
                add("instance-parent-argument", i, "Instance.new passes its parent as argument two.",
                    "Create the instance, configure it, then set .Parent.")
        if word in ("wait", "spawn", "delay") and words[i + 1:i + 2] == ["("]:
            if words[i - 1:i] not in (["."], [":"], ["function"]) and not _shadowed(words, blocks, i, word):
                add("deprecated-task-global", i, f"Deprecated global {word}().",
                    f"Use task.{word}().")

    return sorted(set(found), key=lambda f: (f.line, f.rule_id, f.message))
