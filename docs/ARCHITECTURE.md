# STAR Genesis research build v0.2 — current architecture

```text
Windows 11 CLI
    │
    ├── Local LM Studio HTTP 127.0.0.1:1234/v1 (model must support images + tool calls)
    │       └── limited agent loop, basic compaction
    │
    ├── Roblox built-in MCP stdio (selected sandbox Studio ID)
    │       └── allowlisted inspection and optional auto-edit tools
    │
    ├── SQLite checkpoints + candidate/reviewed knowledge + immutable artifacts
    │       ├── local JSON task transcripts
    │       └── non-executing task DAG and ownership checks
    │
    └── GitHub App installation JWT → installation access token
            └── source-file updates on star/* branches → draft PR
```

The CLI has no direct shell tool for the model, no package-installer tool, no public web browser, and no unrestricted GitHub action tool. This is a deliberately bounded first version, not a complete self-improving application.

The current `--edit` permission applies to the specified disposable Studio instance and a restricted tool allowlist. `execute_luau` is **not** exposed by default, because arbitrary Luau is not confined by a mere Studio instance path. It requires `--edit --unsafe-luau` and remains unsafe for production or valuable places. Tool permissions do not create a process sandbox.

Compaction archives earlier messages and preserves the original prompt and images, but replaces older working context with a lossy checkpoint. A new task receives the saved project checkpoint and keyword-matching **reviewed** project notes, but it cannot yet automatically search exact earlier transcript snippets or re-inject the pixels of historical images. Original image references are stored locally for future retrieval.

A true self-building STAR will require **separate source worktrees, a guarded local code-editing tool, tests that workers cannot rewrite, integration review, GitHub App branch upload, and rollback**. Building those gates is the next engineering phase, not a feature we claim as complete today.

## Self-building prototype

`star/selfbuild.py` uses LM Studio tool calling on an **isolated Git worktree** and permits `list_skill_files`, `read_skill_file`, `write_skill_file`. All file paths are checked against a narrow allowlist and resolved to prevent symlink escapes. Generated Python is syntax checked only (not run). The worktree is committed to an independent development branch. If GitHub App credentials are configured, it can publish that candidate in a draft PR. This is **source-generation autonomy**, not self-training of model weights, safe execution of arbitrary generated code, or validated new intelligence.

## New research-specific components

- `star/knowledge.py`: reviewed/candidate project notes, provenance and SHA256 content-addressed original artifact files. Basic keyword retrieval only.
- `star/orchestration.py`: accepts a task dependency graph with owned read/write paths, rejects missing dependencies, cycles and colliding concurrent resources. No active agents are launched by it.
- `star/evals.py` + `evals/roblox_cases.json`: 32 defined test cases and summaries. All 32 remain NOT_RUN until separate real-world harnesses supply evidence.
- `.github/workflows/`: read-only CI token defaults and a dependency audit. Cloud CI has not been run from this research environment.
- `docs/`: 9,000-word deep research report, verified MCP tool matrix, GitHub backlog and autonomy guidance.

This source was tested offline with fakes and a temporary local Git repository. A Windows Studio/model/App trial remains mandatory.
