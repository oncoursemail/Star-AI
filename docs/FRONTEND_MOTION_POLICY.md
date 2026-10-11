# Interface motion and product showcase

The desktop uses one effective reduced-motion preference: **the saved STAR setting OR the device preference**. STAR can request less motion; it never overrides a device request for less motion. Device changes are subscribed to live, and the server snapshot is false so website hydration starts from the same markup as prerendering.

`frontend/src/MotionPolicy.tsx` supplies this value to Motion and the STAR components. Explicit variants use zero duration and delay in reduced mode, including opacity and disclosure height: Motion's own reduced-motion configuration intentionally preserves some non-transform animations. Final keyframes settle already-mounted message/menu animations when the preference changes. A presence-aware `MotionSurface` stops and settles route/disclosure animations and releases pending exits after the parent records its next children. This keeps content mounted and focus stable. Reduced mode skips hidden entrance states. The normal timing tokens remain in `motion.ts`.

The same value governs Analytics area animation, local-model progress width, Latest scrolling and Composer menus. A lifecycle-managed `data-star-reduced-motion` document attribute lets CSS cover portalled `.star-layer` dialogs and tooltips, which are outside `.shell`. It is restored when Desktop unmounts. CSS state words, selection, focus rings and completed icons remain visible.

The existing public website keeps its STAR mark, gold selection, actual release availability and early-software language. The product showcase adds numbered keyboard-navigable tabs, a workbench frame, explicit capture/preview/sample modes and a clearer caption hierarchy. A scripted sample run starts only when requested and can be replayed or removed. Its caption states that no model is running and that the answer/timing are examples. Reduced-motion visitors see the completed sample conversation. Switching to another product area removes a chat sample.

The public captures were refreshed from the current read-only browser preview: five screens at wide and narrow widths, plus three feature crops. Their manifest timestamp and alternative text describe these captures. `capture-site-media.mjs` now selects the current composer by accessible name and the current local-model card, so its refresh workflow still works.

## Verification

- Full frontend suite: 126 tests across 13 files pass with one worker and a 15-second per-test timeout. Existing Motion/React test-environment warnings remain; no unhandled error was reported. The focused policy tests cover pending route exit release, disclosure settlement and retained focus.
- TypeScript: `pnpm exec tsc --noEmit --incremental false` passes.
- Bundle: `pnpm exec vite build --configLoader native` passes; 2,916 modules. Main website JS 317.72 kB (96.99 kB gzip), desktop JS 819.85 kB (248.96 kB gzip), CSS 118.98 kB (22.57 kB gzip). The presence-aware surface is a desktop-only module, preserving the website's lazy workspace boundary. The existing large-desktop-chunk warning remains.
- Website prerender: `node scripts/prerender-site.mjs` writes a 56 kB landing document successfully. This is the website path; regular desktop builds keep an empty root.
- Headless Edge verifies the production/prerendered bundle at 1440×1000 and 390×844 with normal and reduced motion. Both website and workspace have no horizontal overflow or page errors. Keyboard tour navigation and opt-in sample selection work, and twelve screenshots record these views.
- A synthetic browser-only host verifies immediate preference persistence, live device changes, image-dialog timing (160 ms normally, 0.01 ms when reduced), focus restoration, Latest scrolling (smooth normally, auto when reduced) and a populated chart rendering without running DOM animations. Browser fixtures exercise preference changes during route and disclosure animation. Unit coverage verifies the animation flag handed to the actual chart renderer.

The branch includes the separately reviewed `star/export-path-20261011` dependency: export-parent normalization for POSIX paths. It has no independent learning changes. The existing Python source-contract test follows the extracted policy and effective preference; its CSS, save and research assertions remain intact.

After that dependency and source-contract update, Python `compileall` passes and the full suite reports **957 passed, 8 skipped** in 62.22 seconds. The audit uses a scratch APPDATA/LOCALAPPDATA and offscreen Qt platform; the real STAR profile remains untouched.

These are browser and synthetic-host checks. They do not establish native Qt performance, production Lighthouse scores, live-model output quality or Roblox multiplayer correctness. No model server, real user data, native desktop window, credentials, publication or new package dependency is required by this change.

## References

- [Motion accessibility](https://motion.dev/docs/react-accessibility) and [MotionConfig](https://motion.dev/docs/react-motion-config)
- [Web rendering and animation performance](https://web.dev/articles/animations-guide)
- [Fluent motion principles](https://fluent2.microsoft.design/motion)
- [WCAG animation from interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
- [Radix accessibility](https://www.radix-ui.com/primitives/docs/overview/accessibility)
