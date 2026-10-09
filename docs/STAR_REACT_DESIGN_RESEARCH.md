# STAR Intelligence — React interface & interaction research

**Engineering snapshot:** October 2026. The claims in this report distinguish design principles, implemented code, and features still requiring real Windows testing.

## Objective and scope

STAR has evolved from a Python/PySide desktop utility into an AI development workspace. The goal is **not** maximal decorative complexity. We want the restraint and information hierarchy associated with excellent developer tools, but with enough warmth, personality and tactile motion to make STAR recognizable.

Our usability priorities:

1. **Clarity at a glance.** The current project, current model state, current activity and version should be visible without sending a message.
2. **The conversation is the canvas.** Give readable messages generous space. Controls should recede until needed. Avoid narrow chat columns blocked by giant cards.
3. **Approachable entry.** A new user should be able to start from a single screen and attach an image without understanding model-server ports or quantization terminology.
4. **Real status, not decorative diagnostics.** Analytics must come from local SQLite events. Empty counters are more honest than sample data.
5. **Small, meaningful motion.** Animate enter/exit and feedback states; do not add distracting permanent particles, neon, or excessive parallax.
6. **Native capability, careful boundary.** React must not gain unbounded operating-system access. Tool calls go through an audited Python bridge with explicit operation names and scopes.
7. **One shared design language.** The public React website uses exactly the same color, typography and icon directions as the desktop shell.

## Primary research and the engineering decisions it informed

### React documentation

