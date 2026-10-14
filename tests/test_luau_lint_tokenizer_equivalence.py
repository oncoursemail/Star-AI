"""The faster Luau tokenizer returns exactly what the original character loop returned.

`_reference_tokens` is the tokenizer as it was before the performance change (re.match on a
slice of the rest of the code for every bracket, one loop step per whitespace or string
character). Random scripts built from Luau's tricky pieces (long brackets with equals levels,
unclosed strings, escapes at the very end, Unicode and control whitespace) must tokenize the same.
"""
import random
import re
from pathlib import Path

import pytest

from star import luau_lint
from star.luau_lint import _Token, _tokens, lint

_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]", re.ASCII)


def _reference_tokens(code: str) -> list[_Token]:
    out = []
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
            out.append(_Token(match.group(), line, i))
            i = match.end()
        line += code[start:i].count("\n")
    return out


PIECES = ("local", "x", "=", "game", ":", "GetService", "(", ")", '"ServerStorage"', "'DataStoreService'",
          "[", "]", "[[", "]]", "[=[", "]=]", "[==[", "]==]", "--", "--[[", "--[=[", "\n", "\r\n", " ", "\t",
          " ", " ", "　", "\x1c", "\x1f", "\x0b", "\x0c", "\x85", '"', "'", "\\", '\\"', "\\'",
          "\\\n", "a[1]", "1.5", "12", "é", "名字", "end", "function", "while true do", "wait(1)",
          "{", "}", ",", ".", "..", "#", "~=", "==", "!", "\x00")


def _random_script(rng: random.Random) -> str:
    return "".join(rng.choice(PIECES) for _ in range(rng.randint(0, 120)))


def test_random_scripts_tokenize_exactly_as_before():
    rng = random.Random(20261013)
    for _ in range(4000):
        code = _random_script(rng)
        assert _tokens(code) == _reference_tokens(code), repr(code)


@pytest.mark.parametrize("code", [
    "", "-", "--", "--[", "--[=", "--[==[ unclosed", "[", "[=", "[[", "[=[ x ]] still ]=]", '"', "'", '"\\',
    '"abc\\', "'a\\'b'", '"line\nbreak"', "x--[[c]]y", "a[[b]]c", "a[ [b] ]", " x　y", "\x1cz",
    "\\", "'\\\n'", '"unclosed\nmore lines\n',
])
def test_edge_cases_tokenize_exactly_as_before(code):
    assert _tokens(code) == _reference_tokens(code)


def test_repository_luau_tokenizes_exactly_as_before():
    files = sorted((Path(__file__).resolve().parents[1] / "evals" / "roblox").rglob("*.luau"))
    assert files
    for file in files:
        code = file.read_text(encoding="utf-8", errors="replace")
        assert _tokens(code) == _reference_tokens(code), file.name


def test_cached_tokens_are_a_fresh_list_each_call():
    code = "local a = 1\nprint(a)"
    first = _tokens(code)
    first.clear()
    assert _tokens(code) == _reference_tokens(code)


def _reference_block_end(v: list[str], start: int) -> int:
    """lint's block_end as it was: a forward scan to the matching end, for every call."""
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


BLOCK_WORDS = ("function", "if", "for", "while", "do", "repeat", "end", "until", "then", "x", "(", ")", "in",
               "pairs", "local", "=", "1")


def test_block_end_matches_the_forward_scan_for_every_start():
    rng = random.Random(1013)
    for _ in range(1500):
        # Mostly plain words, so `for ... do` windows of every length (and unclosed blocks) occur.
        words = [rng.choice(BLOCK_WORDS[:8]) if rng.random() < 0.35 else rng.choice(BLOCK_WORDS[8:])
                 for _ in range(rng.randint(0, 90))]
        block_end = luau_lint._block_end_finder(words)
        for start in range(len(words)):
            assert block_end(start) == _reference_block_end(words, start), (words, start)


def test_block_end_matches_on_repository_luau():
    files = sorted((Path(__file__).resolve().parents[1] / "evals" / "roblox").rglob("*.luau"))
    for file in files[:20]:
        words = [t.value for t in _tokens(file.read_text(encoding="utf-8", errors="replace"))]
        block_end = luau_lint._block_end_finder(words)
        for start, word in enumerate(words):
            if word in ("function", "while", "repeat", "for", "if"):
                assert block_end(start) == _reference_block_end(words, start), (file.name, start)


def test_local_shadowing_of_deprecated_globals_is_unchanged():
    def rules(code):
        return [(f.rule_id, f.line) for f in lint(code, external=False)]
    # Only calls after `local wait` (or spawn) are the local; earlier ones are still the global.
    assert rules("wait(1)\nlocal wait = task.wait\nwait(2)\nspawn(f)") == [
        ("deprecated-task-global", 1), ("deprecated-task-global", 4)]
    assert rules("local spawn = 1\nspawn(f) delay(1, f)") == [("deprecated-task-global", 2)]
    assert rules("local\nwait(1)") == []


def test_server_service_literal_detection_is_unchanged():
    # Detected through the string literal after GetService( ... including spacing and quotes ...
    for call in ('game:GetService("ServerStorage")', "game:GetService( 'DataStoreService' )",
                 'game:GetService(\n"ServerScriptService")'):
        found = lint(call + "\nlocal p = game.Players.LocalPlayer", external=False)
        assert "mixed-client-server" in {f.rule_id for f in found}, call
    # ... and not for other services or unquoted names.
    for call in ('game:GetService("Players")', "game:GetService(ServerStorageName)"):
        found = lint(call + "\nlocal p = game.Players.LocalPlayer", external=False)
        assert "mixed-client-server" not in {f.rule_id for f in found}, call
    assert len(luau_lint._SERVER_LITERALS) == len(luau_lint._SERVER)
