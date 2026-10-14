"""Opt-in security diagnostics for inline Roblox Luau remote handlers.

Conservative token-based checks, not a parser or data-flow security audit.
No script execution, files, network access, GPU, or external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from star.luau_lint import Finding, _tokens


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$", re.ASCII)
_DATASTORE = frozenset(("GetAsync", "SetAsync", "UpdateAsync", "RemoveAsync", "IncrementAsync"))
_MUTATORS = frozenset(("Destroy", "PivotTo", "SetAttribute", "ClearAllChildren", "BreakJoints"))
_PROPERTIES = frozenset(("Parent", "Position", "CFrame", "Transparency", "Anchored", "CanCollide"))
_BALANCES = frozenset(("coins", "coin", "money", "cash", "wallet", "currency",
                       "gold", "credits", "points", "balance"))
_DATA_TABLES = frozenset(("inventory", "data", "profile", "owned", "entitlements"))


@dataclass(frozen=True)
class _Handler:
    event: int
    start: int
    end: int
    player: str
    parameters: tuple[str, ...]


def _closing(words: list[str], opening_at: int) -> int:
    depth = 0
    for index in range(opening_at, len(words)):
        if words[index] == "(":
            depth += 1
        elif words[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return len(words)


def _block_end(words: list[str], opening_at: int) -> int:
    """Find a function/if end, tolerating nested blocks and loop do."""
    stack: list[str] = []
    pending_do = 0
    for index in range(opening_at, len(words)):
        word = words[index]
        if word in ("function", "if", "repeat"):
            stack.append(word)
        elif word in ("while", "for"):
            stack.append("loop")
            pending_do += 1
        elif word == "do":
            if pending_do:
                pending_do -= 1
            else:
                stack.append("do")
        elif word == "until":
            if stack and stack[-1] == "repeat":
                stack.pop()
        elif word == "end" and stack:
            stack.pop()
            if not stack:
                return index
    return len(words)


def _handlers(words: list[str]) -> list[_Handler]:
    handlers = []
    for index, word in enumerate(words):
        if word == "OnServerEvent" and words[index + 1:index + 4] == [":", "Connect", "("]:
            fn = index + 4
        elif word == "OnServerInvoke" and words[index + 1:index + 3] == ["=", "function"]:
            fn = index + 2
        else:
            continue
        if words[fn:fn + 2] != ["function", "("]:
            continue
        close = _closing(words, fn + 1)
        end = _block_end(words, fn)
        if close >= end or end >= len(words):
            continue  # Named callbacks and malformed blocks are deliberately not guessed.
        args: list[str] = []
        field: list[str] = []
        nesting = 0
        for item in words[fn + 2:close] + [","]:
            if item == "," and not nesting:
                if field and _IDENT.fullmatch(field[0]):
                    args.append(field[0])
                field = []
            else:
                field.append(item)
                if item in ("(", "[", "{"):
                    nesting += 1
                elif item in (")", "]", "}"):
                    nesting -= 1
        if len(args) >= 2:
            handlers.append(_Handler(index, close + 1, end, args[0], tuple(args[1:])))
    return handlers


def _has(words: list[str], sequence: list[str]) -> bool:
    width = len(sequence)
    return any(words[i:i + width] == sequence for i in range(len(words) - width + 1))


def _contexts(words: list[str], start: int, sink: int) -> list[tuple[list[str], str]]:
    """Prior unconditional rejecting guards and branches actually enclosing a sink.

    A return inside a nested function/conditional does not exit the handler.
    Likewise a guard in a scope that ends before the sink cannot protect it.
    """
    scopes = [(i, _block_end(words, i)) for i in range(start, sink)
              if words[i] in ("function", "if", "while", "for", "do", "repeat")]
    result: list[tuple[list[str], str]] = []
    for index, end in scopes:
        if words[index] != "if" or end >= len(words):
            continue
        if any(opening < index < closing < sink for opening, closing in scopes):
            continue
        then = next((j for j in range(index + 1, end) if words[j] == "then"), end)
        if then == end:
            continue
        condition = words[index + 1:then]
        first_else = next((j for j in range(then + 1, end)
                           if words[j] in ("else", "elseif")), end)
        direct_return = any(
            words[j] == "return" and not any(
                then < opening < j < closing for opening, closing in scopes)
            for j in range(then + 1, first_else)
        )
        if end < sink and direct_return:
            result.append((condition, "reject"))
        elif then < sink < first_else:
            result.append((condition, "accept"))
    return result


def _type_guarded(contexts: list[tuple[list[str], str]], name: str) -> bool:
    for condition, branch in contexts:
        for index, word in enumerate(condition):
            if word not in ("type", "typeof"):
                continue
            if condition[index + 1:index + 4] != ["(", name, ")"]:
                continue
            op = condition[index + 4:index + 6]
            if (branch == "reject" and op == ["~", "="]) or (
                    branch == "accept" and op == ["=", "="]):
                return True
    return False


def _bounded(contexts: list[tuple[list[str], str]], name: str) -> bool:
    signs: set[str] = set()
    for condition, branch in contexts:
        # Rejecting an in-range AND is not a bounds check; nor is an
        # accepting OR. These compound forms can let bad values through.
        if (branch == "reject" and "and" in condition) or (
                branch == "accept" and "or" in condition):
            continue
        for index, word in enumerate(condition):
            if word != name:
                continue
            if index + 1 < len(condition) and condition[index + 1] in ("<", ">"):
                signs.add(condition[index + 1])
            if index and condition[index - 1] in ("<", ">"):
                signs.add(">" if condition[index - 1] == "<" else "<")
            if index >= 2 and condition[index - 1] == "=" and condition[index - 2] in ("<", ">"):
                signs.add(">" if condition[index - 2] == "<" else "<")
    return signs == {"<", ">"}


def _catalog(name: str) -> bool:
    return any(part in name.lower() for part in
               ("allow", "whitelist", "catalog", "product", "items", "prices", "valid"))


def _allowlisted(words: list[str], start: int, sink: int, name: str) -> bool:
    contexts = _contexts(words, start, sink)
    checked_aliases: set[str] = set()
    for i in range(start, sink - 6):
        if (words[i] == "local" and _IDENT.fullmatch(words[i + 1]) and
                words[i + 2] == "=" and _catalog(words[i + 3]) and
                words[i + 4:i + 7] == ["[", name, "]"]):
            checked_aliases.add(words[i + 1])
    for condition, branch in contexts:
        if not condition:
            continue
        negative = condition[0] == "not"
        if (branch == "reject") != negative:
            continue
        for i in range(len(condition) - 3):
            if (_catalog(condition[i]) and condition[i + 1:i + 4] == ["[", name, "]"]):
                return True
        if any(alias in condition for alias in checked_aliases):
            return True
    return False


def _owns_character(words: list[str], start: int, sink: int,
                    instance: str, player: str) -> bool:
    for condition, branch in _contexts(words, start, sink):
        descendant = [instance, ":", "IsDescendantOf", "(", player, ".", "Character", ")"]
        # The negation must apply to this exact ownership check. An
        # unrelated 'not' or an AND-gated rejection is not protection.
        if (branch == "reject" and condition == ["not", *descendant]) or (
                branch == "accept" and condition == descendant):
            return True
        for i in range(len(condition) - 7):
            if condition[i:i + 3] != [instance, ".", "Parent"]:
                continue
            op = condition[i + 3:i + 5]
            if condition[i + 5:i + 8] != [player, ".", "Character"]:
                continue
            if (branch == "reject" and op == ["~", "="]) or (
                    branch == "accept" and op == ["=", "="]):
                return True
    return False


def _money_sink(words: list[str], start: int, index: int) -> bool:
    # Bound context to the same statement to avoid treating a condition as a write.
    beginning = max(start, index - 20)
    for j in range(index - 1, beginning - 1, -1):
        if words[j] in ("then", "end", "return", "local", ";"):
            beginning = j + 1
            break
    prefix = words[beginning:index]
    for j, word in enumerate(prefix):
        if word != "=" or (j and prefix[j - 1] in ("<", ">", "~", "=")):
            continue
        if any(token.lower() in _BALANCES for token in prefix[:j]) and (
                j == len(prefix) - 1 or "+" in prefix[j:] or "-" in prefix[j:]):
            return True
    return False


def _instance_sink(words: list[str], index: int) -> bool:
    if words[index + 1:index + 2] == [":"] and words[index + 2:index + 3]:
        return words[index + 2] in _MUTATORS
    return (words[index + 1:index + 2] == ["."] and
            words[index + 2:index + 3] and words[index + 2] in _PROPERTIES and
            words[index + 3:index + 4] == ["="])


def _datastore_args(words: list[str], index: int) -> list[list[str]]:
    if (index < 1 or words[index - 1] != ":" or words[index] not in _DATASTORE or
            words[index + 1:index + 2] != ["("]):
        return []
    close = _closing(words, index + 1)
    if close >= len(words):
        return []
    fields: list[list[str]] = [[]]
    depth = 0
    for word in words[index + 2:close]:
        if word in ("(", "[", "{"):
            depth += 1
        elif word in (")", "]", "}"):
            depth -= 1
        if word == "," and depth == 0:
            fields.append([])
        else:
            fields[-1].append(word)
    return fields


def lint_server_trust(code: str) -> list[Finding]:
    """Find suspicious inline handlers without running the supplied Luau."""
    if not isinstance(code, str):
        raise TypeError("code must be str")
    tokens = _tokens(code)
    words = [token.value for token in tokens]
    findings: list[Finding] = []
    for handler in _handlers(words):
        aliases = {name: name for name in handler.parameters}
        clamped: set[str] = set()
        for index in range(handler.start, handler.end):
            word = words[index]
            if (word == "local" and index + 3 < handler.end and
                    _IDENT.fullmatch(words[index + 1]) and words[index + 2] == "="):
                alias = words[index + 1]
                rhs: list[str] = []
                j = index + 3
                while j < handler.end and tokens[j].line == tokens[index].line and (
                        words[j] not in (";", "then", "end", "return", "local")):
                    rhs.append(words[j])
                    j += 1
                original = next((aliases[item] for item in rhs if item in aliases), None)
                if original and (rhs == [original] or _has(rhs, [".", "."]) or
                                 any(item in rhs for item in ("tostring", "tonumber", "clamp"))):
                    aliases[alias] = original
                    if _has(rhs, ["math", ".", "clamp", "(", original]):
                        clamped.add(alias)

            fields = _datastore_args(words, index)
            if fields:
                key = next((aliases[item] for item in fields[0] if item in aliases), None)
                if key and not _allowlisted(words, handler.start, index, key):
                    findings.append(Finding(
                        "SEC-DATASTORE-CLIENT-KEY", tokens[index].line,
                        "DataStore key includes client-controlled input.",
                        "Use a per-player server-owned UserId key or a strict server allow-list.",
                        "warning"))
                if word == "IncrementAsync" and len(fields) > 1:
                    increment = next((aliases[item] for item in fields[1] if item in aliases), None)
                    guards = _contexts(words, handler.start, index)
                    if increment and not (_type_guarded(guards, increment) and
                                          _bounded(guards, increment)):
                        findings.append(Finding(
                            "SEC-CLIENT-AMOUNT", tokens[index].line,
                            "DataStore increment uses an unchecked client amount.",
                            "Check numeric type, finite range, and server-side entitlement.",
                            "warning"))

            if word not in aliases:
                continue
            original = aliases[word]
            guards = _contexts(words, handler.start, index)
            if _money_sink(words, handler.start, index):
                if "price" in original.lower() or "cost" in original.lower():
                    findings.append(Finding(
                        "SEC-CLIENT-PRICE", tokens[index].line,
                        "Currency operation uses a price supplied by the client.",
                        "Derive the price from a server-owned item catalogue.", "warning"))
                elif not (_type_guarded(guards, original) and (
                        _bounded(guards, original) or word in clamped)):
                    findings.append(Finding(
                        "SEC-CLIENT-AMOUNT", tokens[index].line,
                        "Currency change uses an unbounded or untyped client amount.",
                        "Check numeric type, finite range, and server-side entitlement.",
                        "warning"))

            if _instance_sink(words, index) and not _owns_character(
                    words, handler.start, index, word, handler.player):
                findings.append(Finding(
                    "SEC-INSTANCE-OWNERSHIP", tokens[index].line,
                    "Client-provided Instance is mutated without a visible character ownership guard.",
                    "Check typeof, expected class and ownership before mutation.",
                    "warning"))

            if (index >= 2 and words[index - 1] == "[" and
                    words[index + 1:index + 3] == ["]", "="] and
                    any(part in words[index - 2].lower() for part in _DATA_TABLES) and
                    not _allowlisted(words, handler.start, index, original)):
                findings.append(Finding(
                    "SEC-REMOTE-ALLOWLIST", tokens[index].line,
                    "Client key writes server data without a visible allow-list.",
                    "Validate the requested key against a server-owned allow-list.",
                    "warning"))
    return sorted(set(findings), key=lambda finding: (
        finding.line, finding.rule_id, finding.message))
