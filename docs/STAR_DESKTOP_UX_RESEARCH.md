# STAR Intelligence — OLED Desktop Design Research & Implementation (October 2026)

## Product objective

A friendly, *real working* AI development application should feel less like a control panel for an inference server and more like a creative game-development workspace. STAR remains deliberately local-first, honest about limitations, and controllable by the user. This v0.6.0 redesign changes hierarchy, messages, keyboard flow, actual analytics, motion and public release architecture—not merely the color palette.

## Studied primary references and specific lessons

1. **Linear, “A calmer interface for a product in motion” (March 2026)** — https://linear.app/now/behind-the-latest-design-refresh. The design team identifies accumulated interface clutter, overly prominent sidebars, inconsistent headers and crowded control bars. They reduce competition for attention and move toward warmer, more neutral grays. **Applied:** STAR's sidebar is a quiet `#0C0E11`, content is foregrounded `#0F1115`, one header pattern is reused, and old panels don't all compete at full brightness.

2. **Raycast, “A fresh look and feel”** — https://www.raycast.com/blog/a-fresh-look-and-feel. Raycast concentrates actions around primary user input and keeps navigation fast to scan, with legible icons and a recognizable action area. **Applied:** STAR's message composer is primary; the sidebar groups tools, tool actions are named, and Ctrl+Enter sends a message without reaching for the mouse.

3. **Microsoft Fluent 2, Layout** — https://fluent2.microsoft.design/layout. A four-pixel spacing rhythm and visible grouping are more coherent than arbitrary whitespace. **Applied:** token scale 4/8/12/16/20/24/32/40/48; compact, uniform cards; predictable sidebar and topbar positioning. Empty space establishes content hierarchy rather than drawing every surface with a border.

4. **Microsoft Fluent 2, Typography** — https://fluent2.microsoft.design/typography. Use Segoe UI Variable, logical heading tiers, sentence case and measured text contrast. **Applied:** 11–12 px supportive labels, 13–14 px body content, 21 px page headings, 27 px greeting; medium-weight navigation and generous line wrapping. Message content is selectable and can be copied.

5. **Microsoft Fluent 2, Color** — https://fluent2.microsoft.design/color. Accent color is not the whole interface. Neutrals establish hierarchy; semantic colors represent meaning, not decoration. **Applied:** almost-black canvases, soft near-whites, an actual warm-gold STAR identity `#EFCB70`, green for success and muted red for failures; no electric-yellow frames on every component. Brand gold has 12.1:1 contrast against the canvas; ordinary foreground text has 17.0:1.

6. **Microsoft Fluent 2, Motion** — https://fluent2.microsoft.design/motion. Motion should communicate entry, attention and state changes, never delay a user or flash at them. **Applied:** message fade 180 ms OutCubic, discrete task status changes, passive graph redraws from real values, user-controlled reduced motion, no incessant pulsation in the chat area.

7. **Windows 11 Design Principles** — https://learn.microsoft.com/en-us/windows/apps/design/design-principles. Calm, intuitive, familiar, coherent and adaptable. **Applied:** Windows-native Qt widgets, keyboard accessible controls, familiar editable inputs, consistent navigation, focus strokes. A desktop gaming aesthetic can still behave like a predictable Windows app.

8. **Discord, “Revamped Overlay & Refreshed Desktop” (2025)** — https://discord.com/blog/player-release-q12025. Game-oriented UI benefits from modular widgets, configurable density, OLED-oriented dark themes and centralized important actions. **Applied:** STAR's Analytics is a focused module with separate task trend, operational metrics and activity log. Do not imitate Discord's crowded server grid or paste game decorations onto the app.

9. **Qt for Python, QGraphicsOpacityEffect / QPropertyAnimation / QPainter** — https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsOpacityEffect.html, https://doc.qt.io/qtforpython-6/PySide6/QtCore/QPropertyAnimation.html, https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPainter.html. Native Qt can produce meaningful fades and crisp antialiased charts without web rendering dependencies. **Applied:** actual `QPropertyAnimation`, native `QPainter` task chart, `QSvgRenderer` for source-defined icons rather than random emoji.

