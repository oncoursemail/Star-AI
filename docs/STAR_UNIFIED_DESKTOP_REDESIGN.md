# STAR Intelligence — Unified Stellar Desktop

Status: feature branch / review candidate. Do not advertise a shipped Windows executable until CI, real Windows GPU/model checks and owner acceptance pass.

## Diagnosis from the owner's October 2026 screenshots

- React desktop and legacy PySide6 desktop expose distinct navigation and styling. The old React Library image action opens the legacy executable, creating an unexpected second STAR window.
- The chat store historically keyed all turns to a project, not independent chat threads, so New Chat could not isolate conversations.
- Conversation rows were separated by heavy full-width borders. Type and composer appeared small and repetitive status badges competed for attention.

## Research and design decisions

- Creative Tim Vision UI Dashboard React: https://demos.creative-tim.com/vision-ui-dashboard-react/#/dashboard — use layered dark surfaces, navigation hierarchy and subtle tonal changes, not copied dashboard components or invented analytics.
- Aceternity UI: https://ui.aceternity.com/components — take contextual hover, entrance motion and tactile buttons while avoiding continuous glowing backgrounds, GPU-heavy effects and decorative noise.
- HeroUI: https://heroui.com/ — adopt consistent form focus states and accessibility principles, but don't add a second heavyweight React component framework alongside STAR's Radix controls and custom CSS.
- Chakra UI: https://chakra-ui.com/ — consistent readable typography, spacing and component states. Avoid mixing Chakra, HeroUI and other competing design foundations in the same app.
- Supernova comparison: https://www.supernova.io/blog/top-10-pre-built-react-frontend-ui-libraries-for-2025 — select a single owned design system; component libraries and effect libraries serve different purposes.
- Motion accessibility: https://motion.dev/docs/react-accessibility — respect reduced motion and avoid movement that interrupts reading.

## Architecture

1. Keep the primary Windows launch path as React + Qt WebEngine with the existing restricted QWebChannel. Do not introduce a second standalone desktop frontend.
2. Use frontend/src/stellar-ui.css as a narrowly scoped, STAR-owned dark theme overlay. Background is obsidian/navy; accent is restrained warm gold. All sections share navigation, typography, field focus, surface and motion treatments.
3. The conversation is the primary view: unboxed assistant answers, right-aligned user bubbles, readable Markdown, code copy and no horizontal line per message. The multiline composer autosizes and stays docked; near-bottom scroll follows generation while manually scrolled readers are not yanked away.
4. Persist real threads in project-scoped SQLite chats/active_chats tables. Add chat_id to the legacy message table defaulting to legacy. Old message content, timestamps, model paths and project storage are retained.
5. Thread switching is blocked while a model request runs; each completion stays with its originating thread. Model recent turn context is filtered by thread. Reviewed project knowledge/memory remains project scoped (not chat isolated).
6. Image Lab lives inside React and invokes the existing allowlisted local ComfyUI generator through the explicit Python bridge. Pick an approved API-format workflow from a native file dialog, validate node ID and loopback port and save outputs under the STAR profile. The legacy UI can still be manually invoked with --legacy-ui only for recovery.
7. Keep credentials, file access, inference endpoints, downloads and privileged actions on the Python side. Keep the repo public and leave releases/installers untouched.

## Acceptance criteria

- Python compileall, full pytest, React typecheck, unit tests and production build must pass.
- Existing pre-upgrade SQLite conversations migrate safely, preserve all old rows and show as Previous conversation. Creating/switching threads must survive restarting the application.
- One STAR window throughout the normal workflow, including Image Lab and Library navigation.
- No user messages leak into a different thread's recent-context window. Project-scoped notes remain available by intentional design.
- Chat panel respects keyboard focus, Shift+Enter, empty/error/loading states, long code blocks, natural scroll, reduced-motion setting and constrained window widths.
- Live Windows application confirms working local model responses, correct tool permission checks, model download, ComfyUI workflow result, update/restart behavior and %APPDATA%/STAR user-data persistence.
- Browser screenshots are visual evidence only; they do not substitute for an installed Windows smoke test or user visual approval.

## Release guidance

This branch should first become a reviewed PR. Do not merge it automatically, manufacture green QA or publish a Windows installer until the real environment has been tested.