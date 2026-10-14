---
name: lang-web-html-css-wasm
description: Modern HTML, CSS and WebAssembly as of 2026-10: semantic elements, dialog/popover/invokers, cascade layers, :has(), container queries, anchor positioning, Baseline status, Wasm 3.0, WASI 0.3, threads and cross-origin isolation, Roblox UI mapping.
---
# Modern HTML, CSS and WebAssembly (checked 2026-10-13)
- Pick the element for its meaning: button for actions, a href for navigation, dialog for modals, label for every input. A div with a click handler has no focus, no keyboard activation and no role.
- Modal: dialog plus showModal() or the invoker button command="show-modal" commandfor="id" (Baseline newly available since Dec 2025). showModal puts it in the top layer, makes the page inert, traps focus, closes on Escape. show() and the open attribute are NOT modal. form method="dialog" closes it.
- Menus, toasts, tooltips: the popover attribute plus popovertarget (newly available since Jan 2025). popover="auto" light-dismisses; popover="manual" does not. Popover is not modal.
- Top layer beats z-index. Fix "z-index does nothing": the element needs position or a flex/grid parent, and a parent with transform, opacity below 1, filter or isolation creates a stacking context that traps it.
- Cascade order: origin and !important, then cascade layers (later layer wins; unlayered beats every layer; !important flips the order), then specificity, then @scope proximity, then source order. Declare "@layer reset, base, components, utilities;" first. :where() has zero specificity.
- Widely available now: cascade layers, nesting, :has(), size container queries, subgrid, color-mix(), oklch(). Newly available: @scope, container style queries, field-sizing, details name, light-dark() (needs color-scheme: light dark), text-wrap balance, @starting-style, same-document view transitions.
- Limited (guard with @supports, write a plain fallback declaration first): scroll-driven animations (no Firefox stable), cross-document view transitions (no Firefox), if() and @function (Chromium only), customizable select, interest invokers. Anchor positioning core ships in Chrome 125, Firefox 147, Safari 26; keep a fallback.
- Layout: flex for one axis, grid for two. On flex/grid children set min-width: 0 to allow shrinking; use minmax(min(16rem, 100%), 1fr) to avoid overflow. Use 100dvh, not 100vh, on phones. sticky needs top and no overflow: hidden ancestor.
- A container with container-type: inline-size cannot take its width from its children; give it a width from its parent.
- Animate transform, translate, scale and opacity, not width or top. Animate display: none with @starting-style and transition-behavior: allow-discrete. Respect prefers-reduced-motion.
- Images: width and height attributes or aspect-ratio (no layout shift), loading="lazy" except the main image. Forms: required, pattern, type=email; setCustomValidity(""); validate again on the server.
- Security: never put untrusted text in innerHTML; use textContent or a sanitizer; add a Content Security Policy; sandbox iframes.
- Roblox UI mapping: Scale = %, Offset = px, UDim2.new(1,-20,0,40) = calc(100% - 20px) and 40px, AnchorPoint 0.5 = translate -50%, UIListLayout = flex plus gap, UIGridLayout = grid, UIPadding = padding, UICorner = border-radius, UIStroke = border or outline, UIAspectRatioConstraint = aspect-ratio, TweenService = transition or element.animate().
- Wasm is a compile target, not a language: a module has imports and exports, and the host grants every capability. Linear memory is one ArrayBuffer; out-of-bounds traps, but bugs inside the module can still corrupt its own data.
- Wasm 3.0 (Sept 2025): GC, typed references, Memory64, multiple memories, tail calls, exceptions with exnref, relaxed SIMD, JS string builtins. Feature-detect (wasm-feature-detect) and ship a fallback build; Safari has Memory64 and relaxed SIMD only behind flags.
- Serve .wasm as application/wasm for instantiateStreaming. "expected magic word 00 61 73 6d" means the server returned HTML (a 404 page).
- memory.grow detaches old views: re-create Uint8Array/Float32Array from memory.buffer after any call that may allocate.
- SharedArrayBuffer and Wasm threads need cross-origin isolation: Cross-Origin-Opener-Policy: same-origin plus Cross-Origin-Embedder-Policy: require-corp (or credentialless); check self.crossOriginIsolated. Never Atomics.wait on the main thread.
- Async browser APIs from Wasm: JSPI (WebAssembly.Suspending and WebAssembly.promising) where shipped, else Asyncify or a callback main loop (emscripten_set_main_loop).
- Cross the JS boundary rarely: one step(dt) per frame, share data through memory views, avoid string conversion in hot paths.
- WASI 0.3 (June 2026): async func, stream and future in the Component Model; wasi:io is gone. WASI 0.2 still common. Wasmtime 46+ enables component async by default.
- Mods: embed Wasmtime with fuel or epoch interruption and memory limits; expose only validated host functions. Client Wasm is readable and editable, so keep authority on the server.
- Luau runs in a page through the Luau.Web Emscripten build (LUAU_BUILD_WEB, executeScript, checkScript): the VM only, no Roblox API.
