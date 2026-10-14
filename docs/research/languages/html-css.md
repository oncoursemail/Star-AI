# HTML and CSS for STAR (research, checked 2026-10-13)

Status: Baseline data read from the web-features / webstatus.dev API on 2026-10-13 [1][2]. Verified in that data: cascade layers, nesting, `:has()`, size container queries, subgrid, `color-mix()` and Oklab/OkLCh are **Baseline widely available**. `<dialog>` is widely available. Popover, invoker commands (`command`/`commandfor`), `<details name>`, `@scope`, container style queries, same-document view transitions, `field-sizing`, `text-wrap: balance`, `light-dark()`, `@starting-style` and `transition-behavior` are **Baseline newly available**. Scroll-driven animations, cross-document view transitions, `if()`, `@function`, `interpolate-size`, interest invokers, customizable `<select>`, `reading-flow` and `corner-shape` are **limited availability**. Anchor positioning: the core properties ship in Chrome/Edge 125, Firefox 147 and Safari 26 [3][4], but webstatus.dev still lists the whole feature group as "limited" because some sub-features are incomplete; treat the core as usable with a fallback and the extras as progressive enhancement. Exact Firefox version numbers for features listed as limited are unverified as of 2026-10-13.

HTML has no version number: it is the WHATWG HTML Living Standard [5]. CSS has no "CSS4": it is a set of modules at different levels, and "Baseline" (from the W3C WebDX community group) is the practical compatibility signal [1].

---

## 1. Mental model

- **HTML is a tree of meaning, not of looks.** Every element carries semantics that the browser exposes to the accessibility tree, to search engines, to form submission and to built-in behaviour (focus, keyboard activation, top layer). Pick the element for what it *is* (`<button>` for an action, `<a href>` for navigation, `<dialog>` for a modal, `<nav>`, `<main>`, `<h1>`..`<h6>` in order). A `<div onclick>` is not a button: no focus, no Enter/Space activation, no role.
- **The parser forgives, the DOM does not lie.** The HTML parser repairs bad markup (auto-closes `<p>` before a block, moves stray table content, ignores unknown attributes). What you wrote and what the DOM contains can differ; inspect the DOM, not the source.
- **CSS is declarative constraint resolution.** You do not "run" CSS. For every element and property the browser picks one winning declaration (the cascade), computes a value (inheritance, `var()`, relative units), then layout resolves sizes from constraints (available space, intrinsic content size, flex/grid algorithms). Think "which declaration wins and why", not "which line ran last".
- **Layout is formatting contexts.** Block/inline flow, flex, grid, positioned (absolute/fixed/anchor), multi-column, and table. A child's size depends on its parent's formatting context. Most "my CSS doesn't work" problems are a property that has no effect in the current context (for example `justify-self` in a flex item, `z-index` in a non-positioned, non-flex item before stacking rules apply, `width` on an inline element).
- **The top layer.** Modal `<dialog>`, popovers and fullscreen elements render in a separate top layer above everything, regardless of `z-index` and ancestors' `overflow`/`transform` [6]. This removes most z-index wars for overlays.
- **Progressive enhancement is the normal way to adopt new features.** Write a baseline declaration first, then the new one; browsers drop declarations they cannot parse. Use `@supports` for blocks.
- **Roblox mapping.** A ScreenGui hierarchy with UIListLayout/UIGridLayout/UIPadding is the closest Roblox analogue: Frame ~ `<div>`, TextLabel ~ text element, layout objects ~ `display: flex/grid`, UDim2 Scale ~ `%`, Offset ~ `px`. The big difference: in CSS, sizes are usually *content-driven* (intrinsic) by default; in Roblox, they are explicit unless AutomaticSize is set.

## 2. Type system (values, units, cascade, specificity)

