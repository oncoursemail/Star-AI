"""Conservative, offline Roblox API-name checks against a supplied Studio dump.

This is not a Luau parser or a type checker. Only simple direct assignments
from Instance.new or game:GetService establish a variable's class.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class ApiClass:
    superclass: str
    members: frozenset[str]
    service: bool


@dataclass(frozen=True)
class ApiDump:
    classes: dict[str, ApiClass]
    inherited_members: dict[str, frozenset[str]]
    services: frozenset[str]


@dataclass(frozen=True)
class ApiFinding:
    rule_id: str
    line: int
    class_name: str | None
    name: str
    suggestion: str | None

    @property
    def severity(self) -> str:
        """Normalized advisory severity; API spelling guesses are not engine proof."""
        return "warning"

    @property
    def message(self) -> str:
        """A bounded statement without echoing untrusted names."""
        if self.rule_id == "unknown-class":
            return "Unknown Roblox class in Instance.new; check against the local API dump."
        if self.rule_id == "unknown-service":
            return "Unknown service in GetService; check against the local API dump."
        return "Possible unknown class member; verify its receiver and the local API dump."

    @property
    def suggested_fix(self) -> str:
        """A repair action, not an unverified automatic rename."""
        if self.rule_id == "unknown-class":
            return "Use a class listed in the validated local Roblox API dump."
        if self.rule_id == "unknown-service":
            return "Use a service listed in the validated local Roblox API dump."
        return "Confirm the inferred class and choose a documented member from the local API dump."


@dataclass(frozen=True)
class _Token:
    value: str
    line: int
    kind: str


_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[^\s]", re.ASCII)
_LONG_OPEN = re.compile(r"\[(=*)\[")


def load_api_dump(path: str | Path) -> ApiDump:
    """Load Roblox Studio's --fullApi (v1) JSON; reject incomplete schemas."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid Roblox Full API dump JSON") from exc

    if not isinstance(data, dict) or not isinstance(data.get("Classes"), list) or not data["Classes"]:
        raise ValueError("Roblox Full API dump requires a non-empty Classes list")

    classes: dict[str, ApiClass] = {}
    for entry in data["Classes"]:
        if not isinstance(entry, dict):
            raise ValueError("Malformed class in Roblox API dump")
        name, parent, members, tags = (
            entry.get("Name"), entry.get("Superclass"), entry.get("Members"), entry.get("Tags", [])
        )
        if (not isinstance(name, str) or not name or name in classes
                or not isinstance(parent, str) or not isinstance(members, list)
                or not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags)):
            raise ValueError("Malformed or duplicate class in Roblox API dump")
        names: set[str] = set()
        for member in members:
            if not isinstance(member, dict) or not isinstance(member.get("Name"), str) or not member["Name"]:
                raise ValueError(f"Malformed member in Roblox API class {name}")
            names.add(member["Name"])
        classes[name] = ApiClass(parent, frozenset(names), "Service" in tags)

    inherited: dict[str, frozenset[str]] = {}
    for name in classes:
        names = set()
        seen: set[str] = set()
        current = name
        while current in classes:
            if current in seen:
                raise ValueError(f"Superclass cycle in Roblox API class {name}")
            seen.add(current)
            info = classes[current]
            names.update(info.members)
            current = info.superclass
        if current not in ("", "<<<ROOT>>>"):
            raise ValueError(f"Unknown superclass {current} in Roblox API class {name}")
        inherited[name] = frozenset(names)

    return ApiDump(classes, inherited, frozenset(
        name for name, info in classes.items() if info.service
    ))


def _tokens(source: str) -> list[_Token]:
    """Retain only plain string literals; ignore code inside comments and strings."""
    result: list[_Token] = []
    i, line, size = 0, 1, len(source)
    while i < size:
        start, start_line = i, line
        if source.startswith("--", i):
            i += 2
            long_open = _LONG_OPEN.match(source, i)
            if long_open:
                i = long_open.end()
                closing = "]" + long_open.group(1) + "]"
                end = source.find(closing, i)
                i = size if end < 0 else end + len(closing)
            else:
                end = source.find("\n", i)
                i = size if end < 0 else end
        elif source[i] in ("'", '"'):
            quote = source[i]
            i += 1
            content_start = i
            escaped = False
            closed = False
            while i < size:
                if source[i] == "\\":
                    escaped = True
                    i = min(i + 2, size)
                elif source[i] == quote:
                    closed = True
                    break
                else:
                    i += 1
            content = source[content_start:i] if closed and not escaped else ""
            if closed:
                i += 1
            result.append(_Token(content, start_line, "string" if closed and not escaped else "opaque"))
        elif source[i] == "[" and (long_open := _LONG_OPEN.match(source, i)):
            i = long_open.end()
            closing = "]" + long_open.group(1) + "]"
            end = source.find(closing, i)
            i = size if end < 0 else end + len(closing)
            result.append(_Token("", start_line, "opaque"))
        elif source[i] == chr(96):  # Luau interpolated/backtick strings.
            i += 1
            while i < size:
                if source[i] == "\\":
                    i = min(i + 2, size)
                elif source[i] == chr(96):
                    i += 1
                    break
                else:
                    i += 1
            result.append(_Token("", start_line, "opaque"))
        elif source[i].isspace():
            i += 1
        else:
            match = _WORD.match(source, i)
            assert match is not None
            word = match.group()
            result.append(_Token(word, start_line, "word" if word[0].isascii() and (
                word[0].isalpha() or word[0] == "_") else "punct"))
            i = match.end()
        line += source[start:i].count("\n")
    return result


