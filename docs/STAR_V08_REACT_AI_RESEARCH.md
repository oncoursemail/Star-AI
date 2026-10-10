# STAR Intelligence — Genesis v0.8 React + Local AI Research

**Prepared October 2026.** This is an implementation-led research record, not an advertisement. Features are clearly distinguished from future proposals, and CI checks are not mistaken for live Windows/GPU acceptance tests.

## 1. Core design direction: premium, quiet, unusually useful

STAR is an AI creation workspace first, a styled desktop application second. The conversation should occupy the majority of usable space. Context, model health, and safety controls must remain discoverable without covering the content. The visual language borrows *principles* from mature productivity apps such as [Linear](https://linear.app/), [Raycast](https://www.raycast.com/), [VS Code](https://code.visualstudio.com/docs/getstarted/userinterface), [Microsoft Fluent 2](https://fluent2.microsoft.design/), and accessible primitives in [Radix](https://www.radix-ui.com/primitives/docs/overview/accessibility), without cloning any screen.

Observed product patterns worth retaining: (1) clear product and workspace identity, (2) one dominant action per view, (3) subdued navigation, (4) a fast conversation/editor lane, (5) context-specific secondary actions, (6) useful empty states, (7) visible but unobtrusive error recovery, (8) keyboard support for frequent actions. Visual complexity is not proof of engineering quality.

STAR-specific constraints: OLED near-black instead of large glowing gradients; neutral graphite layers rather than a cascade of saturated panels; warm off-white text and limited antique gold for the active state or primary action; cool slate only for supporting metadata; authentic SVG icons; no random decorative spheres, neon edge glows, overlapping controls, generic AI figures or fabricated analytics. System-based typography on Windows avoids an unexpected network font dependency.

### Implemented visual tokens

| Token | Value | Role |
|---|---|---|
| Base canvas | `#090b0e` | True dark with enough separation from chrome |
| Raised surface | `#191d22` | Editor/composer and accessible control targets |
| Border | `#292e33` | Quiet separators, 1 px |
| Text | `#f2f3f0` | Primary, readable foreground |
| Body | `#adb3b6` | Reading and explanatory copy, contrast review required |
| Accent | `#e8bf76` | Selected nav, primary action and verified model focus |
| Positive | `#a9d3b7` | Explicit success in addition to icon/text |

Spacing follows a small scale (4, 8, 12, 16, 24, 32, 48 px) rather than arbitrary per-component values. Main reading text is 14 px with generous line height; compact metadata remains visually secondary but must still pass contrast review. Cards should only exist when they clarify an affordance, not as decoration.

## 2. React architecture — the hooks are not the design

[React: You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect) recommends deriving UI data from state during render instead of redundant synchronization. STAR follows this for filtered chat messages, selected product-tour copy, activity views and settings labels. A React render must not trigger a Qt file operation or inference request.

[React: useEffect](https://react.dev/reference/react/useEffect) defines effects as synchronization with external systems and requires cleanup. Native WebChannel listeners, global keyboard shortcuts and bridge bootstrap are such systems. STAR subscribes to bridge events with an unsubscribe callback and removes window keyboard handlers on unmount. The Qt WebChannel initialization now reuses one promise to avoid duplicate listener registration during development StrictMode cycles.

[React: useTransition](https://react.dev/reference/react/useTransition) allows non-urgent updates to avoid blocking high-priority typing, but explicitly should not control the raw state of a text input. STAR keeps the composer controlled and immediate; future long-history virtualization/search may adopt transitions only after profiling. Do not add every hook because it sounds advanced.

[React: Components and Hooks rules](https://react.dev/reference/rules) imply immutable props, stable keys and hooks at the top level. Current preview tabs use stable keys. Live response segments accumulate into an explicit state entry with a stable message identity. The public website never tries to make native tool calls simply because it shares React components with the desktop.

The production architecture is React 19 + Vite/TypeScript built to static assets, packaged inside Qt WebEngine. Python remains the authority for local files, Studio tool permissions, model HTTP requests, SQLite persistence, checksums, analytics and updates. [Qt WebChannel documentation](https://doc.qt.io/qt-6/qtwebchannel-javascript.html) informs a narrowly typed action/event bridge; there is no exposed arbitrary shell endpoint. `frontend/dist` is a compiled offline presentation layer, not another model server.

## 3. Motion: meaningful, interruptible, inexpensive

[Motion layout animations](https://motion.dev/docs/react-layout-animations) use transforms and `layoutId` for shared selection indicators. STAR keeps a shared selected-track underline, bounded navigation transition and brief view changes; it does not animate large geometry on every frame. [AnimatePresence](https://motion.dev/docs/react-animate-presence) is appropriate for replacing product-tour copy and settings detail without leaving two overlapping panels.

[Motion accessibility](https://motion.dev/docs/react-accessibility) and [MotionConfig](https://motion.dev/docs/react-motion-config) support `reducedMotion='user'` and a stronger `always` policy when the app setting is enabled. STAR's React root honors OS settings; the desktop shell now wraps its state with an additional `MotionConfig`. CSS disables nonessential transitions/loops in `prefers-reduced-motion: reduce`.

[Chrome/web.dev performance guidance](https://web.dev/articles/animations-guide) favors opacity/transform over expensive layout and paint properties. Therefore, do not animate `box-shadow`, width, blur or full-screen filter surfaces on continuous loops. The default site and chat avoid fullscreen glow and background video. Button hover effects are short (~150–200ms), product-tour text ~180ms, page entrance ~350–550ms. These are starting targets, not proof of measured device smoothness.

Streaming text is throttled at the backend to roughly 75 ms or 90 characters per event. This avoids rendering Markdown on every generated token or saturating Qt signals. Internal reasoning-content fields are never treated as user-facing assistant text. The active model progress state remains visible without pretending to show token-per-second measurements.

## 4. Accessibility and interaction contracts

[WCAG 2.2 minimum contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum) asks for 4.5:1 normal text and 3:1 large text, with exceptions. Review actual rendered pairs instead of assuming a gold color means sufficient contrast. The app uses visible focus outlines, text-plus-icon health statuses, accessible labels for image/file actions and touch-friendly controls where possible.

[WAI-ARIA tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) require `tablist`, `tab`, `tabpanel`, `aria-selected`, proper labeling and arrow-key navigation. STAR's product tour now implements Arrow Up/Down/Left/Right and Home/End, a single tabbable active selection and explicit panel IDs. Generic interactive concepts use pressed buttons rather than incorrect tab semantics.

Chat interaction requirements: Enter sends; Shift+Enter inserts a line break; Ctrl/Cmd+K focuses the composer; Ctrl/Cmd+, opens Settings; Escape dismisses temporary UI. Search and copy are explicit controls. Local engine activity should be announced through `role='status'` without blocking text entry. A rejected model request must show actionable recovery and preserve the original user message; never erase the existing chat database for an upgrade.

## 5. Backend diagnosis: the Qwen HTTP 500

The exact screenshot traceback references a Jinja exception at line 85 saying **System message must be at the beginning**. This is independently documented for Qwen3.5 and later strict templates; see [llama.cpp issue #20733](https://github.com/ggml-org/llama.cpp/issues/20733) and [llama.cpp discussion #27281](https://github.com/ggml-org/llama.cpp/discussions/27281). It is not a CSS or React rendering error.

Before the fix, `star/agent.py` emitted two adjacent `system` chat messages. A later compaction also inserted an additional system turn. Strict Qwen templates only accept the system turn at message index 0, so the engine rejected the payload before generation. `make_system_message` consolidates instructions and bounded project notes into one first message. `validate_model_roles` fails locally before an invalid payload reaches llama-server, and the memory-compaction path rebuilds exactly one first system turn.

The local runtime uses the OpenAI-compatible [llama.cpp chat completion endpoint](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Jinja is explicitly enabled for tool-compatible templates. Unit tests now record all outbound chat requests and assert one system role at index zero, including after compaction. A separate health probe posts a real short chat to the loopback model; GET `/models` alone cannot establish a working chatbot.

Engine startup waits for a real completion before claiming the brain is ready. Failed requests receive user-actionable errors rather than exposing long Jinja source text. These are source-level and simulated-client regressions: successful GPU inference must still be verified on an actual Windows PC with the pinned model and projector.

## 6. Conversation UX: stream, recover, copy, inspect

STAR's backend emits streamed `assistant_delta` events **only for simple chats without tool definitions**, preserving complete structured tool-call responses for Studio/workspace operations. Events are bounded and throttled. The React UI displays a partial assistant message labeled Writing and replaces it with the final persisted answer on completion. If a model server rejects streaming with HTTP 400/422/501 before sending any text, STAR retries that request once as a standard completion. No automatic replay occurs after a partially generated stream.

The chat top line provides project identity, search within loaded messages, copy transcript, and a route to model controls. Code fences receive their own copy button and correct horizontal scrolling. Markdown links permit safe protocols only, and remote Markdown images are not loaded automatically. The composer retains attachments selected through the native approved-file picker, rather than allowing arbitrary browser-side paths.

Critical truthfulness: previews are explicitly read-only; activity is not fabricated; live model status comes from the Python runtime; local chat history remains in `%APPDATA%/STAR/conversations.sqlite3`. Streaming does not imply an internet connection or hosted LLM. Project and Studio capabilities still depend on connected, authorized tools.

## 7. Website research and execution

The old STAR homepage had a strong basic headline but the hero was dominated by decorative circles, which added little task comprehension. The new design uses a large, clean editorial headline, clear Windows CTA, restrained typography, and an interactive **illustrative workflow** (clearly labeled not a live AI session). The deeper product section embeds a **real running React interface** in `?preview=1&tab=...` mode, rather than a fake screenshot of successful AI messages.

The tour switches among Conversation, STAR Brain, Developer Tools and Real Analytics. Its iframe is same-origin static presentation: it has no Qt WebChannel, no models, no personal files and no privileged tools. Real releases are linked to the official public GitHub page. No marketing copy pretends that passing frontend CI proves a frontier foundation model or automated AAA game production.

[Vite relative base](https://vite.dev/guide/build#public-base-path) allows both the GitHub Pages project subpath and local bundled file URLs. [GitHub Pages Actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) can deploy the Vite bundle, but the repository owner must enable Pages first. If Pages deployment returns 404 while the site build succeeds, the site is **not live**. Do not report it as published.

## 8. Quality gates for the next candidate

| Gate | Automated evidence | Still requires human/device QA |
|---|---|---|
| Strict Qwen roles | Unit tests including compaction and tool reply | Real pinned Qwen3.5 model on Windows |
| Local AI responsiveness | Fake-client real-chat probe and streaming regressions | Inference speed, GPU/Vulkan, vision projector |
| Frontend syntax and dependencies | TypeScript, Vitest and Vite production build | Interaction/perf profiling in Qt WebEngine |
| Site presentation | Headless Chrome screenshots on PR artifacts | Human visual review at 100/125/150% and narrow layouts |
| Data retention | SQLite migration/unit and installer fixture guards | Actual upgrade from v0.6.1 preserving all files |
| Installer quality | Windows PyInstaller and Inno Setup artifact checks | User-install and self-updater restart on Windows 11 |
| Public deployment | Pages artifact and workflow status | Owner must enable Pages; HTTP site verification |
| Roblox edit quality | Allowed-tool authorization tests | Real unpublished Studio fixture, screenshots and undo |

Suggested visual QA viewports: 1440×900, 1280×800, 1050×680, 390×844 browser; Windows 100%, 125%, 150% scaling. Verify labels never overlap icons, keyboard focus remains visible, code fences scroll, the send button is reachable, buttons represent real actions, empty analytics are honest, and reduced-motion mode removes nonessential movement.

## 9. Deliberately not claimed as done

Persistent multi-thread chat history within one project, real token streaming during multi-tool execution, live model download cancellation, GPU and frame-accurate UI profiling, signed desktop installers, guaranteed Roblox asset quality, autonomous publication, and a newly trained foundation model are **not** implemented by this UI work. They require further scoped engineering and verification. The v0.8 acceptance checklist documents release conditions separately.

## Reference index

**Core:** [React](https://react.dev/) · [React effects](https://react.dev/reference/react/useEffect) · [derived state](https://react.dev/learn/you-might-not-need-an-effect) · [React transitions](https://react.dev/reference/react/useTransition) · [Vite](https://vite.dev/guide/) · [Qt WebChannel](https://doc.qt.io/qt-6/qtwebchannel-javascript.html).

**Interaction:** [Motion layout](https://motion.dev/docs/react-layout-animations) · [AnimatePresence](https://motion.dev/docs/react-animate-presence) · [reduced motion](https://motion.dev/docs/react-accessibility) · [Fluent 2](https://fluent2.microsoft.design/) · [W3C tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) · [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum) · [web performance](https://web.dev/articles/animations-guide) · [Radix](https://www.radix-ui.com/primitives/docs/overview/accessibility).

**Model/distribution:** [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [llama.cpp strict-template issue](https://github.com/ggml-org/llama.cpp/issues/20733) · [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).