- **[React installation and gradual adoption](https://react.dev/learn/installation):** React is appropriate for progressively replacing a Qt Widgets interface; a complete rewrite of STAR's Python AI core is unnecessary.
- **[React escape hatches](https://react.dev/learn/escape-hatches)** and **[useEffect](https://react.dev/reference/react/useEffect):** External systems (including the Qt WebChannel) belong at synchronization boundaries. Render state is kept in React; native access remains inside the host application. The bridge subscribes once, cleans subscriptions on unmount and sends JSON protocol events.
- **[Avoid unnecessary effects](https://react.dev/learn/you-might-not-need-an-effect):** Derived UI such as activity totals, session labels, success percentages and disabled buttons is computed directly from state where practical.

### Vite and deployment

- **[Vite relative base path](https://vite.dev/guide/build#relative-base):** STAR's Vite build uses `base: './'` so its static JavaScript and styles can load both from a GitHub Pages project path and Qt's local `file://` application bundle.
- **[GitHub Pages custom Actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)** and **[configuring Pages source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site):** The Pages workflow builds the Vite site on a GitHub-hosted runner and deploys an artifact with short-lived OIDC credentials. Repository owner must ensure GitHub Pages source is set to **GitHub Actions**.

### Motion, visual rhythm and accessibility

- **[Motion for React](https://motion.dev/docs/react):** Motion should handle important component enter/exit and high-value microinteractions. Simple hover colors and focus rings remain CSS transitions; no unnecessary JavaScript animation loops.
- **[Motion layout transitions](https://motion.dev/docs/react-layout-animations):** Shared active-tab and navigation transitions should use layout animation with interruptible transforms rather than reflow-heavy animated widths/positions.
- **[Reduced motion](https://motion.dev/docs/react-accessibility):** `MotionConfig reducedMotion="user"` and CSS `prefers-reduced-motion` suppress nonessential transforms. Avoid autoplay video and ambient 3D motion.
- **[W3C text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum):** Use at least 4.5:1 for ordinary text; UI surfaces use non-color cues and visible focus treatments.
- **[W3C CSS reduced-motion technique](https://www.w3.org/WAI/WCAG22/Techniques/css/C39.html):** Provide simple fallbacks so the interface works when system animation preferences request minimal movement.

### Native interoperability

- **[Qt WebChannel JavaScript API](https://doc.qt.io/qt-6/qtwebchannel-javascript.html):** Qt WebEngine can load the bundled `qrc:///qtwebchannel/qwebchannel.js` module and expose a narrowly scoped QObject bridge. No local HTTP daemon is needed solely to host the interface. The model requests remain in Python, not in browser-side code.
- **[Qt WebChannel architecture](https://doc.qt.io/qt-6/qtwebchannel-index.html):** Signals provide task, model-download and update progress. Slots return typed JSON results. Native filesystem and Studio access never become direct JavaScript privileges.

## Competitive design analysis

The patterns worth learning are **observable principles**, not pixel-copying other products:

- **Modern productivity applications:** compact navigation, easy-to-scan hierarchy, keyboard-first search and low-contrast dividers. Primary work stays visually dominant over chrome.
- **Developer tools:** present active project, tasks, file scope and diagnostics in a predictable place. Error messages need next actions, not stack traces displayed by default.
- **Game-feeling microinteractions:** successful UI feels tactile with controlled press/hovers, slight inertia on state transitions and occasional branded motion; it does not require distracting fantasy graphics.
- **Conversation applications:** prose stays legible in a moderate width, with code blocks scrollable in-line, clean attachments, available copy controls and a sticky composer.
- **Analytics:** graphs need clear units, time windows, honest zero states, and local/source context. A fake chart erodes trust even if it looks good.

## STAR v0.7 React design system

| Token | Value | Use |
|---|---|---|
| Canvas | `#090A0C` | OLED-inspired near-black base |
| Sidebar | `#101114` | Navigation elevation |
| Surface | `#131519` | Workspace cards |
| Raised surface | `#191C21` | Composer, focused layers |
| Border | `#292C32` | One-pixel separators |
| Primary text | `#F3F1EC` | Headlines and important labels |
| Body text | `#D6D6D4` | Reading surfaces |
| Secondary text | `#898D94` | Metadata (review contrast before shipping) |
| Accent | `#F1BF62` | STAR, selected states, primary CTA |
| Safety green | `#8DB9A6` | Confirmed local/ready state |

### Type and spacing

- Favor **Segoe UI Variable** and system-native fonts for the packaged Windows app. Public site can add licensed self-hosted fonts later; STAR Desktop does not silently fetch Google Fonts.
- Use `Space Grotesk` only as an optional heading enhancement; system fallbacks remain acceptable.
- Normal text size 12–14 px in compact desktop controls, with 13–15 px for chat body; 1.65–1.85 line-height for actual responses. This is a first-pass implementation requiring native DPI review.
- Four/five levels of density: micros and metadata, controls, reading text, page headings, hero heading. Keep all labels consistent.
- 8/12/16/24/32 px scale; avoid arbitrary icon sizes and cards with no meaning.

### Motion tokens

- 140–200 ms for hover/focus; 180–240 ms for message entrance; ~180 ms for tab transitions; avoid looping effects in the main reading area.
- Feedback is state-driven: working model gets an activity indicator, verified download gets a progress bar, and failed operations get an actionable toast.
- Prefer opacity/transform animation over paint-heavy filters and large blur animations. Respect `prefers-reduced-motion`.

## Implemented architecture

```
frontend/ (React + TypeScript + Vite)
  src/views/Landing.tsx       public marketing site
  src/views/StudioApp.tsx     React desktop workspace and public preview
  src/lib/bridge.ts          typed Qt WebChannel boundary and preview handling
  src/styles.css             design tokens, components and responsiveness
        |
        | Qt WebChannel (JSON commands + JSON signals, local file bundle)
        v
star/react_shell.py         explicit native bridge allowlist
        |
        +-- star/desktop_core.py    chat, settings, model execution
        +-- star/brain_setup.py     verified local engine/model install
        +-- star/studio.py          Roblox Studio MCP discovery
        +-- star/analytics.py       actual SQLite activity/trend data
        +-- star/updates.py         verified public Releases updates
```

### Explicit bridge command allowlist

`bootstrap`, `switchProject`, `pickFiles`, `sendMessage`, `saveSettings`, `installBrain`, `startBrain`, `listModels`, `discoverStudio`, `checkUpdates`, `installUpdate`, `transcribe`, `openDataFolder`, and `copyText`, following the exact allowlist in `star/react_shell.py`. **There is no arbitrary shell command or filesystem read endpoint in React.** Source/model operations remain inside the existing Python policy and resource controls.

### Lifecycle

The desktop shell loads `frontend/dist/index.html?desktop=1`. The webpage sees the Qt WebChannel transport and registers a bounded bridge. `?demo=1` on the public site renders the same interface but **does not fabricate AI responses, analytics, model state or tool actions**. The homepage is the default path.

Chat messages continue in `%APPDATA%\STAR\conversations.sqlite3`; model installations, checkpoints, project memories and task logs remain in their original locations. This migration changes presentation, not the user's stored data format.

### Packaging / verification

- GitHub Windows CI compiles TypeScript, builds Vite, then packages `frontend/dist` with PyInstaller and Qt WebEngine.
- The `--doctor` command checks that React assets exist inside a packaged executable.
- GitHub Pages CI builds the same frontend and uploads the exact release asset for deployment.
- Python offline tests verify bridge whitelist, settings validation, version consistency and build wiring. TypeScript compile and Windows integration must pass on GitHub before publishing an executable.
- Device QA on Windows should validate 100%, 125% and 150% scaling; 1050×680, 1440×900, and narrow/responsive windows. Use real screenshots of the WebEngine React UI and check that no text overlaps icons or buttons.
- A successful CI `--doctor` check does **not** mean the local model downloader, multimodal AI, Roblox Studio tools or self-updater were tested on the user's GPU.

## Current limitations and prioritized follow-ups

- The current site does not expose local conversation data. A public preview is intentionally a sandbox with no fabricated AI activity.
- The Windows integration needs visual and interaction testing on a real user's display; Qt WebEngine packaging can vary across Windows runner images.
- Model streaming should gain token-by-token events; current backend sends a final response plus tool events.
- Add loading skeletons, better codeblock copy controls, full keyboard shortcuts and virtualized long chat history only after real usability tests establish the need.
- Test accessibility with keyboard-only operation, screen readers, color contrast and reduced motion on Windows; CI static checks are not sufficient.
- GitHub Pages may require a one-time owner setting: **Settings → Pages → Source: GitHub Actions**. Never claim a live page until a deployment succeeds and HTTP content is verified.

**The success criterion is not “modern-looking screenshots.” It is whether someone can use STAR to accomplish an actual task with less friction and fewer errors, while retaining control of their data.**
