"""Chunkers for the STAR knowledge prototype.

Three document shapes are handled differently on purpose:

* guides (Markdown/MDX): split on headings, then pack paragraphs/code blocks up to a size cap.
  A fenced code block is never cut in the middle of a line and keeps its fence.
* engine API reference (generated YAML): one chunk for the class/datatype/library overview and one
  chunk per member (property, method, event, callback, constructor, function). Each member chunk
  starts with a readable signature line so both BM25 and the embedding see the identifier.
* enums: one chunk per enum (items packed, split only if very large).

Everything here is pure text processing; no network and no model calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

import yaml

TARGET_CHARS = 1000   # preferred chunk body size (about 230-330 tokens for prose)
MAX_CHARS = 1500      # hard cap for a chunk body; star-embed accepts at most 512 tokens per input (physical batch size)
MIN_CHARS = 220       # sections smaller than this are merged with the following one


@dataclass
class Chunk:
    kind: str            # guide | api-overview | api-member | enum | news
    heading: str         # breadcrumb, e.g. "TweenService > Create" or "Frames > Clipping"
    anchor: str          # URL fragment without '#', may be empty
    text: str            # body shown to the model
    idents: str = ""     # extra identifier tokens for the FTS index (split CamelCase)


@dataclass
class Doc:
    path: str
    kind: str
    title: str
    url: str
    chunks: list[Chunk] = field(default_factory=list)


# ---------------------------------------------------------------- shared text helpers

_FENCE = re.compile(r"^(\s*)(```+|~~~+)(.*)$")
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9.]*(?:\s+[^<>]*)?/?>")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_XREF_PIPE = re.compile(r"\b(?:Class|Datatype|Enum|Library|Global)\.([A-Za-z0-9_.:()]+)\|([^`|]+)")
_XREF = re.compile(r"\b(?:Class|Datatype|Library)\.([A-Za-z0-9_]+)")
_XREF_GLOBAL = re.compile(r"\bGlobal\.(?:LuaGlobals|RobloxGlobals)\.([A-Za-z0-9_]+)")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
_IDENT = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[A-Z][a-z0-9]+)+[A-Za-z0-9]*\b|\b[A-Z]{2,}[a-z][A-Za-z0-9]*\b")


def split_camel(word: str) -> list[str]:
    """UIListLayout -> [UI, List, Layout]; TweenService -> [Tween, Service]."""
    return _CAMEL.findall(word)


def ident_tokens(text: str, limit: int = 120) -> str:
    """Split CamelCase identifiers found in text, for a separate FTS column."""
    seen: dict[str, None] = {}
    for word in _IDENT.findall(text):
        parts = split_camel(word)
        if len(parts) > 1:
            seen.setdefault(" ".join(parts), None)
            if len(seen) >= limit:
                break
    return " ; ".join(seen)


def clean_xrefs(text: str) -> str:
    """Creator Docs cross-reference markup -> plain identifiers.

    `Class.Tween|Tweens` -> `Tweens` (or `Tweens (Tween)` when the display text hides the name),
    `Class.TweenService:Create()` -> `TweenService:Create()`. `Enum.X` is real Luau and is kept.
    """
    def pipe(match: re.Match) -> str:
        target, shown = match.group(1), match.group(2).strip()
        stem = re.split(r"[.:(]", target)[0]
        return shown if stem.lower() in shown.lower() else f"{shown} ({target})"
    text = _XREF_PIPE.sub(pipe, text)
    text = _XREF_GLOBAL.sub(r"\1", text)
    return _XREF.sub(r"\1", text)


def _strip_tags_outside_code(prose: str) -> str:
    """Remove JSX/HTML tags from prose but leave inline code spans (`Pair<T>`) untouched."""
    out = []
    for i, part in enumerate(re.split(r"(`[^`\n]*`)", prose)):
        if i % 2:
            out.append(part)
        else:
            out.append(_TAG.sub("", _COMMENT.sub("", part)))
    return "".join(out)


def _closes(line: str, fence: str) -> bool:
    """CommonMark: a closing fence uses the same character, is at least as long, and has no info string."""
    stripped = line.strip()
    return stripped.startswith(fence) and stripped.strip(fence[0]) == ""


def split_blocks(body: str) -> list[tuple[str, str]]:
    """Return [(type, text)] where type is 'code' (fenced, intact) or 'prose' (one paragraph)."""
    blocks: list[tuple[str, str]] = []
    prose: list[str] = []
    code: list[str] = []
    fence = None

    def flush_prose():
        if prose:
            text = _strip_tags_outside_code("\n".join(prose))
            for para in re.split(r"\n\s*\n", text):
                para = para.strip("\n")
                if para.strip():
                    blocks.append(("prose", para))
            prose.clear()

    for line in body.split("\n"):
        m = _FENCE.match(line)
        if fence is None and m:
            flush_prose()
            fence = m.group(2)  # the full marker run: a ```` block may contain ``` blocks
            code.append(line.strip())
        elif fence is not None:
            code.append(line)
            if _closes(line, fence):
                blocks.append(("code", "\n".join(code)))
                code.clear()
                fence = None
        else:
            prose.append(line)
    if code:  # unterminated fence: keep what we have, closed
        blocks.append(("code", "\n".join(code) + "\n" + (fence or "```")))
    flush_prose()
    return blocks


def _split_long(kind: str, text: str, cap: int) -> list[str]:
    """Split one oversized block on line boundaries; code pieces are re-fenced."""
    if len(text) <= cap:
        return [text]
    lines = text.split("\n")
    opener = closer = ""
    if kind == "code" and len(lines) >= 2:
        opener, closer, lines = lines[0], lines[-1].strip() or "```", lines[1:-1]
    pieces, current, size = [], [], 0
    for line in lines:
        while len(line) > cap:  # a single huge line (minified data): hard cut
            head, line = line[:cap], line[cap:]
            if current:
                pieces.append(current)
                current, size = [], 0
            pieces.append([head])
        if size + len(line) + 1 > cap - len(opener) - len(closer) - 2 and current:
            pieces.append(current)
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        pieces.append(current)
    if kind == "code":
        return ["\n".join([opener, *p, closer]) for p in pieces]
    return ["\n".join(p) for p in pieces]


def pack(blocks: list[tuple[str, str]], target: int = TARGET_CHARS, cap: int = MAX_CHARS) -> list[str]:
    """Greedy pack of blocks into chunk bodies; never exceeds cap, prefers to close near target."""
    out, current, size = [], [], 0
    for kind, text in blocks:
        for piece in _split_long(kind, text, cap):
            if current and (size + len(piece) + 2 > cap or (size >= target and kind == "prose")):
                out.append("\n\n".join(current))
                current, size = [], 0
            current.append(piece)
            size += len(piece) + 2
    if current:
        out.append("\n\n".join(current))
    return out


def slugify(heading: str) -> str:
    text = re.sub(r"[`*_~]", "", heading.strip().lower())
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    return re.sub(r"\s+", "-", text).strip("-")


def frontmatter(raw: str) -> tuple[dict, str]:
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(raw[3:end]) or {}
            except yaml.YAMLError:
                meta = {}
            body = raw[end + 4:]
            return (meta if isinstance(meta, dict) else {}), body.lstrip("\n")
    return {}, raw


# ---------------------------------------------------------------- guides (Markdown / MDX)

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")


def chunk_markdown(raw: str, *, path: str, url: str, kind: str = "guide",
                   fallback_title: str = "") -> Doc:
    meta, body = frontmatter(raw.replace("\r\n", "\n"))
    title = str(meta.get("title") or fallback_title or path.rsplit("/", 1)[-1])
    description = str(meta.get("description") or "").strip()
    body = clean_xrefs(body)

    # 1. sections by heading (outside code fences)
    sections: list[tuple[list[str], list[str]]] = [([], [])]
    trail: list[tuple[int, str]] = []
    fence = None
    for line in body.split("\n"):
        m = _FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(2)
            elif _closes(line, fence):
                fence = None
        h = _HEADING.match(line) if fence is None else None
        if h:
            level, text = len(h.group(1)), _TAG.sub("", h.group(2)).strip()
            trail = [(lv, t) for lv, t in trail if lv < level] + [(level, text)]
            sections.append(([t for _, t in trail], []))
        else:
            sections[-1][1].append(line)

    # 2. merge tiny sections forward, then pack
    doc = Doc(path=path, kind=kind, title=title, url=url)
    pending_heads: list[str] | None = None
    pending_blocks: list[tuple[str, str]] = []

    def emit():
        nonlocal pending_heads, pending_blocks
        if not pending_blocks:
            pending_heads, pending_blocks = None, []
            return
        heads = pending_heads or []
        crumb = " > ".join([title, *heads]) if heads else title
        anchor = slugify(heads[-1]) if heads else ""
        for body_text in pack(pending_blocks):
            doc.chunks.append(Chunk(kind=kind, heading=crumb, anchor=anchor, text=body_text,
                                    idents=ident_tokens(crumb + " " + body_text)))
        pending_heads, pending_blocks = None, []

    first = True
    for heads, lines in sections:
        blocks = split_blocks("\n".join(lines))
        if first and description:
            blocks.insert(0, ("prose", description))
        first = False
        if not blocks:
            continue
        size = sum(len(t) for _, t in blocks)
        if pending_blocks:
            pending_size = sum(len(t) for _, t in pending_blocks)
            if pending_size < MIN_CHARS and pending_size + size <= MAX_CHARS:
                # carry the small previous section into this one, keeping its heading inline
                if heads:
                    pending_blocks.append(("prose", "#" * min(len(heads) + 1, 4) + " " + heads[-1]))
                pending_blocks.extend(blocks)
                continue
            emit()
        pending_heads, pending_blocks = heads, blocks
    emit()
    return doc


# ---------------------------------------------------------------- engine API reference (YAML)

def _txt(value) -> str:
    return clean_xrefs(str(value or "").strip())


def _tags(item: dict) -> str:
    bits = []
    if item.get("tags"):
        bits.append("Tags: " + ", ".join(map(str, item["tags"])))
    sec = item.get("security")
    if isinstance(sec, dict):
        bits.append("Security: read " + str(sec.get("read")) + ", write " + str(sec.get("write")))
    elif sec:
        bits.append("Security: " + str(sec))
    if item.get("thread_safety"):
        bits.append("Thread safety: " + str(item["thread_safety"]))
    if item.get("deprecation_message"):
        bits.append("DEPRECATED: " + _txt(item["deprecation_message"]))
    elif "Deprecated" in (item.get("tags") or []):
        bits.append("DEPRECATED")
    return ". ".join(bits)


def _params(item: dict) -> tuple[str, str]:
    params = item.get("parameters") or []
    sig = ", ".join(
        f"{p.get('name')}: {p.get('type')}" + (f" = {p['default']}" if p.get("default") not in (None, "") else "")
        for p in params if isinstance(p, dict))
    detail = "\n".join(f"- {p.get('name')} ({p.get('type')}): {_txt(p.get('summary'))}".rstrip(": ")
                       for p in params if isinstance(p, dict) and (p.get("summary") or p.get("type")))
    return sig, detail


def _returns(item: dict) -> tuple[str, str]:
    rets = [r for r in (item.get("returns") or []) if isinstance(r, dict)]
    sig = ", ".join(str(r.get("type")) for r in rets)
    detail = "\n".join(f"- {r.get('type')}: {_txt(r.get('summary'))}".rstrip(": ") for r in rets)
    return sig, detail


def _member_chunks(owner: str, group: str, item: dict, owner_kind: str) -> list[Chunk]:
    full = str(item.get("name") or "")
    short = re.split(r"[.:]", full)[-1] if full else ""
    psig, pdetail = _params(item)
    rsig, rdetail = _returns(item)
    label = {"properties": "property", "methods": "method", "events": "event", "callbacks": "callback",
             "constructors": "constructor", "functions": "function", "constants": "constant",
             "math_operations": "math operation"}.get(group, group)
    if group == "properties" or group == "constants":
        signature = f"{full}: {item.get('type')}"
    elif group == "events":
        signature = f"{full}({psig})"
    elif group == "math_operations":
        signature = f"{item.get('type_a')} {item.get('operation')} {item.get('type_b')} -> {item.get('return_type')}"
        short = ""
    else:
        signature = f"{full}({psig})" + (f": {rsig}" if rsig else "")
    head = f"{signature}   [{owner_kind} {owner} {label}]"
    parts = [("prose", head)]
    if item.get("summary"):
        parts.append(("prose", _txt(item["summary"])))
    meta = _tags(item)
    if meta:
        parts.append(("prose", meta))
    if pdetail:
        parts.append(("prose", "Parameters:\n" + pdetail))
    if rdetail:
        parts.append(("prose", "Returns:\n" + rdetail))
    description = _txt(item.get("description"))
    if description and description != _txt(item.get("summary")):
        parts.extend(split_blocks(description))
    bodies = pack(parts)
    crumb = f"{owner} > {short}" if short else f"{owner} > {label}"
    out = []
    for i, body in enumerate(bodies):
        if i:  # continuation keeps the signature so the piece stands alone
            body = head + " (continued)\n\n" + body
        out.append(Chunk(kind="api-member", heading=crumb, anchor=short, text=body,
                         idents=ident_tokens(owner + " " + short + " " + body, limit=60)))
    return out


def chunk_reference_yaml(raw: str, *, path: str, url: str, parents: dict[str, list[str]] | None = None) -> Doc:
    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or not data.get("name"):
        raise ValueError("not an engine reference file: " + path)
    name, kind = str(data["name"]), str(data.get("type") or "class")
    doc = Doc(path=path, kind="api-" + kind, title=name, url=url)

    if kind == "enum":
        head = f"Enum.{name}   [enum]"
        blocks = [("prose", head)]
        if data.get("summary"):
            blocks.append(("prose", _txt(data["summary"])))
        if data.get("description") and _txt(data["description"]) != _txt(data.get("summary")):
            blocks.extend(split_blocks(_txt(data["description"])))
        meta = _tags(data)
        if meta:
            blocks.append(("prose", meta))
        items = []
        for item in data.get("items") or []:
            line = f"- Enum.{name}.{item.get('name')} = {item.get('value')}"
            if item.get("summary"):
                line += ": " + " ".join(_txt(item["summary"]).split())
            if item.get("deprecation_message") or "Deprecated" in (item.get("tags") or []):
                line += " (deprecated)"
            items.append(line)
        if items:
            blocks.append(("prose", "Items:\n" + "\n".join(items)))
        for i, body in enumerate(pack(blocks)):
            if i:
                body = head + " (continued)\n\n" + body
            doc.chunks.append(Chunk(kind="enum", heading=f"Enum.{name}", anchor="", text=body,
                                    idents=ident_tokens(name + " " + body, limit=60)))
        return doc

    groups = [g for g in ("constructors", "constants", "properties", "methods", "functions",
                          "events", "callbacks", "math_operations") if data.get(g)]
    chain = []
    if parents is not None:
        seen, cursor = set(), name
        while cursor in parents and parents[cursor] and cursor not in seen:
            seen.add(cursor)
            cursor = parents[cursor][0]
            chain.append(cursor)
    head = f"{name}   [{kind}]"
    blocks = [("prose", head)]
    if chain:
        blocks.append(("prose", "Inherits: " + " > ".join(chain)))
    elif data.get("inherits"):
        blocks.append(("prose", "Inherits: " + ", ".join(map(str, data["inherits"]))))
    meta = _tags(data)
    if meta:
        blocks.append(("prose", meta))
    if data.get("summary"):
        blocks.append(("prose", _txt(data["summary"])))
    if data.get("description") and _txt(data["description"]) != _txt(data.get("summary")):
        blocks.extend(split_blocks(_txt(data["description"])))
    member_lines = []
    for group in groups:
        names = [re.split(r"[.:]", str(m.get("name") or ""))[-1] for m in data[group] if isinstance(m, dict)]
        names = [n for n in names if n]
        if names:
            member_lines.append(f"{group}: " + ", ".join(names))
    if member_lines:
        blocks.append(("prose", f"Members of {name}:\n" + "\n".join(member_lines)))
    for i, body in enumerate(pack(blocks)):
        if i:
            body = head + " (continued)\n\n" + body
        doc.chunks.append(Chunk(kind="api-overview", heading=name, anchor="", text=body,
                                idents=ident_tokens(name + " " + body, limit=80)))
    for group in groups:
        for item in data[group]:
            if isinstance(item, dict):
                doc.chunks.extend(_member_chunks(name, group, item, kind))
    return doc
