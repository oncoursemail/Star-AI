"""Read, write and lint a project's DESIGN.md (Google's design.md format, "alpha" version).

Format: https://github.com/google-labs-code/design.md (Apache-2.0), docs/spec.md at commit
9bf8eae. A DESIGN.md is optional YAML front matter holding design tokens (colors, typography,
rounded, spacing, components) followed by Markdown sections (Overview, Colors, Typography,
Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts).

This is an independent Python implementation of the spec's checks (it does not run or copy the
upstream TypeScript linter). The lint rule names follow the upstream ones where they exist
(broken-ref, missing-primary, contrast-ratio, missing-sections, missing-typography,
section-order, unknown-key); STAR adds token-completeness, invalid-color, invalid-dimension
and invalid-typography.

PyYAML is not a STAR dependency, so the front matter is read by a small parser for the
block-style YAML subset DESIGN.md files use (nested mappings, block lists, quoted or plain
scalars, one-line ``[a, b]`` lists). Anything else is reported as a parse error, never guessed.
"""
from __future__ import annotations

import colorsys
import json
import os
from pathlib import Path
import re
import tempfile

FILENAME = "DESIGN.md"
MAX_BYTES = 200_000
MAX_LINES = 4000
MAX_DEPTH = 8
WCAG_AA = 4.5
WCAG_AA_LARGE = 3.0
SPEC_URL = "https://github.com/google-labs-code/design.md/blob/main/docs/spec.md"

TOP_LEVEL_KEYS = ("version", "name", "description", "omitted", "colors", "typography", "rounded",
                  "spacing", "components")
TOKEN_GROUPS = ("colors", "typography", "rounded", "spacing", "components")
COMPONENT_PROPERTIES = ("backgroundColor", "textColor", "typography", "rounded", "padding", "size",
                        "height", "width")
TYPOGRAPHY_PROPERTIES = ("fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing",
                         "fontFeature", "fontVariation")
# Canonical section order and the alternative headings the spec accepts.
SECTIONS = (
    ("Overview", ("overview", "brand & style", "brand and style")),
    ("Colors", ("colors", "colours")),
    ("Typography", ("typography",)),
    ("Layout", ("layout", "layout & spacing", "layout and spacing")),
    ("Elevation & Depth", ("elevation & depth", "elevation and depth", "elevation")),
    ("Shapes", ("shapes",)),
    ("Components", ("components",)),
    ("Do's and Don'ts", ("do's and don'ts", "dos and don'ts", "do's and don’ts", "dos and donts")),
)
# Text-on-background colour pairs checked when both tokens exist (STAR extension of the spec's
# component check; the names follow the spec's recommended tokens and common palettes).
COLOR_PAIRS = (("on-primary", "primary"), ("on-secondary", "secondary"), ("on-tertiary", "tertiary"),
               ("on-accent", "accent"), ("on-surface", "surface"), ("on-background", "background"),
               ("foreground", "background"), ("card-foreground", "card"), ("on-error", "error"),
               ("on-destructive", "destructive"), ("muted-foreground", "muted"))
RECOMMENDED_COLORS = ("primary", "secondary", "neutral", "surface", "on-surface", "error")
RECOMMENDED_TYPOGRAPHY = ("headline-lg", "headline-md", "body-lg", "body-md", "body-sm", "label-md")

_DIMENSION = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)(?:px|em|rem)$")
_NUMBER = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)$")
_REF = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")
_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
# CSS named colours most often used in design files; any other name is accepted but not measured.
_NAMED = {"black": "#000000", "white": "#FFFFFF", "red": "#FF0000", "green": "#008000", "blue": "#0000FF",
          "yellow": "#FFFF00", "gray": "#808080", "grey": "#808080", "silver": "#C0C0C0", "maroon": "#800000",
          "purple": "#800080", "fuchsia": "#FF00FF", "lime": "#00FF00", "olive": "#808000", "navy": "#000080",
          "teal": "#008080", "aqua": "#00FFFF", "orange": "#FFA500", "cornflowerblue": "#6495ED",
          "rebeccapurple": "#663399", "whitesmoke": "#F5F5F5", "slategray": "#708090"}
