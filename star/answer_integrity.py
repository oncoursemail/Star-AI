"""Advisory, pure detection of incomplete model answers and ignored self-checks.

This module is NOT wired into STAR's output path. Findings are reasons to
retest or request repair, not a Luau parse result or proof of Studio behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .code_answer_completion import open_fence
from .eval_checks import split_answer, strip_luau


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    reason: str
    repair_instruction: str


@dataclass(frozen=True)
class IntegrityVerdict:
    issues: tuple[IntegrityIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def reason(self) -> str:
        return "; ".join(item.reason for item in self.issues)

    @property
    def repair_instruction(self) -> str:
        return " ".join(item.repair_instruction for item in self.issues)


_FENCE = re.compile(r"^[ \t]*(?P<run>\x60{3,}|~{3,})(?P<info>[^\r\n]*)$")
_WORDS = re.compile(r"\b[A-Za-z_]\w*\b")
_TRAILING = re.compile(
    r"\b(?:and|or|but|because|although|if|when|then|so|to|for|with|"
    r"the|an|a|is|are|was|were|will|that|which)\s*$|[,;]\s*$|[-–]\s*$", re.I
)
_ERROR = re.compile(r"\b(?:errors?|fail(?:ed|ure|ures)?|assertion|diagnostic|issues?)\b", re.I)
_RESOLVED = re.compile(
    r"\b(?:no|zero|0)\s+(?:errors?|failures?|issues?)\b|"
    r"\b(?:passed|resolved|repaired|fixed|success)\b|error-free", re.I
)


def _luau_segments(answer: str) -> tuple[str, ...]:
    """Extract closed and still-open Luau fences; never parse ordinary prose."""
    blocks: list[str] = []
    lines: list[str] = []
    active: tuple[str, int, str] | None = None
    for line in answer.splitlines():
        marker = _FENCE.fullmatch(line)
        if active is None:
            if marker:
                run = marker.group("run")
                lang = marker.group("info").strip().lower().split(" ", 1)[0]
                active = (run[0], len(run), lang)
                lines = []
            continue
        if (marker and marker.group("run")[0] == active[0] and
                len(marker.group("run")) >= active[1] and not marker.group("info").strip()):
            chunk = "\n".join(lines)
            if active[2] in {"luau", "lua"} or (not active[2] and
                    re.search(r"\b(?:local|function|end|return)\b", chunk)):
                blocks.append(chunk)
            active = None
        else:
            lines.append(line)
    if active is not None:
        chunk = "\n".join(lines)
        if active[2] in {"luau", "lua"} or (not active[2] and
                re.search(r"\b(?:local|function|end|return)\b", chunk)):
            blocks.append(chunk)
    return tuple(blocks)


def _unclosed_blocks(code: str) -> tuple[str, ...]:
    """Conservative keyword stack; skip quoted strings and all Lua comment forms.

    for/while consume their own do; repeat consumes until. This does not parse
    Luau's full grammar (especially type expressions or backtick interpolation).
    """
    tokens = _WORDS.findall(strip_luau(code, strings=True))
    stack: list[tuple[str, bool]] = []  # (construct, pending 'do')
    for token in tokens:
        if token in {"function", "if", "for", "while", "repeat"}:
            stack.append((token, token in {"for", "while"}))
        elif token == "do":
            if stack and stack[-1][1]:
                stack[-1] = (stack[-1][0], False)
            else:
                stack.append(("do", False))
        elif token == "end":
            if stack and stack[-1][0] != "repeat":
                stack.pop()
        elif token == "until":
            if stack and stack[-1][0] == "repeat":
                stack.pop()
    return tuple(kind for kind, _ in stack)


def _code_fingerprint(text: str) -> str:
    blocks = _luau_segments(text)
    code = "\n".join(blocks) if blocks else text
    # Whitespace in Lua strings still matters, so remove only line-edge changes.
    return "\n".join(line.rstrip() for line in strip_luau(code).splitlines() if line.strip())


def _has_reported_errors(self_check: str) -> bool:
    return any(_ERROR.search(line) and not _RESOLVED.search(line)
               for line in self_check.splitlines())


def inspect_answer(answer: str, *, self_check: str = "",
                   previous_code: str | None = None) -> IntegrityVerdict:
    """Return structured findings without modifying code or calling a model.

    Self-check findings need both an explicit error report and a comparable
    pre-check code snapshot; without that snapshot the verdict is UNKNOWN.
    """
    if not isinstance(answer, str) or not isinstance(self_check, str):
        raise TypeError("answer and self_check must be strings")
    if previous_code is not None and not isinstance(previous_code, str):
        raise TypeError("previous_code must be text or None")
    body, _ = split_answer(answer)
    issues: list[IntegrityIssue] = []
    if open_fence(body) is not None:
        issues.append(IntegrityIssue(
            "unclosed_fence", "Unbalanced Markdown code fence",
            "Complete the remaining fenced code and close the Markdown fence before submitting."
        ))
    chunks = _luau_segments(body)
    for number, chunk in enumerate(chunks, 1):
        waiting = _unclosed_blocks(chunk)
        if waiting:
            issues.append(IntegrityIssue(
                "unclosed_luau_block",
                f"Luau block {number} has unmatched constructs: {', '.join(waiting)}",
                "Close the remaining Luau blocks with their matching end or until, then compile again."
            ))
    tail = body.rstrip().splitlines()
    last = tail[-1].strip() if tail else ""
    if (last and len(last.split()) >= 3 and not _FENCE.fullmatch(last) and
            not last.startswith("#") and _TRAILING.search(last)):
        issues.append(IntegrityIssue(
            "trailing_fragment", "Answer ends in a likely unfinished sentence",
            "Finish the dangling sentence without adding claims that have not been checked."
        ))
    if (previous_code is not None and _has_reported_errors(self_check) and
            _code_fingerprint(answer) == _code_fingerprint(previous_code)):
        issues.append(IntegrityIssue(
            "unrepaired_selfcheck", "Self-check reported errors but the final code was unchanged",
            "Repair the reported errors in the code and rerun the self-check before sending it."
        ))
    return IntegrityVerdict(tuple(issues))
