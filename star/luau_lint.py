"""Offline, deterministic pattern diagnostics for generated Roblox Luau.

Not a parser or data-flow analyzer. Aliases, shadowing and complex branches may
escape these conservative heuristics. No network access or code execution.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
import re


@dataclass(frozen=True)
class Finding:
    rule_id: str
    line: int
    message: str
    suggested_fix: str
    severity: str


@dataclass(frozen=True)
class _Token:
    value: str
    line: int
    offset: int


_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]", re.ASCII)
_SERVICES = frozenset(("Players", "ReplicatedStorage", "ServerStorage", "ServerScriptService",
    "DataStoreService", "RunService", "TweenService", "UserInputService", "MarketplaceService",
    "Lighting", "Workspace", "CollectionService", "MessagingService", "TeleportService",
    "HttpService", "SoundService", "ContextActionService", "Teams", "StarterGui", "StarterPlayer"))
_SERVER = frozenset(("ServerStorage", "ServerScriptService", "DataStoreService"))
_ASYNC = frozenset(("GetAsync", "SetAsync", "UpdateAsync", "RemoveAsync"))
# game:GetService("ServerStorage") and the like, matched right after the opening parenthesis.
_SERVER_LITERALS = tuple(re.compile(r"""\s*['"]""" + service + r"""['"]""") for service in sorted(_SERVER))


# One pass of a single precompiled pattern over the script. The alternatives are tried in the
# order the original character loop tested them: `--` comments (long, then to the end of the
# line, leaving the newline), quoted strings (a backslash skips the next character, even a
# newline; an unclosed string runs to the end), long strings with equals levels (an unclosed one
# runs to the end), whitespace (str.isspace, as \s is for str patterns), then one token, where
# \s and \d keep the ASCII meaning they had in _WORD.
_SCAN = re.compile(r"""
    (?P<skip>
        --\[(?P<comment_level>=*)\[[\s\S]*?(?:\](?P=comment_level)\]|\Z)
      | --[^\n]*
      | "(?:[^\\"]|\\[\s\S]?)*"?
      | '(?:[^\\']|\\[\s\S]?)*'?
      | \[(?P<string_level>=*)\[[\s\S]*?(?:\](?P=string_level)\]|\Z)
      | \s+
    )
  | (?P<word>(?a:[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]))
""", re.VERBOSE)


def _tokens(code: str) -> list[_Token]:
    """Skip -- comments, long comments/strings with equals levels, and escaped quotes.

    `lint`, `luau_safety` and `luau_server_security` each tokenize the same script, so the
    result is cached per code text; every caller gets its own list.
    """
    return list(_token_tuple(code))


@lru_cache(maxsize=16)
def _token_tuple(code: str) -> tuple[_Token, ...]:
    out: list[_Token] = []
    line = 1
    count = code.count
    for match in _SCAN.finditer(code):
        if match.lastgroup == "word":
            start = match.start()
            out.append(_Token(match.group(), line, start))
        else:
            line += count("\n", match.start(), match.end())
    return tuple(out)


_BLOCK_OPENERS = frozenset(("function", "if", "for", "while", "do", "repeat"))
_BLOCK_CLOSERS = frozenset(("end", "until"))
_DO_WINDOW = 12   # a `do` within this many words after `for`/`while` belongs to that loop


def _block_end_finder(v: list[str]):
    """`block_end(start)` for `lint`: the index of the `end`/`until` closing the block opened at `start`.

    The rule is a forward scan from `start` with a depth counter, where a `do` is not another
    block when `for` or `while` appears among the previous _DO_WINDOW words, looking no further
    back than `start` itself. Only the first _DO_WINDOW words after `start` can see `start` in
    that window, so they are scanned directly; from there on every word's effect on the depth
    is the same for every start, and the closing word is found in a precomputed index of where
    each running depth level is reached by a closing word. Each call is then O(log n) instead of
    a scan to the end of the script (which an unclosed `for ... do` used to cause for every
    later block, making large scripts quadratic). Results are identical to the scan.
    """
    size = len(v)

    def opens(j: int, lower: int) -> bool:
        if v[j] != "do":
            return True
        window = v[max(lower, j - _DO_WINDOW):j]
        return "for" not in window and "while" not in window

    levels: list[int] = []                 # running depth after each word, with no lower bound
    closed_at: dict[int, list[int]] = {}   # depth reached -> closing word indexes, ascending
    level = 0
    for j, word in enumerate(v):
        if word in _BLOCK_OPENERS:
            if opens(j, 0):
                level += 1
        elif word in _BLOCK_CLOSERS:
            level -= 1
            closed_at.setdefault(level, []).append(j)
        levels.append(level)

    def block_end(start: int) -> int:
        depth = 1
        stop = min(size, start + _DO_WINDOW + 1)
        for j in range(start + 1, stop):
            word = v[j]
            if word in _BLOCK_OPENERS:
                if opens(j, start):
                    depth += 1
            elif word in _BLOCK_CLOSERS:
                depth -= 1
                if not depth:
                    return j
        if stop >= size:
            return size
        # Depth reaches 0 at the first later closing word that brings the running level to
        # this value (the level moves by one per word, so it cannot skip past it).
        candidates = closed_at.get(levels[stop - 1] - depth)
        if candidates:
            found = bisect_left(candidates, stop)
            if found < len(candidates):
                return candidates[found]
        return size

    return block_end


