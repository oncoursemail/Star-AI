# HTML, CSS and WebAssembly: errors, fixes and the Roblox UI cheat sheet (checked 2026-10-13)

## HTML and CSS

| Symptom or message | Cause | Fix |
|---|---|---|
| z-index has no effect | Element is static and not a flex/grid item, or trapped in a parent stacking context (transform, opacity below 1, filter, isolation, will-change) | position: relative, move it out, or use dialog/popover (top layer) |
| height: 100% does nothing | Parent height is not definite | Grid or flex stretch, or min-block-size: 100dvh on the root container |
| 100vh taller than the phone screen | Browser toolbars not counted | 100dvh or 100svh |
| Horizontal scroll on mobile | Child wider than viewport, 100vw includes scrollbar, flex/grid min-width auto | min-width: 0, minmax(0, 1fr), overflow-wrap: anywhere |
| position: sticky does not stick | No top value, or an ancestor has overflow hidden/auto | Set top: 0; use overflow: clip on ancestors |
| Container query never matches; element is 0 px wide | container-type: inline-size on a content-sized element | Size it from its parent or query a wrapper |
| light-dark() always light | No color-scheme | :root { color-scheme: light dark; } |
| var() fallback earlier in the rule ignored | Invalid at computed-value time acts like unset | var(--x, fallback) or @property with initial-value |
| Utility class loses to component class | Specificity or layer order | @layer components, utilities (utilities last); no id selectors |
| Failed to execute 'showModal' on 'HTMLDialogElement': The element already has an 'open' attribute | Dialog opened with the open attribute or show() | Remove open; close() before showModal() |
| InvalidStateError from showPopover() | Missing popover attribute, already open, or disconnected | Add popover; check :popover-open first |
| Dialog not modal, Escape does nothing | show() or the open attribute | showModal() or command="show-modal" |
| An invalid form control with name='x' is not focusable. | A required field is hidden | Remove required from hidden fields, or disable them |
| Blocked aria-hidden on an element because its descendant retained focus. | aria-hidden on an ancestor of focus | Use inert; move focus first |
| Refused to apply style ... MIME type ('text/html') is not a supported stylesheet MIME type | Wrong path returns HTML, or wrong Content-Type | Fix the URL; serve text/css |
| Refused to apply inline style because it violates ... "style-src 'self'" | CSP blocks inline style | Move to a file, or nonce/hash |
| Transition from display: none does not animate | Discrete property, no start style | @starting-style plus transition-behavior: allow-discrete |
| Unexpected duplicate view-transition-name | Two elements share a name | Unique names; view-transition-class for shared styling |
| Anchored element at top-left | No anchor positioning support or anchor not laid out first | @supports fallback; check the anchor exists and is rendered |
| Layout shift when images load | No reserved size | width/height attributes or aspect-ratio |
| Flex item text overflows | min-width: auto on flex items | min-width: 0 |

## WebAssembly

| Message | Cause | Fix |
|---|---|---|
| Incorrect response MIME type. Expected 'application/wasm'. | Server Content-Type wrong for instantiateStreaming | Serve application/wasm or use instantiate(arrayBuffer) |
| expected magic word 00 61 73 6d, found 3c 21 44 4f | Got HTML (404 page) instead of Wasm | Fix the path or rewrite rules |
| LinkError: ... Import #0 module="env" function="foo": function import requires a callable | Import object incomplete | Provide every import; WebAssembly.Module.imports(mod) lists them |
| RuntimeError: memory access out of bounds | Bad pointer, use after free, stack overflow | -sASSERTIONS=2 -sSAFE_HEAP=1, AddressSanitizer, check lengths |
| RuntimeError: unreachable | Rust panic or C abort compiled to a trap | console_error_panic_hook; build with debug info |
| Detached ArrayBuffer / views read zeros | memory.grow replaced the buffer | Re-create views from memory.buffer after allocating calls |
| SharedArrayBuffer is not defined | Not cross-origin isolated | COOP same-origin plus COEP require-corp or credentialless |
| Cannot enlarge memory arrays / could not allocate memory | Memory cap or low device memory | -sALLOW_MEMORY_GROWTH=1, smaller initial memory, stream assets |
| null function or function signature mismatch | Function pointer cast to a wrong type or null table slot | Fix the prototype |
| CompileError: invalid opcode / unknown type | Engine lacks SIMD, GC, exnref or Memory64 | Feature-detect and ship a fallback build |
| wasm-bindgen schema version mismatch | CLI and crate versions differ | cargo install wasm-bindgen-cli --version matching the crate |
| unknown import: wasi_snapshot_preview1::fd_write | Host did not link WASI | wasmtime run, add WASI to the linker, or adapt to a component |
| Atomics.wait cannot be called in this context | Blocking wait on the main thread | Wait in a worker, or Atomics.waitAsync |
| can't find crate for core (wasm32 target) | Rust target missing | rustup target add wasm32-unknown-unknown (or wasm32-wasip2) |

## Roblox UI to HTML/CSS

| Roblox | HTML/CSS |
|---|---|
| Frame | div or a semantic element |
| ScreenGui / DisplayOrder | body; top layer for dialogs and popovers |
| UDim2.fromScale(0.5, 0) | width: 50% |
| UDim2.fromOffset(200, 50) | width: 200px (prefer rem) |
| UDim2.new(1, -20, 0, 40) | width: calc(100% - 20px); height: 40px |
| AnchorPoint (0.5, 0.5) at Position (0.5, 0.5) | left: 50%; top: 50%; translate: -50% -50% (or place-items: center) |
| UIListLayout (FillDirection, Padding) | display: flex; flex-direction; gap |
| UIGridLayout (CellSize, CellPadding) | display: grid; repeat(auto-fill, minmax(...)); gap |
| UIPadding | padding (padding-inline, padding-block) |
| UICorner | border-radius |
| UIStroke | border / outline; text-shadow for text |
| UIGradient | linear-gradient() |
| UIAspectRatioConstraint | aspect-ratio |
| UISizeConstraint / UITextSizeConstraint | min/max-width; clamp() for font-size |
| AutomaticSize | default auto height, fit-content, field-sizing: content |
| ZIndex | z-index inside a stacking context |
| ClipsDescendants | overflow: hidden or clip |
| ScrollingFrame | overflow: auto; scroll-snap-type |
| TweenService | transition, @keyframes, element.animate() |
| Visible = false | display: none or the hidden attribute |
| Activated | click event on a button (keyboard included) |
| ScreenInsets / safe area | env(safe-area-inset-top) with viewport-fit=cover |
| Breakpoints from ViewportSize | @media and @container |
