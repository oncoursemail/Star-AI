# `star.design_db`

Source: `star/design_db.py`

Offline search over STAR's bundled UI design data (styles, palettes, font pairings, UX rules).

The tables are an unmodified MIT-licensed subset of UI UX Pro Max (see
star/data/design/README.md and PROVENANCE.json). Everything here is local and
deterministic: no network, no file writes, no model calls. Results are reference
data for the model, never instructions.

Main entry points:
- ``search(domain, query, limit)``: ranked rows of one table ("style", "palette",
  "typography", "ux") with BM25 over the descriptive columns.
- ``recommend(query)``: one style, one palette, one font pairing and the top UX
  rules for a product description, plus design tokens ready for ``design_md``.

## Constants

`DATA_DIR`, `DOMAINS`, `MAX_QUERY_CHARS`, `MAX_LIMIT`, `ATTRIBUTION`, `PALETTE_ROLES`, `PALETTE_PAIRS`

## Functions

### `rows`

```python
def rows(domain: str) -> tuple[dict, ...]
```

All rows of one bundled table, as read from the CSV (read-only tuple of dicts).

### `contrast_ratio`

```python
def contrast_ratio(foreground: str, background: str) -> float
```

WCAG 2.x contrast ratio of two opaque #RRGGBB colours.

### `search`

```python
def search(domain: str, query: str, limit: int=5, *, include_deprecated: bool=False) -> dict
```

Ranked matches from one table. Deprecated styles are left out unless asked for.

### `recommend`

```python
def recommend(query: str, *, ux_rules: int=5) -> dict
```

One coherent starting point (style + palette + font pairing + UX rules) and its tokens.

### `tokens_for`

```python
def tokens_for(palette: dict, fonts: dict, style: dict | None=None) -> dict
```

Design tokens in the DESIGN.md front-matter shape (colors, typography, rounded, spacing, components).
