"""Text normalisation and similarity for the near-duplicate and decontamination gates (standard library only).

Token n-gram shingles are hashed to 48-bit integers; Jaccard similarity and containment are computed exactly
(a few thousand items is small enough that MinHash would only add error).
"""
from __future__ import annotations

import hashlib
import math
import re

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\sA-Za-z_0-9]")
_LUAU_COMMENT = re.compile(r"--\[(=*)\[.*?\]\1\]|--[^\n]*", re.DOTALL)


def strip_comments(code: str) -> str:
    return _LUAU_COMMENT.sub(" ", code)


def tokens(text: str, *, code: bool = False) -> list[str]:
    if code:
        text = strip_comments(text)
    return [t.lower() for t in _TOKEN.findall(text)]


def shingles(toks: list[str], n: int = 5) -> set[int]:
    if not toks:
        return set()
    if len(toks) < n:
        toks = toks + [""] * (n - len(toks))
    out = set()
    for i in range(len(toks) - n + 1):
        digest = hashlib.blake2b("\x1f".join(toks[i:i + n]).encode("utf-8"), digest_size=6).digest()
        out.add(int.from_bytes(digest, "big"))
    return out


def jaccard(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def containment(small: set[int], big: set[int]) -> float:
    """Share of `small`'s shingles that also occur in `big`."""
    if not small or not big:
        return 0.0
    return len(small & big) / len(small)


def text_hash(text: str, *, code: bool = False) -> str:
    return hashlib.sha256(" ".join(tokens(text, code=code)).encode("utf-8")).hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def fingerprint(prompt: str, code: str, tests: str = "") -> dict:
    """Everything the similarity gates need from one candidate, computed once."""
    return {
        "prompt_hash": text_hash(prompt),
        "code_hash": text_hash(code, code=True),
        "prompt_sh5": shingles(tokens(prompt), 5),
        "prompt_sh8": shingles(tokens(prompt), 8),
        "code_sh5": shingles(tokens(code, code=True), 5),
        "tests_sh5": shingles(tokens(tests, code=True), 5),
    }
