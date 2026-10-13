"""Offline, deterministic pattern diagnostics for generated Roblox Luau.

Not a parser or data-flow analyzer. Aliases, shadowing and complex branches may
escape these conservative heuristics. No network access or code execution.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _tokens(code: str) -> list[_Token]:
    """Skip -- comments, long comments/strings with equals levels, and escaped quotes."""
    out: list[_Token] = []
    i, line, size = 0, 1, len(code)
    while i < size:
        start = i
        if code.startswith("--", i):
            i += 2
            match = re.match(r"\[(=*)\[", code[i:])
            if match:
                close = "]" + match.group(1) + "]"
                i += len(match.group())
                stop = code.find(close, i)
                i = size if stop < 0 else stop + len(close)
            else:
                stop = code.find("\n", i)
                i = size if stop < 0 else stop
        elif code[i] in ("'", '"'):
            quote = code[i]
            i += 1
            while i < size:
                if code[i] == "\\":
                    i += 2
                elif code[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
        elif code[i] == "[" and (match := re.match(r"\[(=*)\[", code[i:])):
            close = "]" + match.group(1) + "]"
            i += len(match.group())
            stop = code.find(close, i)
            i = size if stop < 0 else stop + len(close)
        elif code[i].isspace():
            i += 1
        else:
            match = _WORD.match(code, i)
            assert match is not None
            out.append(_Token(match.group(), line, i))
            i = match.end()
        line += code[start:i].count("\n")
    return out


def lint(code: str, *, external: bool | None = None, safety_checks: bool = False,
         script_class: str | None = None, server_security: bool = False) -> list[Finding]:
    """Return sorted static findings; the CLI second opinion, lifetime and server-trust checks are OFF by default."""
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

    def block_end(start: int) -> int:
        """Approximate blocks; do paired with while/for is not another block."""
        depth = 1
        for j in range(start + 1, len(v)):
            word = v[j]
            if word in ("function", "if", "for", "while", "do", "repeat"):
                if word == "do" and any(w in v[max(start, j - 12):j] for w in ("for", "while")):
                    continue
                depth += 1
            elif word in ("end", "until"):
                depth -= 1
                if not depth:
                    return j
        return len(v)

    functions = [(j, block_end(j)) for j, w in enumerate(v) if w == "function"]
    protected = [(j, end_of(j + 1)) for j in range(len(v) - 1)
                 if v[j] in ("pcall", "xpcall") and v[j + 1] == "("]

    for i, word in enumerate(v):
        prev = v[i - 1] if i else ""
        if word in ("wait", "spawn", "delay") and v[i + 1:i + 2] == ["("] and prev not in (".", ":", "function", "local"):
            if not any(v[k:k + 2] == ["local", word] or
                       v[k:k + 3] == ["local", "function", word] for k in range(i)):
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
        server_access = any(v[j:j + 2] == ["GetService", "("] and
            re.match(r"""\s*['"]""" + service + r"""['"]""", code[ts[j + 1].offset + 1:])
            for j in range(len(v) - 1) for service in _SERVER)
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
    if external is None:
        from .luau_analyze import enabled
        external = enabled()
    if external:
        from .luau_analyze import analyze
        findings.extend(analyze(code))
    return sorted(set(findings), key=lambda f: (f.line, f.rule_id, f.message))