## Interaction architecture

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│ ✦ STAR       │ Chat with STAR                                  v0.6.0     │
│              ├─────────────────────────────────────────────────────────────┤
│ Chat         │ [Empty state only: What are we building today?]           │
│ Analytics    │                                                             │
│ Projects     │ STAR messages — readable, copyable, calm                   │
│ Roblox Studio│ You — compact right-aligned message                        │
│ Image Lab    │                                                             │
│ STAR Brain   │                                                             │
│ Settings     │ [ Attach ] [ Voice ] [ Read aloud ]          [ Send → ]     │
│              │ Task status, actual events                                  │
│ Project      │                                                             │
│ Set up Brain │                                                             │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

Critical decisions: 
- The large opening greeting disappears once a meaningful conversation starts. Returning to old conversations doesn't waste screen space on a repeated hero.
- Assistant messages no longer live in saturated, thick-outlined colored cards. User messages are subtly distinct.
- Copy always copies actual message text. No decorative inactive controls.
- Settings and model tooling remain accessible but secondary.
- When a user sends a request, the app displays progress from real events. Task errors are visible and stored; no fake tool runs or loading illusions.
- The graphical dashboard is backed by on-device SQLite event records scoped to a project. Each chart tracks real daily task starts; successful/failed counts are distinct; median duration exists only when completion timings were recorded.
- A fresh install displays a clear empty state, **not fabricated analytics**.

## Motion and accessibility requirements

| Event | Pattern | Duration | Keyboard and reduced-motion behavior |
|---|---|---|---|
| New message | Fade in, no slide across screen | 180ms | Disabled with Reduce motion |
| Nav hover | Native button color shift | Immediate | Visible keyboard focus outline |
| Active agent task | Text status changes based on real tool events | Subtle timer | No repeating dot animation with Reduce motion |
| Chart update | QPainter repaint, true observed samples | Immediate | Chart has an accessible name and accompanying metric cards and event list |
| Error | Static explanation + relevant action | Immediate | No distracting shaking/flashing |

## Analytics schema and claims

- `AnalyticsStore` stores only project name, event type, UTC timestamp, optional elapsed milliseconds and short nonsecret tool/error category. SQLite local path `%APPDATA%\\STAR\\analytics.sqlite3` on Windows.
- User message counts read from the actual conversation database. No prompts, images, access tokens, file contents, hardware fingerprint or tool response payload are stored in analytics.
- Daily chart displays the previous 14 days of **run_started**. A day with no observations is drawn as zero; if there is no series it explicitly says so.
- `run_succeeded` and `run_failed` come from task execution; tool acceptance/rejection is separately counted.
- Do not claim current GPU usage or VRAM consumption unless reliably queried from the machine. Future optional GPU panel can use `nvidia-smi` with a timeout and unavailable fallback.
- Future benchmarks must distinguish text tokens/sec and task acceptance rates, with measured sample sizes and test hardware.

## Visual QA matrix for Windows runner

The CI build runs `scripts/capture_desktop_ui.py` to collect four **real Qt application screenshot** images: chat and analytics/Brain at 1440×900 plus chat at 1050×680. The screenshots contain empty-state offline UI with no model running; they do **not** prove local model or Roblox performance.

Human review checklist: 
- No text overlaps icons, separators or labels.
- Sidebar width remains stable; chat controls don't get clipped at 1050×680.
- Main content must dominate, not the navigation.
- Gold remains a limited, readable action accent; no bright neon or unnecessary effects.
- Chart labels are clear, and zero data is not accidentally drawn as success.
- Keyboard focus and Ctrl+Enter work; reduced motion is available.
- A real Windows 125% and 150% scaling check is still required before final polish claims.

## Planned usability improvements after v0.6

A nonblocking streaming assistant response; first-run model downloader diagnostics; cancel/retry download button; fully custom text/code rendering; optional compact/spacious density; sidebar collapse; keyboard command palette; project-level activity filtering; HTML-free charts that can be exported to CSV; measured VRAM/CPU snapshots. None should be called implemented before code and tests exist.

## Success criteria (rather than “AI-looking” subjective scores)

1. Users can locate the Chat field and start a task without understanding a model server.
2. The navigation and selected state are consistent across all seven pages.
3. Long answers wrap without truncating, using readable foreground contrast.
4. The Analytics page uses only actual local information and shows honest zero states.
5. Every UI action is wired to a real callback or disabled with explanation.
6. Windows runner captures offscreen Qt renders; an actual Windows computer validates appearance and accessibility.
7. The next real user screenshot is compared against approved layout references, not blindly rebuilt from vague aesthetics.
