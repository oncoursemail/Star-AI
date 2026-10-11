"""Bounded source excerpts, not Markdown/RST rendering or executable examples.

Raw lines are retained exactly. Includes, macros, HTML and directives are never executed.
Long blocks may continue across excerpts; each continuation is explicitly labelled.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from .chunking import Chunk, Doc, ident_tokens
from .corpus_manifest import CorpusError


@dataclass
class Parsed:
    doc: Doc
    spans: list[dict]
    warnings: list[str]


def parse_source(raw: bytes, path: str, url: str) -> Parsed:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CorpusError("selected source is not UTF-8: " + path) from exc
    if "\x00" in text:
        raise CorpusError("binary material is not a documentation source")
    suffix = PurePosixPath(path).suffix
    kinds = {".md": "markdown", ".mdx": "mdx", ".rst": "rst",
             ".xml": "godot-xml", ".yaml": "reference-yaml"}
    if suffix not in kinds:
        raise CorpusError("unsupported source kind")
    kind = kinds[suffix]
    if suffix == ".xml" and re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        raise CorpusError("XML DTD/entity declarations are not supported")
    lines = text.splitlines(keepends=True)
    headings = []
    warning_set = set()
    heading = PurePosixPath(path).name
    fence = None
    language = ""
    languages = []
    for number, line in enumerate(lines):
        value = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})(.*)$", value) if suffix in (".md", ".mdx") else None
        was_in_code = fence is not None
        if marker:
            if fence is None:
                fence = marker.group(1)
                language = marker.group(2).strip()
            elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) and not marker.group(2).strip():
                fence = None
        if suffix in (".md", ".mdx") and not was_in_code and not marker:
            match = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", value)
            if match:
                heading = match.group(1)
            if "{{" in line or re.search(r"^import\b|\[!INCLUDE\]|:::code\b", line, re.I):
                warning_set.add("unresolved macro/include/import retained as source; no expansion")
            if re.search(r"</?[A-Za-z]", line):
                warning_set.add("HTML/MDX retained as source; no rendering or execution")
        elif suffix == ".rst":
            if number + 1 < len(lines) and value and re.fullmatch(r"[=~^*+\-]{3,}", lines[number + 1].strip()):
                if not line.startswith((" ", "\t", "..")):
                    heading = value
            directive = re.match(r"^\.\.\s+([\w-]+)::\s*(.*)$", value)
            if directive:
                if directive.group(1) in ("code-block", "code", "sourcecode"):
                    language = directive.group(2)
                else:
                    warning_set.add("RST directive retained without execution: " + directive.group(1))
        elif suffix == ".xml":
            match = re.search(r'<(class|method|member|signal|constant)\b[^>]*\bname="([^"]+)"', line)
            if match:
                heading = match.group(1) + " " + match.group(2)
            warning_set.add("Godot XML retained as source; no generated API/signature normalization")
        elif suffix == ".yaml":
            warning_set.add("reference YAML retained as source; use existing Roblox walker for exact symbol tables")
        if len(heading) > 300:
            raise CorpusError("source heading exceeds the 300-character bound")
        headings.append(heading)
        languages.append(language)
        if marker and fence is None:
            language = ""
    if fence:
        warning_set.add("unterminated source fence; no synthetic closing fence added")
    title = next((h for h in headings if h != PurePosixPath(path).name), PurePosixPath(path).name)
    doc = Doc(path=path, kind="source-" + kind, title=title, url=url)
    spans = []
    start = 0
    while start < len(lines):
        heading = headings[start]
        # Existing embed_input has a 1600-character cap. Keep the whole excerpt under it.
        cap = min(1200, 1600 - len("title: " + title + " | text: " + heading + "\n"))
        if cap < 400:
            raise CorpusError("title/heading leaves insufficient excerpt budget")
        end = start
        size = 0
        while end < len(lines) and size + len(lines[end]) <= cap:
            if end > start and headings[end] != heading:
                break
            size += len(lines[end])
            end += 1
        if end == start:
            raise CorpusError("one source line exceeds the excerpt bound; not silently cut")
        body = "".join(lines[start:end])
        if body.strip():
            span = {"line_start": start + 1, "line_end": end, "source_kind": kind,
                    "language": languages[start], "fragment": start > 0 or end < len(lines),
                    "standalone_example_verified": False}
            doc.chunks.append(Chunk(kind=doc.kind, heading=heading, anchor="", text=body,
                                    idents=ident_tokens(heading + " " + body)))
            spans.append(span)
        start = end
    if not doc.chunks:
        raise CorpusError("selected document contains no source text")
    if any(span["fragment"] for span in spans):
        warning_set.add("continued source excerpts; code fragments are not verified standalone examples")
    return Parsed(doc, spans, sorted(warning_set))