def _nearest(name: str, candidates: frozenset[str] | dict[str, ApiClass]) -> str | None:
    matches = get_close_matches(name, sorted(candidates), n=1, cutoff=0)
    return matches[0] if matches else None


def _creation_at(tokens: list[_Token], values: list[str], index: int,
                 dump: ApiDump) -> tuple[str | None, ApiFinding | None] | None:
    if index + 5 >= len(tokens) or (index and values[index - 1] in (".", ":")):
        return None
    if values[index:index + 4] == ["Instance", ".", "new", "("]:
        allowed, rule = dump.classes, "unknown-class"
    elif values[index:index + 4] == ["game", ":", "GetService", "("]:
        allowed, rule = dump.services, "unknown-service"
    else:
        return None

    argument = tokens[index + 4]
    if argument.kind != "string" or values[index + 5] not in (")", ","):
        return None
    if argument.value in allowed:
        return argument.value, None
    finding = ApiFinding(rule, argument.line, None, argument.value,
                         _nearest(argument.value, allowed))
    return None, finding


def check_luau_api(source: str, dump: ApiDump) -> list[ApiFinding]:
    """Report definite spelling misses on known Roblox classes, without executing code.

    Unknown receiver types, dynamic constructor arguments, property reads, and
    chained expressions are intentionally not diagnosed.
    """
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if not isinstance(dump, ApiDump):
        raise TypeError("dump must be an ApiDump loaded by load_api_dump")

    tokens = _tokens(source)
    values = [token.value for token in tokens]
    known: dict[str, str] = {}
    findings: list[ApiFinding] = []
    for i, token in enumerate(tokens):
        # Shadowed locals or function parameters do not retain an inferred class.
        # We do not restore outer bindings: missing a hit is safer than a false one.
        if token.kind == "word" and token.value == "local" and i + 1 < len(tokens):
            known.pop(values[i + 1], None)
        if token.kind == "word" and token.value == "function":
            opening = next((j for j in range(i + 1, min(i + 7, len(tokens)))
                            if values[j] == "("), None)
            if opening is not None:
                expect_name = True
                for j in range(opening + 1, len(tokens)):
                    if values[j] == ")":
                        break
                    if values[j] == ",":
                        expect_name = True
                    elif expect_name and tokens[j].kind == "word":
                        known.pop(values[j], None)
                        expect_name = False

        # An ordinary reassignment kills the last simple inferred type.
        if (token.kind == "word" and values[i + 1:i + 2] == ["="]
                and values[i + 2:i + 3] != ["="]
                and (i == 0 or values[i - 1] not in (".", ":"))):
            known.pop(token.value, None)

        creation = _creation_at(tokens, values, i, dump)
        if creation is not None:
            class_name, finding = creation
            if finding is not None:
                findings.append(finding)
            # Only a simple variable = constructor establishes a type.
            if (i >= 2 and values[i - 1] == "=" and tokens[i - 2].kind == "word"
                    and (i < 3 or values[i - 3] not in (".", ":"))):
                if class_name is not None:
                    known[tokens[i - 2].value] = class_name
                else:
                    known.pop(tokens[i - 2].value, None)

        if (token.kind != "word" or token.value not in known or i + 3 >= len(tokens)
                or (i and values[i - 1] in (".", ":"))
                or values[i + 1] not in (".", ":")
                or tokens[i + 2].kind != "word"):
            continue
        member = tokens[i + 2]
        operation = values[i + 3]
        is_method = operation == "("
        is_assignment = (values[i + 1] == "." and (
            (operation == "=" and values[i + 4:i + 5] != ["="])
            or (operation in ("+", "-", "*", "/", "%", "^", "..")
                and values[i + 4:i + 5] == ["="])
        ))
        if not (is_method or is_assignment):
            continue
        class_name = known[token.value]
        members = dump.inherited_members[class_name]
        if member.value not in members:
            findings.append(ApiFinding(
                "unknown-member", member.line, class_name, member.value,
                _nearest(member.value, members),
            ))
    return sorted(set(findings), key=lambda item: (
        item.line, item.rule_id, item.class_name or "", item.name
    ))