### 2.1 Value types
CSS properties accept typed values: `<length>` (`px`, `rem`, `em`, `ch`, `vw`, `vh`, `svh`/`lvh`/`dvh`, container units `cqi`/`cqb`/`cqw`/`cqh`), `<percentage>` (relative to a property-specific base: width -> containing block width, `padding-top` % also -> containing block **width**, `transform: translate(%)` -> the element's own box), `<number>`, `<color>`, `<angle>`, `<time>`, `<image>`, keywords. A wrong type invalidates the whole declaration at parse time (it is dropped, and the previous valid declaration wins).

Custom properties (`--x: value`) are untyped token streams by default; `var()` substitutes at computed-value time. An invalid substitution makes the property "invalid at computed-value time", which behaves like `unset` (not like a parse-time drop, so the fallback earlier in the rule does **not** apply). Use `@property` to give a custom property a syntax, initial value and inheritance; registered properties can be animated/transitioned:

```css
@property --angle {
  syntax: "<angle>";
  inherits: false;
  initial-value: 0deg;
}
.spinner { transition: --angle 1s; background: conic-gradient(from var(--angle), red, blue); }
.spinner:hover { --angle: 180deg; }
```

### 2.2 Color
Modern color: `oklch(70% 0.15 250)`, `oklab()`, `color(display-p3 1 0 0)`, relative colors `oklch(from var(--brand) calc(l + 0.1) c h)`, `color-mix(in oklch, var(--brand) 70%, white)` (widely available [2]). `light-dark(#111, #eee)` picks by the used `color-scheme`, and only works when `color-scheme: light dark` is set on the element or an ancestor (newly available [2]). Prefer OkLCh for palettes: equal L steps look equally bright, unlike HSL.

### 2.3 The cascade, in order
For each property, the winner is decided by, in order [7]:
1. **Origin and importance** (user-agent < user < author; `!important` reverses the order and beats normal declarations; transitions beat everything, animations beat normal author styles).
2. **Context** (shadow DOM: outer context wins for normal declarations).
3. **Element-attached styles** (`style=""`).
4. **Cascade layers** (`@layer`): for normal declarations, later layers win and **unlayered styles beat all layers**; for `!important`, the order flips (earlier layers win).
5. **Specificity** (id, class/attribute/pseudo-class, type/pseudo-element) as a 3-tuple compared left to right.
6. **Scope proximity** (`@scope`: the closer scope root wins, before order of appearance).
7. **Order of appearance**.

```css
@layer reset, base, components, utilities;      /* declare order once, first */
@layer reset { *, *::before, *::after { box-sizing: border-box; } }
@layer components { .btn { padding: .5rem 1rem; } }
@layer utilities { .p-0 { padding: 0; } }        /* wins over .btn regardless of specificity */
@import url(vendor.css) layer(vendor);           /* put third-party CSS in a low layer */
```

Specificity tools: `:where(...)` has zero specificity (good for defaults and resets), `:is(...)` and `:not(...)` and `:has(...)` take the specificity of their most specific argument. Nesting `&` behaves like `:is()`, so `.a, #b { & .c {} }` has id-level specificity for every match.

### 2.4 Inheritance and computed values
Inherited properties (color, font-*, line-height, visibility, cursor, custom properties by default) flow down; non-inherited (margin, padding, border, background, display, width) do not. Keywords: `inherit`, `initial` (the spec's initial value, e.g. `display: inline`), `unset`, `revert` (back to the user-agent style), `revert-layer` (back to the previous layer).

## 3. Runtime: rendering pipeline and event loop

### 3.1 Pipeline
Parse HTML -> DOM; parse CSS -> CSSOM; style (match selectors, cascade, compute) -> layout (geometry) -> paint (display lists) -> composite (GPU layers). Changes trigger the cheapest needed stage:
- `transform`, `opacity`, `filter` (often): **composite only** when the element is on its own layer. Animate these.
- `color`, `background`, `box-shadow`: **paint**.
- `width`, `height`, `top`, `margin`, font size, adding DOM nodes: **layout** (and then paint and composite).

### 3.2 Event loop
One main thread runs JS tasks, microtasks (promises), then, once per frame (~16.7 ms at 60 Hz), `requestAnimationFrame` callbacks, style, layout, paint. A long JS task blocks rendering and input (INP, Interaction to Next Paint, is the Core Web Vital that measures this). Reading layout (`offsetWidth`, `getBoundingClientRect`) after writing styles forces a synchronous layout ("layout thrashing"); batch reads before writes.

### 3.3 Loading
`<script>` without `defer`/`async`/`type=module` blocks parsing. Module scripts are deferred by default. CSS in `<head>` blocks rendering (by design, to avoid a flash of unstyled content). Use `<link rel="preload">` for late-discovered critical assets, `loading="lazy"` for below-the-fold images/iframes, `fetchpriority="high"` for the LCP image, and always give `<img>` `width`/`height` (or `aspect-ratio`) to prevent layout shift (CLS).

## 4. Tooling and package management

- **No build is required.** Modern CSS (nesting, layers, custom properties, `color-mix`) runs natively; preprocessors (Sass) are optional. Sass still adds mixins, loops and modules; native nesting covers the most common reason people used it.
- **PostCSS / Lightning CSS** for transpiling new syntax to old browsers and minification; **Browserslist** to declare targets; Baseline targets ("baseline widely available") are supported in Browserslist query syntax [1].
- **Validators and linters**: Nu HTML Checker (validator.w3.org/nu), Stylelint (CSS), axe-core / Lighthouse (accessibility, performance), html-validate.
- **Formatters**: Prettier.
- **Frameworks**: Tailwind CSS v4 (utility classes, CSS-first config with `@theme`, built on cascade layers and native features); component scoping via CSS Modules or `@scope`.
- **Package managers**: npm/pnpm/yarn/bun install CSS libraries; plain `<link>` to a CDN works too (pin versions, use Subresource Integrity `integrity="sha384-..."`).
- **Devtools**: Chrome/Edge/Firefox/Safari inspectors show the cascade (crossed-out declarations), layers, container queries, grid/flex overlays, anchor badges (Firefox 147 added one [4]), the accessibility tree, and Performance panel with layout/paint events.

## 5. Testing

- **Visual regression**: Playwright `expect(page).toHaveScreenshot()`, Storybook + Chromatic, BackstopJS. Run in all three engines (Chromium, Firefox, WebKit); Playwright ships all three.
- **Accessibility**: `@axe-core/playwright` in CI; manual keyboard pass (Tab order, Escape closes dialogs, focus is visible and returned); screen reader spot checks (NVDA, VoiceOver).
- **Layout assertions**: Playwright `toBeVisible`, `boundingBox()`; test at several viewport sizes and with 200% zoom / large text.
- **HTML validity**: run the Nu checker in CI for templates.
- **Feature detection tests**: `CSS.supports('anchor-name: --a')`, `HTMLElement.prototype.hasOwnProperty('popover')`.
- **Performance**: Lighthouse CI budgets; Web Vitals (LCP, INP, CLS) from real users.

## 6. Idiomatic patterns (code)

### 6.1 Modal dialog with invoker commands (no JS)
`command`/`commandfor` are newly available (Chrome 135, Firefox 144, Safari 26.2) [2][8].

```html
<button command="show-modal" commandfor="settings">Settings</button>
<dialog id="settings" closedby="any" aria-labelledby="settings-title">
  <h2 id="settings-title">Settings</h2>
  <form method="dialog">          <!-- submitting closes the dialog; returnValue = button value -->
    <label>Volume <input type="range" name="vol" min="0" max="100"></label>
    <button value="save">Save</button>
    <button command="close" commandfor="settings" type="button">Cancel</button>
  </form>
</dialog>
```
`showModal()` (or `command="show-modal"`) puts the dialog in the top layer, makes the rest of the page inert, traps focus and closes on Escape. `show()` opens it non-modally (no inertness, no Escape). `::backdrop` styles the dimmed overlay. `closedby="any"` (light dismiss by clicking outside) is newer; check support before relying on it (unverified as Baseline on 2026-10-13).

### 6.2 Popover (menus, toasts, tooltips)
```html
<button popovertarget="menu">Menu</button>
<div id="menu" popover>          <!-- popover="auto": light dismiss, one auto popover open at a time -->
  <a href="/profile">Profile</a>
</div>
<div id="toast" popover="manual">Saved</div>   <!-- manual: no light dismiss; you close it -->
```
Popover is newly available since January 2025 [2]. A popover is not modal and does not trap focus; use `<dialog>` with `showModal()` for anything that must block the page.

### 6.3 Anchor positioning (tooltip pinned to its button)
```css
.trigger { anchor-name: --tip; }
.tooltip {
  position: fixed;
  position-anchor: --tip;
  position-area: top;                  /* or: top: anchor(bottom); left: anchor(center); */
  position-try-fallbacks: flip-block;  /* flip below when there is no room above */
  margin-bottom: 4px;
}
@supports not (anchor-name: --a) {
  .tooltip { /* fallback: JS (Floating UI) or a static placement */ }
}
```
Core properties: Chrome/Edge 125, Safari 26, Firefox 147 [3][4]. Combine with `popover` so the tooltip is in the top layer and gets light dismiss for free.

### 6.4 Mutually exclusive accordion
```html
<details name="faq" open><summary>Shipping</summary><p>...</p></details>
<details name="faq"><summary>Returns</summary><p>...</p></details>
```
Same `name` = only one open at a time (newly available 2024 [2]). Content inside a closed `<details>` is findable with Ctrl+F in Chromium (auto-expands).

### 6.5 Layout: flexbox for one dimension, grid for two
```css
.toolbar { display: flex; gap: .5rem; align-items: center; }
.toolbar .spacer { margin-inline-start: auto; }          /* push the rest to the end */

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(16rem, 100%), 1fr));
  gap: 1rem;
}
.card { display: grid; grid-row: span 3; grid-template-rows: subgrid; } /* align titles/bodies/footers across cards */
```
`minmax(min(16rem, 100%), 1fr)` prevents overflow on narrow screens. Subgrid is widely available since March 2026 [2].

### 6.6 Container queries (components that adapt to their slot, not the viewport)
```css
.card-slot { container: card / inline-size; }
@container card (inline-size > 30rem) {
  .card { grid-template-columns: 10rem 1fr; }
}
/* style query on a custom property (newly available May 2026 [2]) */
@container style(--variant: compact) { .card { padding: .25rem; } }
```
A size container cannot size itself from its children in the queried axis (containment); an element with `container-type: inline-size` and no width from its parent collapses to zero width.

### 6.7 `:has()` as a parent / state selector
```css
form:has(:user-invalid) .submit { opacity: .5; }
.card:has(> img) { grid-template-rows: auto 1fr; }
label:has(input:checked) { outline: 2px solid var(--accent); }
```
`:user-invalid` matches only after the user interacted, unlike `:invalid` which matches empty required fields on page load.

### 6.8 Nesting and scope
```css
.card {
  padding: 1rem;
  &:hover { background: color-mix(in oklch, var(--bg), black 5%); }
  .title { font-weight: 700; }           /* descendant; no & needed */
  @media (width < 40rem) { padding: .5rem; }
}
@scope (.card) to (.card-content) {      /* donut scope: styles stop at .card-content */
  img { border-radius: .5rem; }
}
```

### 6.9 Entry and exit animations (display none <-> block)
```css
.toast { transition: opacity .2s, translate .2s, display .2s allow-discrete, overlay .2s allow-discrete; }
.toast:popover-open { opacity: 1; translate: 0 0; }
@starting-style { .toast:popover-open { opacity: 0; translate: 0 1rem; } }
.toast { opacity: 0; translate: 0 1rem; }
```
`@starting-style` gives the "from" values on first render; `transition-behavior: allow-discrete` lets `display` and `overlay` flip at the right end of the transition (both newly available 2024 [2]).

### 6.10 View transitions
Same-document (newly available October 2025 when Firefox 144 shipped it [2]):
```js
if (!document.startViewTransition) updateDOM();
else document.startViewTransition(() => updateDOM());
```
```css
.hero { view-transition-name: hero; }          /* names must be unique on the page at capture time */
::view-transition-old(root), ::view-transition-new(root) { animation-duration: .25s; }
@media (prefers-reduced-motion: reduce) { ::view-transition-group(*) { animation: none; } }
```
Cross-document (MPA) view transitions: opt in on both pages with `@view-transition { navigation: auto; }`; same-origin only; Chromium 126 and Safari 18.2, not Firefox (limited availability [2]).

### 6.11 Scroll-driven animation (progressive enhancement)
```css
@supports (animation-timeline: scroll()) {
  .progress { animation: grow linear both; animation-timeline: scroll(root block); }
  .reveal   { animation: fade-in linear both; animation-timeline: view(); animation-range: entry 0% cover 30%; }
}
@keyframes grow { from { scale: 0 1; } to { scale: 1 1; } }
```
Chrome 115 and Safari 26 ship it; Firefox stable did not as of the webstatus data (limited availability [2]). Always guard with `@supports`.

### 6.12 Forms that size and validate themselves
```html
<textarea name="msg" required minlength="10" style="field-sizing: content; min-block-size: 3lh"></textarea>
<input type="email" name="email" required autocomplete="email">
```
Constraint validation runs on submit: `required`, `pattern`, `min`/`max`, `minlength`, `type=email/url/number`. JS: `input.setCustomValidity("message")` (empty string clears it), `form.reportValidity()`. `field-sizing: content` became newly available in June 2026 [2].

### 6.13 Typography and theme
```css
:root { color-scheme: light dark; --bg: light-dark(#fff, #0b0d10); --fg: light-dark(#111, #e8e8e8); }
h1, h2, h3 { text-wrap: balance; }     /* even line lengths for short headings */
p { text-wrap: pretty; max-inline-size: 65ch; }
html { font-size: 100%; }              /* never lock root size in px; users scale it */
```

### 6.14 Experimental (limited availability; Chromium-first)
```css
/* if(): inline conditional (Chrome 137+) [9] */
.btn { padding: 1em; padding: if(style(--size: small): .25em; else: 1em); }
/* @function: custom functions (Chrome 139+) */
@function --fluid(--min, --max) { result: clamp(var(--min), 2vw + 1rem, var(--max)); }
h1 { font-size: --fluid(1.5rem, 3rem); }
/* customizable select (Chrome 135+, Safari 27) */
select, ::picker(select) { appearance: base-select; }
```
Always precede with a plain declaration: `if()` and `@function` usage invalidate the declaration in unsupporting browsers.

## 7. Top pitfalls and error-message fixes

| Symptom or exact message | Cause | Fix |
|---|---|---|
| `z-index` has no effect | Element is `position: static` and not a flex/grid item, or it is trapped in a parent's stacking context (`transform`, `opacity < 1`, `filter`, `isolation`, `will-change`) | Give it `position: relative`, or move it out of the stacking context; for overlays use `<dialog>`/`popover` (top layer) |
| `height: 100%` does nothing | Parent has no definite height | Use grid/flex stretch, or `min-block-size: 100dvh` on the root container |
| `100vh` taller than the phone screen | Mobile browser UI (URL bar) not included | Use `100dvh` (dynamic) or `100svh` (small) |
| Horizontal scrollbar on mobile | A child wider than the viewport: fixed `width`, long word, `100vw` (includes scrollbar width), grid `1fr` with wide content | `min-width: 0` on flex/grid children, `minmax(0, 1fr)`, `overflow-wrap: anywhere`, avoid `100vw` |
| Flex item text overflows instead of shrinking | Flex items default to `min-width: auto` | `min-width: 0` (or `overflow: hidden`) on the item |
| `position: sticky` does not stick | An ancestor has `overflow: hidden/auto`, or no `top` set, or the parent is as short as the element | Set `top: 0`; remove the overflow on ancestors (use `overflow: clip`) |
| Container query never matches, element is 0 px wide | `container-type: inline-size` on an element sized by its content (size containment) | Give the container a width from its parent (block-level, grid track) or query a parent wrapper |
| `light-dark()` always returns the light value | No `color-scheme` set | `:root { color-scheme: light dark; }` |
| Custom property fallback ignored: `color: red; color: var(--missing-typo-ish)` shows black | Invalid at computed-value time behaves like `unset`; the earlier `red` is already discarded | Use `var(--x, red)` fallback, or `@property` with an initial value |
| Nested rule ignored in old browsers | Native nesting unsupported (pre-2023 engines) | Transpile with Lightning CSS/PostCSS, or set Browserslist targets |
| Utility class loses to component class | Specificity or layer order | Put components and utilities in `@layer` with utilities last; avoid ids in selectors |
| `Uncaught DOMException: Failed to execute 'showModal' on 'HTMLDialogElement': The element already has an 'open' attribute` | Dialog opened via `open` attribute or `show()` first | Remove the `open` attribute; call `close()` before `showModal()` |
| `InvalidStateError` when calling `showPopover()` | Element is missing the `popover` attribute, or is already open, or is disconnected | Add `popover`; check `el.matches(':popover-open')` first |
| Dialog is not modal: page behind still clickable, Escape does nothing | Used `show()` or the `open` attribute | Use `showModal()` or `command="show-modal"` |
| `An invalid form control with name='x' is not focusable.` (console) | A `required` field is hidden (`display: none`) so the browser cannot show the bubble | Remove `required` from hidden fields or use `disabled`; or add `novalidate` and validate yourself |
| `Blocked aria-hidden on an element because its descendant retained focus.` | `aria-hidden="true"` set on an ancestor of the focused element | Use `inert` instead of `aria-hidden` for hidden regions; move focus first |
| `Mixed Content: The page at 'https://...' was loaded over HTTPS, but requested an insecure stylesheet` | `http:` asset on an HTTPS page | Serve the asset over HTTPS |
| `Refused to apply style from '...' because its MIME type ('text/html') is not a supported stylesheet MIME type` | Wrong path returns an HTML 404 page, or server sends wrong Content-Type | Fix the URL; serve `text/css` |
| `Refused to apply inline style because it violates the following Content Security Policy directive: "style-src 'self'"` | CSP blocks `style=""`/`<style>` | Move styles to a file or add a nonce/hash |
| Transition from `display: none` does not animate | `display` is discrete; first render has no "before" style | `@starting-style` plus `transition-behavior: allow-discrete` |
| `view-transition-name` duplicate: `Unexpected duplicate view-transition-name` | Two elements share a name during capture | Make names unique (`view-transition-name: card-1`), or use `view-transition-class` for shared styling |
| Anchored element appears at top-left | Browser lacks anchor positioning, or `position-anchor` names an anchor that is not rendered/visible before it in a valid containing block | Add `@supports` fallback; check the anchor is laid out and acceptable (same containing block rules) |
| Images cause layout shift (CLS) | No intrinsic size reserved | `width`/`height` attributes or `aspect-ratio` |

## 8. Performance

- Animate `transform`, `opacity`, `translate`/`scale`/`rotate` individual transform properties, and `filter` where possible; avoid animating `width`, `top`, `box-shadow` on large areas.
- `content-visibility: auto` with `contain-intrinsic-size: auto 500px` skips rendering of off-screen sections (big win for long lists).
- `will-change` only during the animation; permanently promoting many layers costs GPU memory.
- Avoid layout thrashing: batch DOM reads then writes; use `ResizeObserver`/`IntersectionObserver` instead of polling layout.
- Keep selectors simple; `:has()` is fast in modern engines but very broad `:has()` on `body` invalidates more style on each DOM change.
- Fonts: `font-display: swap`, preload the main font, subset, use `size-adjust` on fallbacks to cut layout shift.
- Images: `srcset`/`sizes`, AVIF/WebP, `loading="lazy"` except the LCP image, `decoding="async"`.
- Measure with Lighthouse, Performance panel and real-user Web Vitals (LCP < 2.5 s, INP < 200 ms, CLS < 0.1) [10].

## 9. Security

- **XSS** is the top risk: never inject untrusted strings with `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`. Use `textContent`, DOM APIs, or a sanitizer (DOMPurify; the native `Element.setHTML()` Sanitizer API is newer, check support). Template engines must auto-escape.
- **Content Security Policy**: `script-src 'self' 'nonce-...'; object-src 'none'; base-uri 'none'` and Trusted Types (`require-trusted-types-for 'script'`) on Chromium.
- **Links**: `target="_blank"` now implies `rel="noopener"` in modern browsers; add `rel="noopener noreferrer"` for older ones.
- **Iframes**: `sandbox` attribute (start with none and add `allow-scripts` etc. as needed); `allow` for permissions policy.
- **CSS can leak data**: attribute selectors plus `background: url()` can exfiltrate input values (CSS injection); do not let users inject CSS. Clickjacking: `frame-ancestors` CSP / `X-Frame-Options`.
- **Forms**: client-side validation is UX only; validate on the server. Use `autocomplete` correctly, `type=password`, and HTTPS.
- **Subresource Integrity** for CDN scripts and styles.

## 10. Game-dev usage

- **Game UI on the web**: HUDs and menus for canvas/WebGL/WebGPU games are often HTML/CSS overlays positioned over the `<canvas>` (`position: absolute; inset: 0; pointer-events: none` on the overlay, `pointer-events: auto` on buttons). Accessible, crisp text, easy layout; keep it in the compositor (transforms/opacity) to avoid stalling the game loop.
- **Engines**: Godot, Unity, Unreal (via community ports), Defold, Bevy export to the web as WebAssembly in a page; the HTML shell (loading bar, fullscreen button) is plain HTML/CSS.
- **Game UI middleware** (Coherent Gameface, Ultralight) renders HTML/CSS inside native engines; their CSS support is a subset, so check each feature.
- **Fullscreen and pointer lock**: `element.requestFullscreen()`, `canvas.requestPointerLock()` need a user gesture. `touch-action: none` on the canvas to stop the browser from panning/zooming.
- **Pixel art**: `image-rendering: pixelated` on canvas/images.
- **Roblox**: none of this runs in Roblox; Roblox UI uses GuiObjects. But Roblox UI designers can borrow the same concepts: layout objects mirror flex/grid, UIAspectRatioConstraint mirrors `aspect-ratio`, Scale vs Offset mirrors `%` vs `px`.

## 11. Cheat sheet vs Luau / Roblox UI

| Concept | Roblox (Luau UI) | HTML/CSS |
|---|---|---|
| Container | Frame | `<div>` / semantic element (`<section>`, `<nav>`) |
| Root UI | ScreenGui in PlayerGui | `<body>`, top layer for overlays |
| Size relative to parent | `UDim2.fromScale(0.5, 0)` | `width: 50%` |
| Fixed pixels | `UDim2.fromOffset(200, 50)` | `width: 200px` (prefer `rem`) |
| Scale + offset | `UDim2.new(1, -20, 0, 40)` | `width: calc(100% - 20px); height: 40px` |
| Viewport units | `workspace.CurrentCamera.ViewportSize` | `vw`, `vh`, `dvh`, `svh` |
| AnchorPoint (0.5, 0.5) centering | `AnchorPoint = Vector2.new(.5,.5)`, Position `{0.5,0},{0.5,0}` | `position:absolute; left:50%; top:50%; translate:-50% -50%` or `place-items:center` on a grid parent |
| UIListLayout | FillDirection, Padding, HorizontalAlignment | `display:flex; flex-direction; gap; justify-content; align-items` |
| UIGridLayout | CellSize, CellPadding | `display:grid; grid-template-columns: repeat(auto-fill, minmax(...)); gap` |
| UIPadding | PaddingTop/Left... | `padding` (logical: `padding-inline`, `padding-block`) |
| UICorner | CornerRadius | `border-radius` |
| UIStroke | Thickness, Color, ApplyStrokeMode | `border` / `outline` (Border mode) or `-webkit-text-stroke` / `text-shadow` (Contextual on text) |
| UIGradient | ColorSequence, Rotation | `linear-gradient(90deg, ...)`, `background-clip: text` for text |
| UIAspectRatioConstraint | AspectRatio | `aspect-ratio: 1` |
| UISizeConstraint / UITextSizeConstraint | Min/MaxSize, MaxTextSize | `min-width`/`max-width`, `clamp()` for font size |
| AutomaticSize | `AutomaticSize = Enum.AutomaticSize.Y` | default behaviour (height: auto), `fit-content`, `field-sizing: content` |
| ZIndex / DisplayOrder | ZIndex per sibling, ScreenGui.DisplayOrder | `z-index` within stacking contexts; top layer for dialogs/popovers |
| ClipsDescendants | `ClipsDescendants = true` | `overflow: hidden` / `overflow: clip` |
| ScrollingFrame + AutomaticCanvasSize | CanvasSize, ScrollingDirection | `overflow: auto`, content-sized by default; `scroll-snap-type` |
| TweenService | `TweenService:Create(obj, TweenInfo.new(.2, Enum.EasingStyle.Quad), {...})` | `transition: transform .2s ease-out` / `@keyframes` / Web Animations API `el.animate()` |
| Visible = false | `Visible = false` | `display: none` / `hidden` attribute; `visibility: hidden` keeps the space |
| Activated / MouseButton1Click | `button.Activated:Connect(fn)` | `button.addEventListener('click', fn)` (fires for keyboard too on `<button>`) |
| Safe area / notch | `ScreenInsets`, `SafeAreaCompatibility` | `env(safe-area-inset-top)` with `viewport-fit=cover` |
| Rich text | `RichText = true`, `<b>`, `<font color>` | Real markup: `<strong>`, `<span style>` |
| Responsive breakpoints | Read ViewportSize and switch layouts in code | `@media (width < 40rem)`, `@container` |

## 12. Recent changes and version notes (2024 to 2026)

- 2024: `<details name>`, `light-dark()`, `text-wrap: balance`, `@starting-style`, `transition-behavior` become Baseline newly available [2].
- January 2025: Popover Baseline newly available [2].
- October 2025: same-document view transitions newly available (Firefox 144) [2].
- December 2025: invoker commands (`command`/`commandfor`) newly available [2][8].
- January 2026: Firefox 147 enables anchor positioning, `anchor-center`, `position-anchor: none` [4].
- March 2026: `@scope` newly available (Firefox 146, Safari 26.4); subgrid widely available [2].
- May to June 2026: container style queries newly available (Firefox 151); `field-sizing` newly available (Firefox 152, Safari 26.2); nesting and `:has()` widely available (June 2026) [2].
- Still limited on 2026-10-13: scroll-driven animations (no Firefox stable), cross-document view transitions (no Firefox), `if()` (Chrome 137+), `@function` (Chrome 139+), `interpolate-size`, interest invokers, `reading-flow`, `corner-shape` (Chromium), customizable `<select>` (Chrome 135, Safari 27) [2][9].

## Sources

1. https://web.dev/baseline (accessed 2026-10-13)
2. https://webstatus.dev/ and its API https://api.webstatus.dev/v1/features/ (feature ids queried: anchor-positioning, scroll-driven-animations, if, view-transitions, cross-document-view-transitions, scope, cascade-layers, nesting, has, container-queries, container-style-queries, subgrid, popover, invoker-commands, details-name, field-sizing, text-wrap-balance, light-dark, color-mix, oklab, dialog, customizable-select, interest-invokers, function, starting-style, transition-behavior, interpolate-size, reading-flow, corner-shape) (accessed 2026-10-13)
3. https://developer.chrome.com/docs/css-ui/anchor-positioning-api (accessed 2026-10-13)
4. https://developer.mozilla.org/en-US/docs/Mozilla/Firefox/Releases/147 (accessed 2026-10-13)
5. https://html.spec.whatwg.org/multipage/ (accessed 2026-10-13)
6. https://developer.mozilla.org/en-US/docs/Glossary/Top_layer (accessed 2026-10-13)
7. https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_cascade/Cascade (accessed 2026-10-13)
8. https://developer.mozilla.org/en-US/docs/Web/API/Invoker_Commands_API (accessed 2026-10-13)
9. https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/if (accessed 2026-10-13)
10. https://web.dev/articles/vitals (accessed 2026-10-13)
11. https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog (accessed 2026-10-13)
12. https://developer.mozilla.org/en-US/docs/Web/API/Popover_API (accessed 2026-10-13)
13. https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries (accessed 2026-10-13)
14. https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API (accessed 2026-10-13)
15. https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations (accessed 2026-10-13)
16. https://developer.mozilla.org/en-US/docs/Web/CSS/@layer (accessed 2026-10-13)
17. https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Constraint_validation (accessed 2026-10-13)
18. https://create.roblox.com/docs/ui/position-and-size (Roblox side of the cheat sheet; accessed 2026-10-13)
