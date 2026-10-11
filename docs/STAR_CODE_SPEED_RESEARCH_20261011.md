# STAR coding speed and repository understanding research — 2026-10-11

**Status:** unmerged draft candidate targeting star/claude-integration-20261010. This is a read-only local-workspace search enhancement, **not** new model training or a demonstration that STAR can autonomously create arbitrary AAA games. It must pass independent review and Windows acceptance before shipping.

## Source audit

- star/agent.py exposes workspace_list, workspace_read, workspace_search and workspace_write when the owner has selected a local workspace. Existing workspace_write permission remains a separate explicit edit mode.
- star/context_layout.py and star/warmup.py already optimize stable llama.cpp prompt prefixes and first-token behavior; rebuilding that path would duplicate work. A CPU/GPU model's decode rate is a separate bottleneck.
- star/repo_intelligence.py is a **different** read-only public GitHub adapter pinned to STAR's public main branch; it is not the user's local workspace index.
- Previously, workspace_search used Path.rglob over the complete workspace and decoded all qualifying files one by one. It did not prune generated directories before scanning. It found matching text but did not return code declarations/signatures.
- Pending PRs address fast model routing, Studio tools and security. This proposal intentionally avoids those overlapping modules.

## Implemented candidate: selective file and symbol search

An optional "mode" parameter on workspace_search supports "text" (default) and "symbols" without attaching another separate tool schema to every model call. Symbol mode returns ranked, compact declarations with file path, 1-based line, kind and signature so the model can identify likely relevant code before calling workspace_read.

- Python: real ast.parse for module functions/classes and class methods, including multiline signatures; never import or run the inspected project.
- Luau/Lua, TypeScript/JavaScript, GDScript, C#: conservative line recognizers for declarations. **Heuristic only**; false positives and missed declarations are possible. Confirm source by reading the file and running the appropriate language diagnostics before edits.
- Text: case-insensitive substring matches, retaining existing query and matches shape. Scope intentionally narrows to common source/document extensions and excludes generated, hidden, symlink and undecodable files.
- Safety: reuse Workspace.resolve checks; skip generated directories and obvious secret-file names; stop after 3,000 eligible files / 1,500 directories; cap result count at 80; report incomplete results. No shell, subprocess, network, package installation, project code execution or file writes.

Example workspace_search request: {"query":"inventory save","mode":"symbols"}. Result identifiers are **navigation hints**, not evidence of successful analysis, compilation or integration tests. For large files or scans, STAR should disclose truncation. The model can call workspace_read for the exact source of the likely match.

### Synthetic benchmark — do not generalize to whole-agent speed

Offline fixture on the execution container: 25 small source files + 1,500 generated Python files beneath node_modules, absent substring query, five warm runs measured with time.perf_counter. Median original implementation: **0.0916 seconds**. Median new implementation: **0.0026 seconds**, ~35.4x faster on this specifically favorable case. It does **not** measure GPU tokens/second, TTFT, end-to-end task completion, retrieval recall, or real Windows/Roblox projects. Test those before making speed claims in STAR's marketing.

Twelve isolated unit tests cover multilingual signatures, Python AST, text compatibility, excluded directories, symlinks, invalid UTF-8, malformed code, edits, validation, scan caps, read-only nonexecution, and the existing write gate.

## Deep research: next improvements to implement in order

