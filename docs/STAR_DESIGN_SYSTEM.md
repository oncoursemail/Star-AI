# STAR — OLED v0.6 Design System

This version replaces the earlier multi-gradient gold-gray palette with a coherent OLED-neutral system informed by [Linear's 2026 design refresh](https://linear.app/now/behind-the-latest-design-refresh), [Microsoft Fluent 2](https://fluent2.microsoft.design), and [Discord's desktop game-overlay approach](https://discord.com/blog/player-release-q12025).

**Design tokens are executable** in [`star/design_system.py`](../star/design_system.py). Do not scatter new accent values through widgets.

| Semantic role | Value |
|---|---|
| App black | `#08090B` |
| Quiet sidebar | `#0C0E11` |
| Work canvas | `#0F1115` |
| Surface | `#16191E` |
| Dividers | `#2B3037` |
| Primary text | `#F2F3F4` |
| Secondary text | `#A0A8B3` |
| STAR warm gold | `#EFCB70` |
| Gold primary button text | `#1B1913` |
| Success semantic | `#81C7A3` |
| Failure semantic | `#EB9A97` |

Only important controls, selected navigation and the STAR mark use gold. No full-screen colored gradients, arbitrary spheres, glowing UI rings, emoji icons, or gradients on every button.

Font family: Segoe UI Variable -> Segoe UI fallback. Regular body 14px; supporting text 11–12; headings 21/27. Native SVG icon paths from `star/visuals.py`, 16–22px, consistent stroke. Spacing grid follows 4px increments. Buttons: 8px corner radius; panels: 11–12; input: 8. Message fades 180ms, with a Reduce motion option.

**Read the detailed design research:** [`STAR_DESKTOP_UX_RESEARCH.md`](STAR_DESKTOP_UX_RESEARCH.md).