_OTHER_COLOR = re.compile(r"^(?:oklch|oklab|lch|lab|hwb|color-mix|color)\(.*\)$", re.I)
_CSS_IDENT = re.compile(r"^[a-z]+$", re.I)


class DesignMdError(ValueError):
    """A DESIGN.md file that cannot be read or written (size, location, YAML subset)."""


# ---------------------------------------------------------------------------------------------
# Colours and WCAG contrast
# ---------------------------------------------------------------------------------------------

def parse_color(value) -> tuple[float, float, float, float] | None:
    """sRGB channels 0..1 and alpha for hex, rgb(a), hsl(a) and common named colours.

    Returns None for a value that is not a colour this module can measure. ``is_color``
    separately accepts the other CSS forms the spec allows (oklch, color-mix, ...).
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    lower = text.lower()
    if lower == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if lower in _NAMED:
        text = _NAMED[lower]
    if _HEX.match(text):
        digits = text[1:]
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits)
        channels = [int(digits[i:i + 2], 16) / 255 for i in range(0, len(digits), 2)]
        return (channels[0], channels[1], channels[2], channels[3] if len(channels) == 4 else 1.0)
    match = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", lower)
    if not match:
        return None
    kind, inner = match.groups()
    parts = [p for p in re.split(r"[\s,/]+", inner.strip()) if p]
    if len(parts) not in (3, 4):
        return None
    try:
        def number(part: str, scale: float) -> float:
            return float(part[:-1]) / 100 if part.endswith("%") else float(part) / scale
        alpha = number(parts[3], 1.0) if len(parts) == 4 else 1.0
        if kind.startswith("rgb"):
            r, g, b = (number(p, 255.0) for p in parts[:3])
        else:
            hue = float(parts[0].removesuffix("deg")) / 360 % 1.0
            sat, light = number(parts[1], 100.0), number(parts[2], 100.0)
            r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    except ValueError:
        return None
    clamp = lambda v: min(1.0, max(0.0, v))  # noqa: E731
    return (clamp(r), clamp(g), clamp(b), clamp(alpha))


def is_color(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    return (parse_color(text) is not None or bool(_OTHER_COLOR.match(text))
            or (bool(_CSS_IDENT.match(text)) and text.lower() not in {"none", "auto", "inherit"}))


def to_hex(value) -> str | None:
    parsed = parse_color(value)
    if parsed is None:
        return None
    return "#" + "".join(f"{round(c * 255):02X}" for c in parsed[:3])


def _luminance(rgb) -> float:
    def linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground, background) -> float:
    """WCAG 2.x contrast ratio (1..21) of two opaque colours in any format ``parse_color`` reads."""
    fg, bg = parse_color(foreground), parse_color(background)
    if fg is None or bg is None:
        raise ValueError("contrast needs two colours in hex, rgb() or hsl() form")
    if fg[3] < 1 or bg[3] < 1:
        raise ValueError("contrast of a translucent colour depends on what is behind it")
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------------------------
# Front matter (block-style YAML subset)
# ---------------------------------------------------------------------------------------------

def split_front_matter(text: str) -> tuple[str | None, str, int]:
    """(yaml text or None, markdown body, line number where the body starts)."""
    lines = text.removeprefix("﻿").splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, text, 1
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:]), index + 2
    raise DesignMdError("Front matter starts with '---' but has no closing '---' line")


def _strip_comment(line: str) -> str:
    quote = None
    for position, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (position == 0 or line[position - 1] in " \t"):
            return line[:position].rstrip()
    return line.rstrip()


def _scalar(text: str, line: int):
    text = text.strip()
    if text == "":
        return None
    if text[0] == '"':
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            raise DesignMdError(f"line {line}: unsupported double-quoted string") from None
        if not isinstance(value, str):
            raise DesignMdError(f"line {line}: unsupported double-quoted string")
        return value
    if text[0] == "'":
        if len(text) < 2 or text[-1] != "'":
            raise DesignMdError(f"line {line}: unterminated single-quoted string")
        return text[1:-1].replace("''", "'")
    if text[0] == "[":
        if text[-1] != "]":
            raise DesignMdError(f"line {line}: multi-line flow lists are not supported")
        inner = text[1:-1].strip()
        return [_scalar(part, line) for part in inner.split(",")] if inner else []
    if text[0] in "{&*!|>%@`":
        raise DesignMdError(f"line {line}: YAML feature {text[0]!r} is not supported in DESIGN.md front matter")
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", text):
        return float(text)
    return text


def _key(text: str, line: int) -> str:
    text = text.strip()
    if text[:1] in "\"'":
        value = _scalar(text, line)
        if not isinstance(value, str):
            raise DesignMdError(f"line {line}: invalid key")
        return value
    if not text or text[0] in "-?[{":
        raise DesignMdError(f"line {line}: invalid key {text!r}")
    return text


def _split_pair(content: str, line: int) -> tuple[str, str] | None:
    """Split 'key: value' at the first ':' outside quotes that ends the key."""
    quote = None
    for position, char in enumerate(content):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == ":" and (position + 1 == len(content) or content[position + 1] in " \t"):
            return _key(content[:position], line), content[position + 1:]
    return None


def parse_front_matter(yaml_text: str) -> tuple[dict, list[dict]]:
    """Parse the front matter. Returns (data, findings for duplicate keys and comment pitfalls)."""
    findings: list[dict] = []
    lines = []
    for number, raw in enumerate(yaml_text.splitlines(), start=2):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise DesignMdError(f"line {number}: tabs are not allowed for YAML indentation")
        content = _strip_comment(raw)
        if not content.strip():
            continue
        if content.strip() != raw.strip() and re.search(r":\s+#[0-9A-Fa-f]{3,8}\b", raw):
            findings.append(_finding("error", "invalid-color", f"line {number}",
                                     "An unquoted #hex value starts a YAML comment, so this token has no "
                                     "value. Quote it, for example \"#1A1C1E\"."))
        lines.append((len(content) - len(content.lstrip(" ")), content.strip(), number))
    if len(lines) > MAX_LINES:
        raise DesignMdError("Front matter is too long")
    if not lines:
        return {}, findings
    value, index = _block(lines, 0, lines[0][0], 0, findings, "")
    if index != len(lines):
        raise DesignMdError(f"line {lines[index][2]}: unexpected indentation")
    if not isinstance(value, dict):
        raise DesignMdError("Front matter must be a mapping of keys to values")
    return value, findings


def _block(lines, index, indent, depth, findings, path):
    if depth > MAX_DEPTH:
        raise DesignMdError(f"line {lines[index][2]}: front matter is nested too deeply")
    content = lines[index][1]
    if content == "-" or content.startswith("- "):
        return _list(lines, index, indent, depth, findings, path)
    return _mapping(lines, index, indent, depth, findings, path)


def _mapping(lines, index, indent, depth, findings, path):
    result: dict = {}
    while index < len(lines):
        column, content, number = lines[index]
        if column < indent:
            break
        if column > indent:
            raise DesignMdError(f"line {number}: unexpected indentation")
        if content == "-" or content.startswith("- "):
            break
        pair = _split_pair(content, number)
        if pair is None:
            raise DesignMdError(f"line {number}: expected 'key: value'")
        key, rest = pair
        here = f"{path}.{key}" if path else key
        if key in result:
            findings.append(_finding("error", "duplicate-key", here, f"Key '{key}' is defined twice (line {number})."))
        index += 1
        if rest.strip():
            result[key] = _scalar(rest, number)
            continue
        if index < len(lines) and (lines[index][0] > indent or
                                   (lines[index][0] == indent and lines[index][1].startswith("-"))):
            result[key], index = _block(lines, index, lines[index][0], depth + 1, findings, here)
        else:
            result[key] = None
    return result, index


def _list(lines, index, indent, depth, findings, path):
    result: list = []
    while index < len(lines):
        column, content, number = lines[index]
        if column != indent or not (content == "-" or content.startswith("- ")):
            if column > indent:
                raise DesignMdError(f"line {number}: unexpected indentation")
            break
        rest = content[1:].lstrip()
        here = f"{path}[{len(result)}]"
        if not rest:
            index += 1
            if index < len(lines) and lines[index][0] > indent:
                item, index = _block(lines, index, lines[index][0], depth + 1, findings, here)
            else:
                item = None
            result.append(item)
            continue
        if _split_pair(rest, number) is not None:
            # "- key: value" starts a mapping whose keys sit at the column of "key".
            inner = column + (len(content) - len(rest))
            lines = lines[:index] + [(inner, rest, number)] + lines[index + 1:]
            item, index = _mapping(lines, index, inner, depth + 1, findings, here)
            result.append(item)
            continue
        result.append(_scalar(rest, number))
        index += 1
    return result, index


# ---------------------------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------------------------

def _finding(severity: str, rule: str, path: str, message: str) -> dict:
    return {"severity": severity, "rule": rule, "path": path, "message": message}


def _sections(body: str, first_line: int) -> tuple[list[tuple[str, int]], bool]:
    headings, fenced = [], False
    for offset, line in enumerate(body.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced and line.startswith("## "):
            headings.append((line[3:].strip(), first_line + offset))
    return headings, fenced


def _canonical(heading: str) -> str | None:
    lowered = heading.strip().lower().rstrip(":")
    for canonical, aliases in SECTIONS:
        if lowered in aliases:
            return canonical
    return None


def _lookup(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


def _resolve(data: dict, value, *, seen=()):
    """Follow {group.token} references to a primitive value. Returns (value, error message or '')."""
    if not isinstance(value, str):
        return value, ""
    match = _REF.match(value.strip())
    if not match:
        return value, ""
    target = match.group(1)
    if target in seen:
        return None, f"circular reference through {{{target}}}"
    found, ok = _lookup(data, target)
    if not ok:
        return None, f"reference {{{target}}} does not resolve to any defined token"
    return _resolve(data, found, seen=(*seen, target))


def _omitted(data: dict) -> set[str]:
    sections = set()
    for entry in data.get("omitted") or []:
        if isinstance(entry, str):
            sections.add(entry.lower())
        elif isinstance(entry, dict) and isinstance(entry.get("section"), str):
            sections.add(entry["section"].lower())
    return sections


def lint(text: str) -> dict:
    """Lint DESIGN.md text. Returns counts, findings and a token summary; never raises on bad content."""
    if not isinstance(text, str):
        raise TypeError("DESIGN.md text must be a string")
    findings: list[dict] = []
    data: dict = {}
    body, body_line = text, 1
    if len(text.encode("utf-8")) > MAX_BYTES:
        findings.append(_finding("error", "too-large", "", f"DESIGN.md is larger than {MAX_BYTES} bytes."))
        return _result(findings, data)
    try:
        yaml_text, body, body_line = split_front_matter(text)
        if yaml_text is None:
            findings.append(_finding("warning", "no-front-matter", "",
                                     "No YAML front matter: the file has no machine-readable design tokens."))
        else:
            data, parse_findings = parse_front_matter(yaml_text)
            findings.extend(parse_findings)
    except DesignMdError as exc:
        findings.append(_finding("error", "yaml-parse", "", str(exc)))
        data = {}
    if data:
        findings.extend(_lint_tokens(data))
    findings.extend(_lint_sections(body, body_line))
    return _result(findings, data)


def _lint_tokens(data: dict) -> list[dict]:
    out: list[dict] = []
    for key in data:
        if key not in TOP_LEVEL_KEYS:
            out.append(_finding("warning", "unknown-key", key, f"'{key}' is not a DESIGN.md front-matter key "
                                "and will be ignored by consumers."))
    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        out.append(_finding("warning", "missing-name", "name", "The design system has no 'name'."))
    for group in TOKEN_GROUPS:
        if group in data and data[group] is not None and not isinstance(data[group], dict):
            out.append(_finding("error", "invalid-group", group, f"'{group}' must be a mapping of token names."))
    colors = data.get("colors") if isinstance(data.get("colors"), dict) else {}
    typography = data.get("typography") if isinstance(data.get("typography"), dict) else {}
    omitted = _omitted(data)

    measurable: dict[str, str] = {}
    for name, value in colors.items():
        resolved, error = _resolve(data, value)
        if error:
            out.append(_finding("error", "broken-ref", f"colors.{name}", error.capitalize() + "."))
        elif not is_color(resolved):
            out.append(_finding("error", "invalid-color", f"colors.{name}",
                                f"{value!r} is not a CSS colour (use #RRGGBB, rgb(), hsl() or a named colour)."))
        elif parse_color(resolved) is not None:
            measurable[name] = resolved
    if colors and "primary" not in colors:
        out.append(_finding("warning", "missing-primary", "colors",
                            "No 'primary' colour: agents will invent the key colour, reducing control of the palette."))
    if colors and not typography and "typography" not in omitted:
        out.append(_finding("warning", "missing-typography", "typography",
                            "No typography tokens: agents will fall back to their own font choices."))
    for name, spec in typography.items():
        out.extend(_lint_typography(data, name, spec))
    for group, allow_number in (("rounded", False), ("spacing", True)):
        tokens = data.get(group)
        if not isinstance(tokens, dict) or not tokens:
            if colors and group not in omitted:
                out.append(_finding("info", "missing-sections", group,
                                    f"No '{group}' tokens; {'corner rounding' if group == 'rounded' else 'spacing'} "
                                    "will fall back to agent defaults."))
            continue
        for name, value in tokens.items():
            resolved, error = _resolve(data, value)
            if error:
                out.append(_finding("error", "broken-ref", f"{group}.{name}", error.capitalize() + "."))
            elif not _is_dimension(resolved) and not (allow_number and _is_number(resolved)):
                out.append(_finding("warning" if group == "rounded" else "info", "invalid-dimension", f"{group}.{name}",
                                    f"{value!r} is not a dimension (a number with px, em or rem)."))
    components = data.get("components") if isinstance(data.get("components"), dict) else {}
    for name, props in components.items():
        out.extend(_lint_component(data, name, props))
    # STAR extension: text/background colour pairs and recommended token coverage.
    for text_token, background_token in COLOR_PAIRS:
        if text_token in measurable and background_token in measurable:
            try:
                ratio = contrast_ratio(_resolve(data, measurable[text_token])[0],
                                       _resolve(data, measurable[background_token])[0])
            except ValueError:
                out.append(_finding("info", "contrast-ratio", f"colors.{text_token}",
                                    f"Contrast with {background_token} not measured (translucent colour)."))
                continue
            if ratio < WCAG_AA:
                out.append(_finding("warning", "contrast-ratio", f"colors.{text_token}",
                                    f"{text_token} on {background_token} is {ratio:.2f}:1, below WCAG AA 4.5:1 "
                                    f"for normal text{'' if ratio >= WCAG_AA_LARGE else ' (and below 3:1 for large text)'}."))
        elif (text_token in colors) != (background_token in colors) and text_token.startswith("on-"):
            present, missing = ((text_token, background_token) if text_token in colors
                                else (background_token, text_token))
            if present == background_token and any(
                    bg == background_token and fg in colors for fg, bg in COLOR_PAIRS):
                continue   # e.g. 'background' is already paired with 'foreground'
            out.append(_finding("info", "token-completeness", f"colors.{missing}",
                                f"'{present}' is defined without its pair '{missing}', so its text contrast "
                                "cannot be checked."))
    if colors:
        missing = [name for name in RECOMMENDED_COLORS if name not in colors]
        if missing:
            out.append(_finding("info", "token-completeness", "colors",
                                "Recommended colour tokens not defined: " + ", ".join(missing) + "."))
    if typography:
        missing = [name for name in RECOMMENDED_TYPOGRAPHY if name not in typography]
        if len(missing) == len(RECOMMENDED_TYPOGRAPHY):
            out.append(_finding("info", "token-completeness", "typography",
                                "None of the recommended typography levels (" + ", ".join(RECOMMENDED_TYPOGRAPHY)
                                + ") are defined; custom names are valid but less predictable for agents."))
    return out


def _is_dimension(value) -> bool:
    return isinstance(value, str) and bool(_DIMENSION.match(value.strip()))


def _is_number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)) or (
        isinstance(value, str) and bool(_NUMBER.match(value.strip())))


def _lint_typography(data: dict, name: str, spec) -> list[dict]:
    path = f"typography.{name}"
    if not isinstance(spec, dict):
        return [_finding("error", "invalid-typography", path, "A typography token must be a mapping of font properties.")]
    out = []
    for prop, value in spec.items():
        value, error = _resolve(data, value)
        if error:
            out.append(_finding("error", "broken-ref", f"{path}.{prop}", error.capitalize() + "."))
            continue
        if prop not in TYPOGRAPHY_PROPERTIES:
            out.append(_finding("warning", "unknown-key", f"{path}.{prop}", f"'{prop}' is not a typography property."))
        elif prop == "fontFamily" and not (isinstance(value, str) and value.strip()):
            out.append(_finding("warning", "invalid-typography", f"{path}.fontFamily", "fontFamily must be a font name."))
        elif prop in ("fontSize", "letterSpacing") and not _is_dimension(value):
            out.append(_finding("warning", "invalid-dimension", f"{path}.{prop}",
                                f"{value!r} is not a dimension (px, em or rem)."))
        elif prop == "fontWeight" and not (_is_number(value) and 1 <= float(value) <= 1000):
            out.append(_finding("warning", "invalid-typography", f"{path}.fontWeight",
                                f"{value!r} is not a numeric font weight from 1 to 1000."))
        elif prop == "lineHeight" and not (_is_dimension(value) or _is_number(value)):
            out.append(_finding("warning", "invalid-dimension", f"{path}.lineHeight",
                                f"{value!r} is neither a dimension nor a unitless multiplier."))
    if "fontFamily" not in spec:
        out.append(_finding("info", "invalid-typography", path, "No fontFamily: agents will pick a font."))
    return out


def _lint_component(data: dict, name: str, props) -> list[dict]:
    path = f"components.{name}"
    if not isinstance(props, dict):
        return [_finding("error", "invalid-group", path, "A component must be a mapping of properties.")]
    out, resolved = [], {}
    for prop, value in props.items():
        if prop not in COMPONENT_PROPERTIES:
            out.append(_finding("warning", "broken-ref", f"{path}.{prop}",
                                f"'{prop}' is not a recognised component sub-token. Valid sub-tokens: "
                                + ", ".join(COMPONENT_PROPERTIES) + "."))
        value_resolved, error = _resolve(data, value)
        if error:
            out.append(_finding("error", "broken-ref", f"{path}.{prop}", error.capitalize() + "."))
            continue
        resolved[prop] = value_resolved
        if prop in ("backgroundColor", "textColor") and not is_color(value_resolved):
            out.append(_finding("error", "invalid-color", f"{path}.{prop}", f"{value!r} is not a colour."))
    background, foreground = resolved.get("backgroundColor"), resolved.get("textColor")
    if background is not None and foreground is not None:
        try:
            ratio = contrast_ratio(foreground, background)
        except ValueError:
            if parse_color(background) is not None and parse_color(foreground) is not None:
                out.append(_finding("info", "contrast-ratio", path, "Contrast not measured (translucent colour)."))
        else:
            if ratio < WCAG_AA:
                out.append(_finding("warning", "contrast-ratio", path,
                                    f"textColor ({to_hex(foreground)}) on backgroundColor ({to_hex(background)}) has "
                                    f"contrast ratio {ratio:.2f}:1, below WCAG AA minimum of 4.5:1."))
    return out


def _lint_sections(body: str, first_line: int) -> list[dict]:
    out = []
    headings, unclosed = _sections(body, first_line)
    if unclosed:
        out.append(_finding("warning", "markdown", "body", "A ``` code fence is not closed."))
    seen: dict[str, int] = {}
    order = [canonical for canonical, _ in SECTIONS]
    last = -1
    for heading, line in headings:
        canonical = _canonical(heading) or heading.strip().lower()
        if canonical in seen:
            out.append(_finding("error", "duplicate-section", f"line {line}",
                                f"Section '## {heading}' appears twice (first on line {seen[canonical]})."))
            continue
        seen[canonical] = line
        if canonical in order:
            position = order.index(canonical)
            if position < last:
                out.append(_finding("warning", "section-order", f"line {line}",
                                    f"Section '## {heading}' is out of order; the spec order is: "
                                    + ", ".join(order) + "."))
            last = max(last, position)
    return out


def _result(findings: list[dict], data: dict) -> dict:
    counts = {level: sum(1 for f in findings if f["severity"] == level) for level in ("error", "warning", "info")}
    summary = {group: len(data[group]) if isinstance(data.get(group), dict) else 0 for group in TOKEN_GROUPS}
    return {"ok": counts["error"] == 0, "errors": counts["error"], "warnings": counts["warning"],
            "infos": counts["info"], "findings": findings, "summary": summary,
            "name": data.get("name") if isinstance(data.get("name"), str) else "", "spec": SPEC_URL}


def parse(text: str) -> dict:
    """Tokens and section headings of DESIGN.md text. Raises DesignMdError when it cannot be read."""
    yaml_text, body, body_line = split_front_matter(text)
    data = parse_front_matter(yaml_text)[0] if yaml_text is not None else {}
    headings, _ = _sections(body, body_line)
    return {"tokens": data, "sections": [heading for heading, _ in headings]}


# ---------------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------------

_PLAIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()%/-]*$")


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value)
    if (_PLAIN.match(text) and text.lower() not in ("true", "false", "null", "yes", "no", "on", "off")
            and not _NUMBER.match(text) and text == text.strip()):
        return text
    return json.dumps(text, ensure_ascii=False)


def _yaml_lines(data, indent: int = 0) -> list[str]:
    pad = " " * indent
    lines = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_text = key if _PLAIN.match(str(key)) and " " not in str(key) else json.dumps(str(key))
            if isinstance(value, dict):
                if not value:
                    continue
                lines.append(f"{pad}{key_text}:")
                lines.extend(_yaml_lines(value, indent + 2))
            elif isinstance(value, list):
                if not value:
                    continue
                lines.append(f"{pad}{key_text}:")
                for item in value:
                    if isinstance(item, dict):
                        inner = _yaml_lines(item, indent + 4)
                        lines.append(f"{pad}  - {inner[0].strip()}")
                        lines.extend(inner[1:])
                    else:
                        lines.append(f"{pad}  - {_yaml_scalar(item)}")
            else:
                lines.append(f"{pad}{key_text}: {_yaml_scalar(value)}")
    return lines


def render(name: str, tokens: dict, sections: dict[str, str] | None = None, *, description: str = "") -> str:
    """DESIGN.md text from tokens (colors/typography/rounded/spacing/components) and section prose.

    Sections are written in the spec's order; unknown section names follow, in the given order.
    """
    if not isinstance(name, str) or not name.strip():
        raise DesignMdError("A DESIGN.md needs a name")
    front = {"version": "alpha", "name": name.strip()}
    if description.strip():
        front["description"] = " ".join(description.split())
    for group in TOKEN_GROUPS:
        if isinstance(tokens.get(group), dict) and tokens[group]:
            front[group] = tokens[group]
    if tokens.get("omitted"):
        front["omitted"] = tokens["omitted"]
    parts = ["---", *_yaml_lines(front), "---", "", f"# {name.strip()}", ""]
    sections = dict(sections or {})
    ordered = [canonical for canonical, _ in SECTIONS if canonical in sections]
    ordered += [heading for heading in sections if heading not in ordered]
    for heading in ordered:
        text = str(sections[heading]).strip()
        if text:
            parts += [f"## {heading}", "", text, ""]
    return "\n".join(parts).rstrip() + "\n"


def draft(recommendation: dict, name: str) -> str:
    """A DESIGN.md built from ``design_db.recommend`` output: tokens plus short, factual prose."""
    style = recommendation.get("style") or {}
    palette = recommendation.get("palette") or {}
    fonts = recommendation.get("typography") or {}
    rules = recommendation.get("ux_rules") or []
    tokens = recommendation.get("tokens") or {}
    colors = tokens.get("colors") or {}
    color_lines = "\n".join(f"- **{token}** ({value})" for token, value in colors.items())
    sections = {
        "Overview": (f"Starting point for {recommendation.get('query', 'this product')}: the "
                     f"**{style.get('name', 'chosen')}** style ({style.get('keywords', '')}). "
                     f"Best for: {style.get('best_for', 'n/a')}. Avoid for: {style.get('avoid_for', 'n/a')}."),
        "Colors": (f"Palette based on the '{palette.get('name', '')}' row of the bundled palette table. "
                   f"{palette.get('notes', '')}\n\n{color_lines}").strip(),
        "Typography": (f"Headings use **{fonts.get('heading_font', 'n/a')}**, body text uses "
                       f"**{fonts.get('body_font', 'n/a')}** ({fonts.get('name', '')}: {fonts.get('mood', '')})."),
        "Layout": "A 4px-based spacing scale (4, 8, 16, 24, 32, 48). Keep related controls grouped and aligned.",
        "Shapes": "Corner radii come from the `rounded` tokens; use one radius per component family.",
        "Components": "Buttons and cards reference the tokens above; add variants (hover, pressed, disabled) as needed.",
        "Do's and Don'ts": "\n".join(
            [f"- Do: {rule['do']} ({rule['issue']})" for rule in rules if rule.get("do")] +
            [f"- Don't: {rule['dont']}" for rule in rules[:3] if rule.get("dont")] +
            ["- Do keep text contrast at WCAG AA (4.5:1 for normal text) or better."]),
    }
    return render(name, tokens, sections,
                  description=f"Generated by STAR from bundled UI UX Pro Max data (MIT) for: {recommendation.get('query', '')}")


# ---------------------------------------------------------------------------------------------
# Project file access (fixed file name in the workspace root)
# ---------------------------------------------------------------------------------------------

def _path(workspace) -> Path:
    if workspace is None:
        raise DesignMdError("Choose a workspace folder first")
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise DesignMdError("The workspace folder does not exist")
    target = root / FILENAME
    if target.is_symlink():
        raise DesignMdError("DESIGN.md is a symbolic link; STAR only reads a regular file")
    return target


def read(workspace) -> dict:
    """Read and lint <workspace>/DESIGN.md. The content is the owner's data, returned as-is."""
    target = _path(workspace)
    if not target.is_file():
        return {"exists": False, "path": FILENAME, "note": "No DESIGN.md in the workspace root yet."}
    if target.stat().st_size > MAX_BYTES:
        raise DesignMdError(f"DESIGN.md is larger than {MAX_BYTES} bytes")
    text = target.read_text(encoding="utf-8")
    return {"exists": True, "path": FILENAME, "text": text, "lint": lint(text)}


def write(workspace, text: str, *, overwrite: bool = False) -> dict:
    """Write <workspace>/DESIGN.md atomically. Refuses to replace an existing file unless asked,
    and refuses text whose lint has errors (so a broken file is never saved by STAR)."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise DesignMdError(f"DESIGN.md text must be a string of at most {MAX_BYTES} bytes")
    report = lint(text)
    if not report["ok"]:
        raise DesignMdError("DESIGN.md has lint errors; fix them before saving: "
                            + "; ".join(f["message"] for f in report["findings"] if f["severity"] == "error")[:400])
    target = _path(workspace)
    if target.exists() and not overwrite:
        raise DesignMdError("DESIGN.md already exists; pass overwrite=True to replace it")
    descriptor, temporary = tempfile.mkstemp(prefix=".DESIGN.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return {"written": True, "path": FILENAME, "bytes": len(text.encode("utf-8")), "lint": report}
