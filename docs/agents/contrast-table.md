# STAR desktop color contrast matrix (WCAG 2.2 AA)

## Measurement and scope

Measured **46 actual CSS role pairs** across `tokens.css`, `stellar-ui.css`,
`redesign.css`, `settings-ui.css`, and `chat.css`. The desktop ships one
OLED-dark palette shared by `.shell` and portalled `.star-layer`; there is
no separate light colour scheme in these stylesheets. Reduced-motion media
queries only alter timing. Decorative dividers are not mistaken for the
boundaries of interactive controls.

Tests read the **real CSS selectors and declarations** plus the live token
definitions on every run and use
`star.design_md.parse_color` / `star.design_md.contrast_ratio`.
For `rgba` washes, each sRGB channel is alpha-composited onto the explicitly
listed underlying opaque surface before contrast is computed; translucent
foreground strokes are composited onto their effective background. The test
compares full-precision contrast with thresholds **4.5:1 text** and **3:1
essential borders and focus**, and the table below rounds only for display.
These ratios are computed from tokens, not measured browser screenshots.

**Before: 9 failures / 46; after: 0 failures / 46.**
Failures were interactive control boundaries / focus, not default text.

## Measured pairs

| CSS use | Role | Foreground | Background (underlay for alpha) | Minimum | Before | After |
| --- | --- | --- | --- | ---: | ---: | ---: |
| shell-body (`stellar-ui.css`) | text | `--star-body` | `--star-bg` | 3.0 | 14.66 | 14.66 |
| rail-hover (`stellar-ui.css`) | text | `--star-text` | `--star-surface-1` | 4.5 | 16.31 | 16.31 |
| rail-current (`stellar-ui.css`) | text | `--star-text` | `--star-surface-2` | 4.5 | 15.20 | 15.20 |
| topbar-hover (`stellar-ui.css`) | text | `--star-text` | `--star-surface-2` | 4.5 | 15.20 | 15.20 |
| search-field (`stellar-ui.css`) | text | `--star-text` | `--star-surface-1` | 4.5 | 16.31 | 16.31 |
| preview-ribbon (`stellar-ui.css`) | text | `--star-muted` | `--star-surface-1` | 4.5 | 8.56 | 8.56 |
| toast (`stellar-ui.css`) | text | `--star-text` | `--star-surface-3` | 4.5 | 13.68 | 13.68 |
| image-dialog (`stellar-ui.css`) | text | `--star-muted` | `--star-surface-1` | 4.5 | 8.56 | 8.56 |
| close-button (`stellar-ui.css`) | text | `--star-text` | `--star-surface-3` | 4.5 | 13.68 | 13.68 |
| primary-button (`stellar-ui.css`) | text | `--star-on-gold` | `--star-gold` | 4.5 | 10.63 | 10.63 |
| secondary-button (`stellar-ui.css`) | text | `--star-body` | `--star-surface-2` | 4.5 | 12.60 | 12.60 |
| secondary-hover (`stellar-ui.css`) | text | `--star-text` | `--star-surface-3` | 4.5 | 13.68 | 13.68 |
| tool-icon (`stellar-ui.css`) | text | `--star-gold-soft` | `--star-surface-3` | 4.5 | 5.45 | 5.45 |
| tag (`stellar-ui.css`) | text | `--star-muted` | `--star-surface-2` | 4.5 | 7.98 | 7.98 |
| tag-success (`stellar-ui.css`) | text | `--star-success` | `--star-success-wash` over `--star-surface-2` | 4.5 | 7.82 | 7.82 |
| tag-gold (`stellar-ui.css`) | text | `--star-gold` | `--star-gold-wash` over `--star-surface-2` | 4.5 | 7.96 | 7.96 |
| tag-error (`stellar-ui.css`) | text | `--star-danger` | `--star-danger-wash` over `--star-surface-2` | 4.5 | 6.97 | 6.97 |
| workflow-picker (`stellar-ui.css`) | text | `--star-body` | `--star-surface-2` | 4.5 | 12.60 | 12.60 |
| health-result (`stellar-ui.css`) | text | `--star-body` | `--star-success-wash` over `--star-surface-2` | 4.5 | 9.63 | 9.63 |
| integrated-panel (`stellar-ui.css`) | text | `--star-body` | `--star-surface-1` | 4.5 | 13.51 | 13.51 |
| rename-field (`redesign.css`) | text | `--star-text` | `--star-surface-2` | 4.5 | 15.20 | 15.20 |
| undo-toast (`redesign.css`) | text | `--star-body` | `--star-surface-3` | 4.5 | 11.33 | 11.33 |
| undo-action (`redesign.css`) | text | `--star-gold` | `--star-surface-1` | 4.5 | 10.50 | 10.50 |
| consent-dialog (`redesign.css`) | text | `--star-body` | `--star-surface-2` | 4.5 | 12.60 | 12.60 |
| consent-button (`redesign.css`) | text | `--star-text` | `--star-surface-3` | 4.5 | 13.68 | 13.68 |
| consent-primary (`redesign.css`) | text | `--star-on-gold` | `--star-gold` | 4.5 | 10.63 | 10.63 |
| voice-chosen (`settings-ui.css`) | text | `--star-gold` | `--star-gold-wash` over `--star-surface-2` | 4.5 | 7.96 | 7.96 |
| studio-rule (`settings-ui.css`) | text | `--star-muted` | `--star-surface-2` | 4.5 | 7.98 | 7.98 |
| dock-banner (`chat.css`) | text | `--star-muted` | `--star-surface-1` | 4.5 | 8.56 | 8.56 |
| chat-jump (`chat.css`) | text | `--star-text` | `--star-surface-3` | 4.5 | 13.68 | 13.68 |
| starter (`chat.css`) | text | `--star-muted` | `--star-surface-1` | 4.5 | 8.56 | 8.56 |
| file-chip (`chat.css`) | text | `--star-body` | `--star-surface-3` | 4.5 | 11.33 | 11.33 |
| send (`chat.css`) | text | `--star-on-gold` | `--star-gold` | 4.5 | 10.63 | 10.63 |
| send-disabled (`chat.css`) | text | `--star-faint` | `--star-surface-3` | 4.5 | 4.52 | 4.52 |
| message (`chat.css`) | text | `--star-text` | `--star-surface-2` | 4.5 | 15.20 | 15.20 |
| correction-input (`chat.css`) | text | `--star-text` | `--star-surface-1` | 4.5 | 16.31 | 16.31 |
| rail-search-border (`stellar-ui.css`) | border | `--star-stroke-control` | `--star-surface-1` | 3.0 | 1.33 | 3.82 |
| topbar-search-border (`stellar-ui.css`) | border | `--star-stroke-control` | `--star-surface-1` | 3.0 | 1.33 | 3.82 |
| secondary-border (`stellar-ui.css`) | border | `--star-stroke-control` | `--star-surface-2` | 3.0 | 1.24 | 3.56 |
| workflow-border (`stellar-ui.css`) | border | `--star-stroke-control` | `--star-surface-2` | 3.0 | 1.24 | 3.56 |
| composer-border (`chat.css`) | border | `--star-stroke-control` | `--star-surface-2` | 3.0 | 1.24 | 3.56 |
| correction-border (`chat.css`) | border | `--star-stroke-control` | `--star-surface-1` | 3.0 | 1.33 | 3.82 |
| jump-border (`chat.css`) | border | `--star-stroke-control` | `--star-surface-3` | 3.0 | 1.45 | 3.21 |
| composer-focus (`chat.css`) | focus | `--star-stroke-focus` | `--star-surface-2` | 3.0 | 2.70 | 7.63 |
| menu-focus (`redesign.css`) | focus | `--star-stroke-focus` | `--star-surface-3` | 3.0 | 2.43 | 6.86 |
| rename-gold-line (`redesign.css`) | border | `--star-gold-line` | `--star-surface-2` | 3.0 | 3.04 | 3.04 |

## Minimal corrective changes

- Added `--star-stroke-control: #6b747d`; only seven functional
  control borders now use it instead of dim decorative strokes
  (`--star-stroke` / `--star-stroke-strong`). Existing dividers
  and brand colours are unchanged.
- Lightened `--star-stroke-focus` from `#59616a` to `#a7afb7`
  for the composer border and menu focus affordance (see before/after rows).
  It must stay brighter than `--star-stroke-control` (2.14:1 against it): the
  composer's resting edge now uses the control stroke, and its focus is shown
  only by the edge colour, so equal tokens would hide focus entirely.
- The `--star-faint` text on the raised third surface still clears
  4.5:1 (smallest text margin); no unnecessary palette change.
- Color-only contrast does not establish keyboard accessibility, icon
  distinguishability under animations, or runtime browser rendering.
  The separate control-names / focus task covers keyboard operation.

A deterministic mutation test replaces the real muted token with an
intentionally low-contrast value and proves that the gate detects it.
No installed renderer, browser screenshot sampling or human contrast
perception test is claimed.
