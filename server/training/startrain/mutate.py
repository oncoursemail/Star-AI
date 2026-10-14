"""Mechanical mutants of a Luau solution, for the test-sanity gate (G4).

A set of tests is only worth keeping if it can tell a correct solution from a deliberately broken one. The
mutants are small, local, syntactic changes (flip a comparison, off-by-one on a number, swap and/or, drop a
statement, ...) made outside comments and strings. Some mutants do not change behaviour; the gate therefore
asks for a high kill rate, not for a perfect one.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
import re


@dataclass
class Mutant:
    kind: str
    line: int
    code: str


def mask(code: str) -> str:
    """Same length as `code`; comments and string contents replaced by spaces (newlines kept)."""
    out = list(code)
    i, n = 0, len(code)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = code[i]
        if code.startswith("--", i):
            m = re.match(r"--\[(=*)\[", code[i:])
            if m:
                close = "]" + m.group(1) + "]"
                end = code.find(close, i + len(m.group(0)))
                end = n if end < 0 else end + len(close)
            else:
                end = code.find("\n", i)
                end = n if end < 0 else end
            blank(i, end)
            i = end
        elif c in "\"'`":
            j = i + 1
            while j < n and code[j] != c and code[j] != "\n":
                j += 2 if code[j] == "\\" else 1
            blank(i + 1, j)
            i = j + 1
        elif c == "[" and re.match(r"\[=*\[", code[i:]):
            m = re.match(r"\[(=*)\[", code[i:])
            close = "]" + m.group(1) + "]"
            end = code.find(close, i + len(m.group(0)))
            end = n if end < 0 else end + len(close)
            blank(i + len(m.group(0)), end - len(close))
            i = end
        else:
            i += 1
    return "".join(out)


_RULES: list[tuple[str, re.Pattern, object]] = [
    ("eq-flip", re.compile(r"(?<![=~<>])==(?!=)"), "~="),
    ("neq-flip", re.compile(r"~="), "=="),
    ("lt-le", re.compile(r"(?<=\s)<(?=\s)"), "<="),
    ("le-lt", re.compile(r"(?<=\s)<=(?=\s)"), "<"),
    ("gt-ge", re.compile(r"(?<=\s)>(?=\s)"), ">="),
    ("ge-gt", re.compile(r"(?<=\s)>=(?=\s)"), ">"),
    ("plus-minus", re.compile(r"(?<=\s)\+(?=\s)"), "-"),
    ("minus-plus", re.compile(r"(?<=\s)-(?=\s)"), "+"),
    ("mul-div", re.compile(r"(?<=\s)\*(?=\s)"), "/"),
    ("add-assign", re.compile(r"\+="), "-="),
    ("sub-assign", re.compile(r"-="), "+="),
    ("and-or", re.compile(r"(?<=\s)and(?=\s)"), "or"),
    ("or-and", re.compile(r"(?<=\s)or(?=\s)"), "and"),
    ("drop-not", re.compile(r"\bnot\s+"), ""),
    ("true-false", re.compile(r"\btrue\b"), "false"),
    ("false-true", re.compile(r"\bfalse\b"), "true"),
]
_INT = re.compile(r"(?<![\w.\"'])(\d+)(?![\w.])")
_CALL_STMT = re.compile(r"^[ \t]*[A-Za-z_][\w.]*(?::[A-Za-z_]\w*)?\(.*\)[ \t]*$")
_SKIP_START = re.compile(r"^\s*(if|elseif|while|for|repeat|until|return|local|function|end|else|do)\b")
_RETURN = re.compile(r"^([ \t]+)return\b[ \t]+[^\n]+$", re.M)
_ASSIGN = re.compile(r"^[ \t]+(?!local\b)[A-Za-z_][\w.\[\]\"']*[ \t]*(?:\+=|-=|=)[ \t]*[^=\n][^\n]*$", re.M)


def _line_of(code: str, pos: int) -> int:
    return code.count("\n", 0, pos) + 1


def candidates(code: str) -> list[Mutant]:
    masked = mask(code)
    found: list[Mutant] = []
    for kind, pattern, replacement in _RULES:
        for m in pattern.finditer(masked):
            found.append(Mutant(kind, _line_of(code, m.start()),
                                code[:m.start()] + replacement + code[m.end():]))
    for m in _INT.finditer(masked):
        value = int(m.group(1))
        for kind, new in (("int-plus1", value + 1), ("int-zero-one", 1 if value == 0 else 0 if value == 1 else value - 1)):
            if str(new) != m.group(1):
                found.append(Mutant(kind, _line_of(code, m.start()), code[:m.start()] + str(new) + code[m.end():]))
    for m in _RETURN.finditer(masked):
        found.append(Mutant("return-nil", _line_of(code, m.start()),
                            code[:m.start()] + m.group(1) + "return nil" + code[m.end():]))
    for m in re.finditer(r"^.*$", masked, re.M):
        line = masked[m.start():m.end()]
        if _CALL_STMT.match(line) and not _SKIP_START.match(line):
            found.append(Mutant("drop-call", _line_of(code, m.start()), code[:m.start()] + code[m.end():]))
    for m in _ASSIGN.finditer(masked):
        found.append(Mutant("drop-assign", _line_of(code, m.start()), code[:m.start()] + code[m.end():]))
    return [f for f in found if f.code != code]


def select(code: str, seed: int, limit: int = 40) -> list[Mutant]:
    """Mutants in a seeded random order, at most `limit`, spread over the kinds (round robin)."""
    rng = random.Random(seed)
    by_kind: dict[str, list[Mutant]] = {}
    for mutant in candidates(code):
        by_kind.setdefault(mutant.kind, []).append(mutant)
    for group in by_kind.values():
        rng.shuffle(group)
    kinds = sorted(by_kind)
    rng.shuffle(kinds)
    out: list[Mutant] = []
    while kinds and len(out) < limit:
        for kind in list(kinds):
            group = by_kind[kind]
            if group:
                out.append(group.pop())
                if len(out) >= limit:
                    break
            else:
                kinds.remove(kind)
    return out
