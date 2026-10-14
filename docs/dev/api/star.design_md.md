# `star.design_md`

Source: `star/design_md.py`

Read, write and lint a project's DESIGN.md (Google's design.md format, "alpha" version).

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

## Constants

`FILENAME`, `MAX_BYTES`, `MAX_LINES`, `MAX_DEPTH`, `WCAG_AA`, `WCAG_AA_LARGE`, `SPEC_URL`, `TOP_LEVEL_KEYS`, `TOKEN_GROUPS`, `COMPONENT_PROPERTIES`, `TYPOGRAPHY_PROPERTIES`, `SECTIONS`, `COLOR_PAIRS`, `RECOMMENDED_COLORS`, `RECOMMENDED_TYPOGRAPHY`

## Classes

### `DesignMdError`(ValueError)

A DESIGN.md file that cannot be read or written (size, location, YAML subset).

## Functions

### `parse_color`

```python
def parse_color(value) -> tuple[float, float, float, float] | None
```

sRGB channels 0..1 and alpha for hex, rgb(a), hsl(a) and common named colours.

Returns None for a value that is not a colour this module can measure. ``is_color``
separately accepts the other CSS forms the spec allows (oklch, color-mix, ...).

### `is_color`

```python
def is_color(value) -> bool
```

### `to_hex`

```python
def to_hex(value) -> str | None
```

### `contrast_ratio`

```python
def contrast_ratio(foreground, background) -> float
```

WCAG 2.x contrast ratio (1..21) of two opaque colours in any format ``parse_color`` reads.

### `split_front_matter`

```python
def split_front_matter(text: str) -> tuple[str | None, str, int]
```

(yaml text or None, markdown body, line number where the body starts).

### `parse_front_matter`

```python
def parse_front_matter(yaml_text: str) -> tuple[dict, list[dict]]
```

Parse the front matter. Returns (data, findings for duplicate keys and comment pitfalls).

### `lint`

```python
def lint(text: str) -> dict
```

Lint DESIGN.md text. Returns counts, findings and a token summary; never raises on bad content.

### `parse`

```python
def parse(text: str) -> dict
```

Tokens and section headings of DESIGN.md text. Raises DesignMdError when it cannot be read.

### `render`

```python
def render(name: str, tokens: dict, sections: dict[str, str] | None=None, *, description: str='') -> str
```

DESIGN.md text from tokens (colors/typography/rounded/spacing/components) and section prose.

Sections are written in the spec's order; unknown section names follow, in the given order.

### `draft`

```python
def draft(recommendation: dict, name: str) -> str
```

A DESIGN.md built from ``design_db.recommend`` output: tokens plus short, factual prose.

### `read`

```python
def read(workspace) -> dict
```

Read and lint <workspace>/DESIGN.md. The content is the owner's data, returned as-is.

### `write`

```python
def write(workspace, text: str, *, overwrite: bool=False) -> dict
```

Write <workspace>/DESIGN.md atomically. Refuses to replace an existing file unless asked,
and refuses text whose lint has errors (so a broken file is never saved by STAR).
