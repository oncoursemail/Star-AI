# STAR 0.7 — React OLED Interface Research & Implementation

## What changed

The frontend is now **React 19 + TypeScript + Vite**, with Motion for transitions, Lucide for real SVG icons, Recharts for true local analytics, and GitHub Pages for the public website. STAR's **existing Python backend** remains in place. **Qt WebEngine + Qt WebChannel** hosts the bundled, offline-build React assets in the installable Windows application. `star_desktop.py --legacy-ui` can still launch the prior PySide6 layout as a compatibility fallback. Existing SQLite databases and model files stay in `%APPDATA%/STAR`; this upgrade does not migrate or delete them.

The same React source ships in two modes:
- **Public website:** a real responsive landing page with a marked interface preview and links to the public `Star-AI` Releases. It cannot access local files or models.
- **STAR Desktop:** Qt WebChannel provides explicitly allowlisted Python operations: bootstrap, persistent messages and projects, conversation processing, reference file selection, local model management, Studio discovery, update checks, and truthful analytics. The browser is NOT given arbitrary filesystem, terminal, GitHub tokens or publishing permissions.

## Research conclusions implemented

### 1. Legibility and hierarchy matter more than effects

**References:** [Linear design ethos](https://linear.app/), [Raycast](https://www.raycast.com/), [Microsoft Fluent](https://fluent2.microsoft.design/), [Radix Accessibility](https://www.radix-ui.com/primitives/docs/overview/accessibility).

STAR uses a 250px quiet navigation rail, an OLED-near-black canvas (`#08090a`), consistent 8/12/16/24/32 spacing decisions, limited gold (`#e9bd60`), and a maximum readable chat column. Instead of colored user/assistant *cards*, replies read as a conversation with a subtle role/avatar. Action hierarchy is explicit, labels never overlay icons, and failures are plainly visible. Gold appears on selection and important actions only; no neon or glow-heavy fake intelligence visuals.

### 2. Motion should communicate, not distract

**Primary reference:** [Motion React layout/transitions](https://motion.dev/docs/react-layout-animations) and [MotionConfig reducedMotion](https://motion.dev/docs/react-motion-config). Page arrivals are ~160ms and messages ~200ms, with subtle transforms and opacity. Sidebar selection uses shared-element layout motion; buttons give a restrained hover response. No infinite pulsing outside brief active task status. CSS `prefers-reduced-motion` honors accessibility settings, per [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion).

### 3. Accessible primitives and rendering discipline

**Reference:** [Radix unstyled accessible primitives](https://www.radix-ui.com/primitives), [Lucide for React](https://lucide.dev/guide/react/). Use semantic buttons and labels, `aria-current`, keyboard sending (Enter; Shift+Enter newline), focus rings, visible status, contrast-rich type, explicit tool-state errors, and no unlabelled status-by-color alone. For larger modal functionality, introduce accessible Radix Dialog rather than inventing keyboard traps.

### 4. Analytics must reflect real user behavior

**Reference:** [Recharts](https://recharts.org/) and current backend `star/analytics.py`. Four metrics use SQLite activity events and conversation counts for the current project, with 14-day area chart when events exist. Fresh installs get *empty states*, not fake graphs. The graph is read-only and cannot submit model instructions; domain calculations are backend-owned. Metrics show run counts and median wall-clock duration, not fabricated token usage or GPU claims.

### 5. React and Qt can coexist without recreating the model stack

**Primary documentation:** [PySide6 Qt WebChannel](https://doc.qt.io/qtforpython-6/PySide6/QtWebChannel/index.html), [Qt WebChannel JavaScript API](https://doc.qt.io/qtforpython-6/overviews/qtwebchannel-javascript.html), [QWebEngineView](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/QWebEngineView.html).

React is built into static assets in `frontend/dist/`, packaged into Windows by PyInstaller. The Python `QObject` bridge exports a SINGLE validated `invoke` method, with an allowlist of actions and JSON results/events. Heavy operations run in bounded workers and send progress asynchronously. Only the bundled local SPA may load in the internal web view; trusted external documentation opens in the user's browser. Model and tool inputs are never executed as arbitrary Qt scripts. This is an incremental migration; it is **not yet a full Tauri rewrite**.

### 6. Public GitHub Pages and a reusable website

**Primary reference:** [Vite GitHub Pages deployment](https://vite.dev/guide/static-deploy.html). Vite is built with `base: './'`, so files work from GitHub Pages' `/Star-AI/` subpath and local Qt file URLs. The website Actions workflow builds, tests and uploads the public bundle; it deploys using Pages on pushes unless the owner sets `STAR_DEPLOY_PAGES=false`. If the GitHub Pages site is not configured, go to **Repository Settings → Pages → Build and deployment → Source: GitHub Actions**. A completed website build is not proof that the site is live; verify the published URL.

## Next QA requirements

1. Run the Windows build and verify that `STAR.exe` launches the **React UI** (not the legacy Qt UI), with QWebChannel able to access project history and analytics.
2. Test first-run model download and screenshots on the user's RTX 3060 Ti (8 GB VRAM), including loading vision input and cancellation.
3. Test screen sizes 1050×680, 1440×900, and Windows 125%/150% scale: buttons, text, chat scrolling, modal focus, and correct icons.
4. Verify that a public browser opening the website cannot read local conversations or call privileged tools.
5. Enable Pages if needed, verify the live `https://oncoursemail.github.io/Star-AI/` route, and test anonymous Release download.
6. Future work: accessibility-reviewed dialogs, model download manager and resumable download UI, event streaming per tool step, approved image preview and separate animation studio.

STAR's model capacity has not magically increased from a UI framework change. This release is about the **quality, usability, integration and reliability** of the product.