def lint(code: str, *, external: bool | None = None, safety_checks: bool = False,
         script_class: str | None = None, server_security: bool = False,
         roblox_rules: bool = False) -> list[Finding]:
    """Return sorted static findings; the CLI second opinion, lifetime, server-trust and Roblox API
    rules (star.luau_roblox_rules) are OFF by default."""
    if not isinstance(code, str):
        raise TypeError("code must be str")
    ts = _tokens(code)
    v = [t.value for t in ts]
    findings: list[Finding] = []

    def add(rule: str, i: int, message: str, fix: str, severity: str = "warning") -> None:
        findings.append(Finding(rule, ts[i].line, message, fix, severity))

    def end_of(start: int, opening: str = "(", closing: str = ")") -> int:
        depth = 0
        for j in range(start, len(v)):
            if v[j] == opening:
                depth += 1
            elif v[j] == closing:
                depth -= 1
                if depth == 0:
                    return j
        return len(v)

    def args(start: int) -> list[list[str]]:
        end = end_of(start)
        result: list[list[str]] = [[]]
        depth = 0
        for word in v[start + 1:end]:
            if word in ("(", "{", "["):
                depth += 1
            elif word in (")", "}", "]"):
                depth -= 1
            if word == "," and depth == 0:
                result.append([])
            else:
                result[-1].append(word)
        return [] if result == [[]] else result

    block_end = _block_end_finder(v)

    functions = [(j, block_end(j)) for j, w in enumerate(v) if w == "function"]
    protected = [(j, end_of(j + 1)) for j in range(len(v) - 1)
                 if v[j] in ("pcall", "xpcall") and v[j + 1] == "("]

    # Where `local wait` (or spawn/delay) first appears: a later bare call is the local, not the global.
    first_local: dict[str, int] = {}
    for k in range(len(v) - 1):
        if v[k] == "local" and v[k + 1] in ("wait", "spawn", "delay"):
            first_local.setdefault(v[k + 1], k)

    for i, word in enumerate(v):
        prev = v[i - 1] if i else ""
        if word in ("wait", "spawn", "delay") and v[i + 1:i + 2] == ["("] and prev not in (".", ":", "function", "local"):
            if not first_local.get(word, i) < i:
                add("deprecated-task-global", i, f"Deprecated global {word}().", f"Use task.{word}().")
        if v[i:i + 4] == ["Instance", ".", "new", "("] and len(args(i + 3)) >= 2:
            add("instance-parent-argument", i, "Instance.new passes its parent as argument two.",
                "Create the instance, set properties, then assign .Parent.")
        if v[i:i + 2] == ["game", "."] and i + 2 < len(v) and v[i + 2] in _SERVICES:
            service = v[i + 2]
            add("service-property", i, f"Service game.{service} accessed as a property.",
                f'Use game:GetService("{service}").')
        if word == "LoadAnimation" and prev == ":" and i >= 2 and v[i - 2].lower() == "humanoid":
            add("humanoid-load-animation", i, "Humanoid:LoadAnimation is deprecated.",
                "Use Animator:LoadAnimation() with an Animator under the Humanoid.")
        if word in _ASYNC and prev == ":" and v[i + 1:i + 2] == ["("]:
            if not any(a < i < b for a, b in protected):
                add("datastore-unprotected", i, f"{word} can throw outside pcall/xpcall.",
                    "Wrap the DataStore call in pcall or xpcall.", "error")
        if word in ("FindFirstChild", "FindFirstChildOfClass") and prev == ":" and v[i + 1:i + 2] == ["("]:
            end = end_of(i + 1)
            if end + 1 < len(v) and v[end + 1] in (".", ":", "["):
                add("unchecked-find-child", i, "FindFirstChild result indexed without a nil check.",
                    "Store the child and check it is non-nil before indexing.")

    # Yield recognition is deliberately syntactic; it is not a guarantee of progress.
    def yields(body: list[str]) -> bool:
        return any(w in ("wait", "WaitForChild") and body[j + 1:j + 2] == ["("] or
                   w == "Wait" and j > 0 and body[j - 1] == ":"
                   for j, w in enumerate(body))

    loops = [(i, block_end(i)) for i, w in enumerate(v) if w in ("while", "repeat", "for")]
    for i, word in enumerate(v):
        if word == "while" and v[i + 1:i + 3] == ["true", "do"]:
            end = block_end(i)
            if end < len(v) and not yields(v[i + 3:end]):
                add("loop-without-yield", i, "Infinite while loop has no visible yield.",
                    "Yield with task.wait() or an event Wait().", "error")
        elif word == "repeat":
            end = block_end(i)
            # A finite repeat/until loop needs no yield; diagnose only the
            # syntactically infinite form where the condition is literally false.
            if end < len(v) and v[end + 1:end + 2] == ["false"] and not yields(v[i + 1:end]):
                add("loop-without-yield", i, "Repeat loop has no visible yield.",
                    "Yield or ensure the loop cannot spin.", "warning")
        if word == "Connect" and i and v[i - 1] in (".", ":") and v[i + 1:i + 2] == ["("]:
            containing = [(a, b) for a, b in loops if a < i < b]
            if containing:
                a, b = containing[-1]
                if "=" not in v[a:i] and "Disconnect" not in v[i:b]:
                    add("loop-connection", i, "Connection in a loop has no visible owner or disconnection.",
                        "Store the connection and disconnect it.", "review")

    server_access = any(w in v for w in _SERVER)
    if not server_access:
        server_access = any(v[j + 1] == "(" and literal.match(code, ts[j + 1].offset + 1)
                            for j in range(len(v) - 1) if v[j] == "GetService" for literal in _SERVER_LITERALS)
    if server_access and "LocalPlayer" in v:
        i = v.index("LocalPlayer")
        add("mixed-client-server", i, "LocalPlayer and server-only services appear together.",
            "Split client and server responsibilities.")

    # Limited same-function pattern, not cross-function or alias tracking.
    for a, b in functions or [(0, len(v))]:
        segment = v[a:b]
        if "GetAsync" in segment and "SetAsync" in segment and segment.index("GetAsync") < segment.index("SetAsync"):
            add("datastore-read-set", a + segment.index("SetAsync"),
                "GetAsync followed by SetAsync may race.", "Use UpdateAsync for atomic updates.")

    for i, word in enumerate(v):
        if word == "Touched" and "Connect" in v[i + 1:i + 10]:
            fn = next((j for j in range(i + 1, len(v)) if v[j] == "function"), -1)
            if fn >= 0:
                body = [w.lower() for w in v[fn:block_end(fn)]]
                if not any(w in body for w in ("debounce", "cooldown", "busy", "active", "canhit", "hitonce")):
                    add("touched-debounce", i, "Touched handler lacks an obvious state guard.",
                        "Add a debounce or per-object cooldown.", "review")
        if word in ("OnServerEvent", "OnServerInvoke"):
            fn = next((j for j in range(i + 1, min(i + 18, len(v))) if v[j] == "function"), -1)
            if fn < 0:
                continue
            par = next((j for j in range(fn + 1, min(fn + 4, len(v))) if v[j] == "("), -1)
            if par < 0:
                continue
            names = [a[0] for a in args(par) if len(a) == 1]
            body = v[end_of(par) + 1:block_end(fn)]
            for name in names[1:]:
                if name in body and any(w in body for w in ("+", "-", "*", "/", "amount", "Amount", "target", "Target")):
                    if not any(w in body[:body.index(name)] for w in ("typeof", "type", "clamp")):
                        add("remote-unvalidated", i, "Client argument used without visible prior validation.",
                            "Check type, allowed targets and server-side range first.", "review")
                        break
    if safety_checks:
        # Import lazily: the optional module reuses this linter's lexer and Finding.
        from .luau_safety import inspect_safety

        extra = inspect_safety(code, script_class=script_class)
        # The opt-in implementations replace these legacy heuristics wholesale,
        # so their old false positives cannot survive alongside the new results.
        replaced_rules = {"loop-without-yield", "instance-parent-argument",
                          "deprecated-task-global"}
        findings = [finding for finding in findings
                    if finding.rule_id not in replaced_rules]
        findings.extend(extra)
    if server_security:
        # Opt in explicitly; default lint behavior remains unchanged.
        from star.luau_server_security import lint_server_trust
        findings.extend(lint_server_trust(code))
    if roblox_rules:
        # Opt in explicitly; deprecated engine APIs and client/server mistakes.
        from .luau_roblox_rules import lint_roblox_rules
        findings.extend(lint_roblox_rules(code, script_class=script_class))
    if external is None:
        from .luau_analyze import enabled
        external = enabled()
    if external:
        from .luau_analyze import analyze
        findings.extend(analyze(code))
    return sorted(set(findings), key=lambda f: (f.line, f.rule_id, f.message))
