"""Read-aloud: turn a chat reply written for the screen into text that sounds right when Star says it.

Chat replies are Markdown: headings, bullet lists, tables, code blocks, links. Read literally they sound like a
robot reading punctuation. `spoken_text` keeps the words a person would say and replaces what only makes sense
on screen with one short spoken pointer ("I've put the code on screen."). Long replies are cut at a sentence
boundary so a wall of text does not keep talking for minutes.

Pure Python, no third-party imports, so it is tested in the plain repo test environment.
"""
from __future__ import annotations

import re

from .chunker import SentenceChunker, speakable

MAX_SPOKEN_CHARS = 1600
REST_ON_SCREEN = "The rest is on screen."
CODE_POINTER = "I've put the code on screen."
TABLE_POINTER = "There's a table on screen."

_THINK = re.compile(r"<think>.*?(</think>|\Z)", re.S | re.I)
_FENCE = re.compile(r"```.*?(```|\Z)", re.S)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d{1,2}[.)])\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_INLINE_CODE = re.compile(r"`([^`\n]{1,60})`")
_LONG_INLINE_CODE = re.compile(r"`[^`\n]{61,}`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_PATHLIKE = re.compile(r"(?<![\w/])(?:[A-Za-z]:[\\/])?(?:[\w.-]+[\\/]){2,}[\w.-]+")


def _end_sentence(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?…:;,":
        text += "."
    return text


def spoken_text(markdown: str, max_chars: int = MAX_SPOKEN_CHARS) -> str:
    """Screen text -> speech text. Empty when nothing in it is worth saying."""
    text = _THINK.sub(" ", markdown or "")
    code_seen = bool(_FENCE.search(text))
    text = _FENCE.sub(f"\n{CODE_POINTER}\n", text)
    text = _IMAGE.sub(r"\1", text)
    lines, in_table, out = text.splitlines(), False, []
    for line in lines:
        if _TABLE_ROW.match(line):
            if not in_table:
                out.append(TABLE_POINTER)
            in_table = True
            continue
        in_table = False
        if _RULE.match(line) or not line.strip():
            continue
        heading = _HEADING.match(line)
        bullet = _BULLET.match(line)
        if heading:
            out.append(_end_sentence(heading.group(1)))
        elif bullet:
            out.append(_end_sentence(bullet.group(1)))      # each list item becomes its own short sentence
        else:
            out.append(line.strip())
    text = " ".join(out)
    text = _LONG_INLINE_CODE.sub(" " + ("" if code_seen else CODE_POINTER + " "), text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _PATHLIKE.sub("a file path", text)
    text = speakable(text)
    # One pointer per kind is enough: "I've put the code on screen" three times in a row sounds broken.
    for pointer in (CODE_POINTER, TABLE_POINTER):
        first = text.find(pointer)
        if first >= 0:
            text = text[: first + len(pointer)] + text[first + len(pointer):].replace(pointer, "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.!?])\.+", r"\1", text)
    if len(text) > max_chars:
        cut = max(text.rfind(mark, 0, max_chars) for mark in (". ", "! ", "? "))
        text = (text[: cut + 1] if cut > max_chars // 3 else text[:max_chars].rsplit(" ", 1)[0] + ".")
        text = f"{text} {REST_ON_SCREEN}"
    return text if any(ch.isalnum() for ch in text) else ""


def sentences(text: str) -> list[str]:
    """Split speech text into the chunks the voice engine speaks one by one (first one early, as in calls)."""
    chunker = SentenceChunker()
    parts = list(chunker.feed(text)) + list(chunker.flush())
    return [part for part in parts if part.strip()]


__all__ = ["CODE_POINTER", "MAX_SPOKEN_CHARS", "REST_ON_SCREEN", "TABLE_POINTER", "sentences", "spoken_text"]
