# Luau quality: opt-in official analyzer as a second opinion

Research snapshot **2026-10-12**, using official source repositories and STAR's `star/next` branch. No model/brain or Roblox server was contacted, and no golden or holdout evaluations were opened.

## STAR baseline and primary sources

`star/luau_lint.py` is a token-pattern checker, not a parser. Its real Studio audit path is `star/roblox_craft.py:audit`, exposed to the assistant by `star/intelligence.py:LocalIntelligence.call('star_roblox_craft_audit', ...)`. The existing offline executable spec runner is `scripts/run_luau_specs.py`. [Roblox type checking](https://create.roblox.com/docs/luau/type-checking) and [Luau CLI](https://github.com/luau-lang/luau/blob/0.691/CLI/src/Analyze.cpp) distinguish static analysis from Studio runtime tests.

## Ranked candidates (licence, upkeep, strengths and tradeoffs)

| Tool | Upstream upkeep (GitHub pushed-at seen 2026-10-12), licence, no-admin installation | Additional defects vs STAR; concrete example | False alarms, speed and cost |
| --- | --- | --- | --- |
| **1. `luau-analyze --mode=strict` — selected** | [Official Luau](https://github.com/luau-lang/luau), pushed **2026-10-10**, **MIT**; [release 0.691](https://github.com/luau-lang/luau/releases/tag/0.691) has standalone ZIP binaries installable in a user-owned folder | In real STAR source `examples/roblox-templates/simulator/ReplicatedStorage/Shared/CostCurve.luau`, seed `local CostCurve = {` (unterminated brace) or insert `local forced: number = "bad"`; the original token checker misses both syntax and type mismatch. The pinned CI smoke runs both **mutations**, preserving the original code | Standalone does **not** know Roblox engine globals: generic `game`/`BasePart` errors must not be treated as proven gameplay defects. Measured time for three probes is printed in the smoke-job log; no overall inference impact measured |
| **2. luau-lsp** | [Official community project](https://github.com/JohnnyMorganz/luau-lsp) pushed **2026-10-12**, **MIT**, downloadable user-local binary/[editor extension](https://github.com/JohnnyMorganz/luau-lsp/blob/main/README.md) | Roblox-aware symbols and Rojo sourcemaps could analyze the existing `CheckpointService` `BasePart`/`Player` signatures correctly | Requires language-server lifecycle, workspace and sourcemap; false positives on incomplete DataModel. Startup/speed on STAR **unmeasured** |
| **3. Selene** | [Official project](https://github.com/Kampfkarren/selene), pushed **2026-10-01**, **MPL-2.0**; [documentation](https://kampfkarren.github.io/selene/), user-local binary | Style/policy lint checks complementary to STAR's `wait`, `FindFirstChild` and RemoteEvent heuristics | Needs Roblox standard-library config, can warn on unknown globals; tool describes itself as fast but no STAR speed measurement |
| **4. StyLua** | [Official project](https://github.com/JohnnyMorganz/StyLua), pushed **2026-10-12**, **MPL-2.0**; [release v2.6.0](https://github.com/JohnnyMorganz/StyLua/releases/tag/v2.6.0) user-local executable | Formats/parses Luau; would catch malformed brace but **not** the annotated number/string type mismatch. Generated project builder opt-in is already [draft PR #188](https://github.com/oncoursemail/Star-AI/pull/188) | Formatting differences are not game bugs; no measured Luau correctness gain yet |

## Why choose the official analyzer

Lowest incremental integration cost: STAR's [pinned Luau template workflow](../../../.github/workflows/luau-specs.yml) already verifies `luau-ubuntu.zip` for release **0.691 (2025-09-15)** with published SHA-256 `9b7699968c911beb3781f682c6be298440879ae279ff352d36dd58603418de2b`. The upstream [0.691 analyzer implementation](https://github.com/luau-lang/luau/blob/0.691/CLI/src/Analyze.cpp) supports strict mode and diagnostics of the form `file(line,column): Kind: message`. This is a **fixed older version**, not a claim to use the latest Luau.

## Operator configuration and safeguards

- **OFF by default:** only `STAR_LUAU_ANALYZE=on` activates it. `lint(code, external=False)` forces the original path; the `LocalIntelligence.call` Studio craft audit uses the same opt-in setting. Off means no binary lookup or subprocess and byte-identical results (offline tests).
- Executable resolution: `STAR_LUAU_TOOLS_DIR/luau-0.691/luau-analyze` (`.exe` on Windows), else `luau-analyze` already on PATH. The PATH alternative is not assumed checksum-pinned. The runtime **never downloads or installs** software; user-owned folder or PATH requires no administrator access.
- On opt-in, source is staged in a fixed-named temporary `.luau` file, never executed or written to the owner's repository. The analyzer gets a fresh temporary working directory, a six-second timeout, a minimal environment with no provider credentials, a 20,000-byte source cap and 48,000-byte diagnostic cap.
- Exact CLI diagnostic locations and types are mapped to STAR `Finding` entries: syntax = error, type = warning, other lint = review; no false engine-global findings for known Roblox names. A missing binary or failed run emits a single generic notice per process, then the original checks remain available. No raw external errors or local paths enter the model's prompt.
- The real Studio craft audit checks **at most three scripts**, retaining existing read-only/no-Luau-execution behavior and disclosing truncated analysis. Findings include the actual inspected script path, `certainty: analyzer`, and official [Luau type-checking docs](https://create.roblox.com/docs/luau/type-checking).

## Reproducible verification and limits

Recorded-output tests exercise both `lint()` and the real `LocalIntelligence.call('star_roblox_craft_audit', ...)`, including missing binary, timeout, safe error reporting, strict diagnostics, engine-global false alarms, pinned-path preference and OFF behavior. They work without binary downloads or credentials.

An additional `luau-quality-smoke` CI job downloads the **same** 0.691 official ZIP as the existing spec runner and checks the same published SHA-256, then runs the adapter against **three STAR-derived snippets**: unmodified CostCurve, syntactically broken CostCurve, and type-mismatched CostCurve. It prints counts of added findings and median elapsed milliseconds. No benchmarking of Selene, StyLua or luau-lsp is claimed.

**Certain only after green CI:** The selected binary actually runs and recognizes injected syntax and type defects missed by baseline pattern diagnostics. **Unknown:** defects present in unmodified STAR examples, full false-positive rates with Roblox APIs, real Studio gameplay correctness and improvement in model answer quality. The unmodified example's findings are printed in CI for inspection.

**Smallest next step:** Independently compare a few analyzer warnings to Studio's actual typed engine APIs in a disposable place; then evaluate opt-in against a fixed practice set without touching the golden or holdout suites.

**Pinned CLI caveat (2026-10-12):** In [the initial real CLI smoke](https://github.com/oncoursemail/Star-AI/actions/runs/38254718008), `luau-analyze --mode=strict -` returned exit 0 and no diagnostics for deliberately malformed source. Unlike a captured-output unit test, this exposes a version-specific limitation: the adapter now checks a disposable `star-check.luau` file rather than relying on stdin. A green follow-up smoke must confirm parser/typechecker execution.
