# `star.design_system`

Source: `star/design_system.py`

STAR's OLED desktop design system.

A 4px spacing rhythm, one restrained solar-gold accent, dark neutral layers,
regular-weight icons and short, functional transitions. Sources and decisions
are documented in docs/STAR_DESKTOP_UX_RESEARCH.md.

## Constants

`COLORS`, `SPACING`, `MOTION_MS`

## Functions

### `contrast_ratio`

```python
def contrast_ratio(foreground: str, background: str) -> float
```

WCAG relative luminance contrast for opaque RGB colors.

### `stylesheet`

```python
def stylesheet() -> str
```
