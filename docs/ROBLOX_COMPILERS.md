# Roblox UI compiler

Pure Python: `from star.roblox_ui_compiler import compile_ui, validate, SpecError`.

`compile_ui(json_text)` returns `Compilation(source, warnings)`. Place the source in a ModuleScript required by a client LocalScript; it creates the GUI under PlayerGui, returns `handles` keyed by id and a `destroy()` function to disconnect events and cancel tweens. No network or model calls; this tool is not wired into STAR's runtime.

## Format

Top-level object: `palette` maps symbolic names to `#RRGGBB`; `root` is a screen node; optional `mobile` accepts `safeArea` (boolean), `minTouchSize` (44..200), `referenceWidth` (320..3840), `scaleByViewport` (boolean).

Nodes require `id` (unique alphanumeric/underscore identifier starting with letter) and `type` (`screen`, `frame`, `scroll`, `grid`, `text`, `button`, `image`, `input`, `toggle`, `progress`). Container nodes accept nested `children`. Optional node properties: `name`, `size`, `position`, `anchor`, `background`, `transparency`, `visible`, `padding`, `corner`, `stroke`, `text`, `font`, `textSize`, `textColor`, `textWrapped`, `image`, `layout`, `states`, `minSize`, `maxSize`, `aspectRatio`, `value`, `placeholder`, `enabled`.

Dimensions use `{"scale":0.5,"offset":12}` and vectors use `{"x":{"scale":0.5},"y":{"offset":40}}`. `stroke` accepts `color` (palette name), `thickness`, `transparency`. `layout.kind` is `list` or `grid`; optional attributes include `direction`, `spacing`, `columns`, `cellSize`, `cellPadding`, alignments and sort order. Interactive `states` include `hover`, `pressed`, `disabled`, `selected`, with palette colors, `transparency`, `duration`, TweenService `easing` and `direction`.

Example: `{"palette":{"light":"#FFFFFF","dark":"#111111"},"root":{"type":"screen","id":"ui","children":[{"type":"text","id":"title","text":"Hello","textColor":"light","background":"dark"}]}}`.

Unknown keys, out-of-range values, duplicate ids and duplicate JSON keys are errors. A contrast ratio below 4.5:1 creates a warning. Diagnostics carry a JSON path and source line/column; positions are best-effort for repeated object names, while JSON decoding errors use exact parser positions.

Generated code must only display client data. Never authorize purchases, inventory grants or game-state changes based on LocalPlayer or UI handles. Studio visual and runtime testing is still required: Python tests cannot execute the Roblox engine.

API references: [GuiObject](https://create.roblox.com/docs/reference/engine/classes/GuiObject), [ScreenGui](https://create.roblox.com/docs/reference/engine/classes/ScreenGui), [TweenService](https://create.roblox.com/docs/reference/engine/classes/TweenService), [GuiService](https://create.roblox.com/docs/reference/engine/classes/GuiService), [UIScale](https://create.roblox.com/docs/reference/engine/classes/UIScale).