| Priority | Technique / tools | Concrete STAR deliverable | Proof required |
| --- | --- | --- | --- |
| P0 | Aider-style token-budgeted repo maps + Tree-sitter | Incremental, project-scoped symbol index by file hash; rank symbols by task and import graph within a 1–2k token retrieval budget | Useful-hit@10, false positive rate, edit success on held-out tasks, invalidation after edits |
| P0 | Safe plan → focused patch → independent tests → diff review | Patch staging with file-level undo, syntax gate, impact-based test selection and human final approval | Negative tests for lost edits, hallucinated success and mutation during tests |
| P0 | llama.cpp live profiling, prompt prefix reuse and bounded speculative decoding | Per-model cold/warm TTFT, prompt-eval tokens/s, decode tokens/s and cache hit/miss telemetry | p50/p95 measured on owner's local machine, GPU/VRAM budget and cancellation |
| P1 | ripgrep (optional pinned executable) | Ignore-aware search with literal argv, path allowlist, timeout and Python fallback | Hash/provenance verification, Windows permission & injection tests |
| P1 | Tree-sitter and language servers | Replace approximate Luau, TS/JS and C# declaration regex with parser/LSP metadata and incremental updates | Parser error recovery, version pins, fake workspace tests, no implicit downloads |
| P1 | Rojo, Rokit, luau-lsp, StyLua and Selene | Safe source sync, pinned Roblox toolchain, sourcemap-aware diagnostics, formatter and linter checks | Source conflict resolution; scoped Studio permissions; no unrestricted code execution |
| P1 | Ruff, pytest, Vitest and engine-native diagnostics | Deterministic relevant-test feedback after edits; full suite before merge | tests stay independent of proposed patch; no fabricated green states |
| P2 | Reviewed local learning from approved edits and failures | Better retrieval/routing through owner-approved lessons and confidence-calibrated outcomes | Held-out evaluations, rollback and independently owned promotion gate |
| P2 | Parallel **read-only** research teams | Overlap independent I/O while serializing resource-constrained local inference and writes | End-to-end p95, RAM/VRAM usage, cancellations and ownership conflicts |

### Important architectural choices

1. Do not send the model entire source trees by default. Retrieve signatures and relevant snippets, confirm dependencies, and only then read/edit exact files. This can reduce prompt tokens and lower the chance of editing the wrong module.
2. Use a stable prompt prefix for llama.cpp where supported; avoid inserting timestamps or rapidly changing retrieval snippets before stable instructions. OpenAI cloud prompt caching has different settings; do not assume cloud APIs match local server behavior.
3. AST/LSP parsing is data analysis; never execute a user's repository during indexing. Tool binaries must be reviewed, pinned and launched under the user's explicit scoped permission.
4. Testing is independent of the editing agent. A green result requires real executed test logs, not a model statement. Do not use one public coding benchmark as proof of intelligence.
5. Preserve safety, license provenance, editable assets, the Roblox owner approval gate, user workspace isolation and data privacy. Increasing autonomy is **not** permission to ignore verification.

## Research references and their applicability

- Aider's graph-ranked repository map and token budget: https://aider.chat/docs/repomap.html
- Tree-sitter incremental parsing library: https://tree-sitter.github.io/
- ripgrep ignore behavior and binary skipping: https://github.com/BurntSushi/ripgrep
- llama.cpp server, cache and speculative decoding metrics: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Cloud prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Roblox Luau gradual type checking: https://create.roblox.com/docs/luau/type-checking
- Luau LSP + Rojo sourcemap support: https://github.com/JohnnyMorganz/luau-lsp
- StyLua formatter: https://github.com/JohnnyMorganz/StyLua
- Rokit toolchain pinning: https://github.com/rojo-rbx/rokit
- Ruff lint/format: https://docs.astral.sh/ruff/
- OpenAI 2026-07-08 analysis found material benchmark defects in about 30% of SWE-bench Pro tasks: https://openai.com/index/separating-signal-from-noise-coding-evaluations/ ; use a separately curated, private, human-reviewed suite as primary engineering evidence.

## Acceptance criteria before merging

1. Run python -m compileall -q star main.py and python -m pytest -q; run frontend Vitest if frontend code changes. The isolated tests require no network, GPU, keyring or Roblox account.
2. Validate existing workspace_read/write capabilities did not regress and the new mode is available to tool-enabled Agent users only when a workspace is selected.
3. On Windows, test 30 real held-out code navigation prompts with Luau/Rojo/TypeScript/Python projects. Compare symbol search useful-hit@10, p50/p95 search latency, total agent tokens, task pass rate, time-to-first-visible-token, and verified repair cycles against the existing system.
4. Manually review scope escapes, symlink races, prompt injection in code comments, truncation reporting, model claims and potential code that is excluded by file extension. This candidate is not a security boundary against a hostile process concurrently mutating the filesystem.
5. An independent reviewer must approve any eventual CI/workflow or security-policy changes. No PR is merged or marked ready automatically.
