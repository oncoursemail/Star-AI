# STAR Intelligence — source architecture

> Canonical public source: [oncoursemail/Star-AI](https://github.com/oncoursemail/Star-AI), main branch. This is a code map, not a claim that unmerged features are shipped. Refer to [REPOSITORY_GUIDE.md](REPOSITORY_GUIDE.md) for ownership and working rules.

```text
Windows desktop (STAR.exe / star_desktop.py)
  ├── React 19 + TypeScript + Vite UI (frontend/)
  │     └── restricted Qt WebChannel action bridge (star/react_shell.py)
  ├── Python app/controller (star/desktop_core.py)
  │     ├── local-first model loop (star/agent.py)
  │     ├── llama.cpp / local Qwen model setup (star/local_runtime.py, star/brain_setup.py)
  │     ├── project knowledge, memory and SQLite analytics (star/knowledge.py, star/memory.py, star/analytics.py)
  │     ├── scoped Roblox Studio MCP (star/studio.py, star/policy.py)
  │     └── selected media, integration and skill adapters (star/*.py)
  └── per-user persistent data outside application install (%APPDATA%/STAR)

Public website: frontend/ → build frontend/dist → GitHub Pages workflow
Windows packages: scripts/build_windows.ps1, installer/STAR.iss, Windows workflow
Updates: public oncoursemail/Star-AI GitHub Releases → SHA-256 checked Setup → install
Development: isolated branches + reviewable PRs, never silent agent self-merges
```

## Current shipping boundaries

- The canonical desktop and website share React frontend source. `star/desktop.py` remains as a legacy native GUI while the React interface matures. Do not create a second separate STAR product/UI.
- The app defaults to local inference and does not require LM Studio or a hosted model API key. Optional model and agent features on *unmerged* development PRs must not be described as shipped.
- Model responses and tool outputs are untrusted. `star/policy.py` and the WebChannel bridge enforce the configured capabilities; no prompt may bypass their permissions.
- Project-scoped chat/knowledge, local models and reference assets persist in the user's app-data profile, **not** in GitHub, public Pages, or the replaceable installed application folder.
- New skill generation/benchmarks/evaluations are bounded candidate workflows; tests and independently reviewed Roblox game results are required before calling them production-ready.

## Request layout and the model server's prompt cache

A CPU llama.cpp server reads new prompt tokens slowly but reuses, for free, the tokens of the previous request in the
same slot as long as the new request starts with the same bytes. Every model request is therefore laid out as
(`star/context_layout.py`, `star/agent.py`):

1. one system message: the rules, then the stable checkpoint (`system_prefix`). Plain chat gets the short
   `FAST_RULES`; any request with tools gets the full `RULES`.
2. earlier turns as real user/assistant messages in append-only order (`conversation_window`). The window is cut in
   segments measured from the first message of the chat, so it moves rarely instead of sliding every turn.
3. the new user message, followed by everything that changes per turn: retrieved notes, web sources, the selected
   Studio, mode and date. `star.agent.volatile_context` is the only place per-turn text enters a request; a new
   retrieval source appends one `(heading, text)` pair to `turn_sections` in `desktop_core.run_task`.

Rules that keep this working: never put per-turn text in the system message or in an earlier turn; trim history from
the oldest end in whole blocks; keep the tool list in a fixed order with rarely attached tools last (Qwen templates
render tools before the system text). `providers.llama_request_fields` adds `cache_prompt`, `preserve_thinking` and a
steady `id_slot` for the owner's own llama.cpp servers only; cloud providers never receive them. `star/warmup.py`
checks the selected server at start and sends the start of the open chat once, with `max_tokens=1`, so the first real
message does not pay for it; it writes nothing and any real request cancels it.
`scripts/measure_first_token.py` measures the effect against a live server.

## Paths worth preserving

| Path | Role |
|---|---|
| `frontend/` | React app and public website; desktop preview is not a privileged web session |
| `star/` | Python AI brain, local model, tool adapters, memory and GUI bridge |
| `tests/`, `evals/` | Regression safety and reproducible evaluation fixtures |
| `scripts/`, `installer/` | Desktop build, QA, installer and maintenance tooling |
| `.github/workflows/` | Windows build/release, public React Pages, tests and dependency checks |
| `docs/` | Research, release gates, architecture and integration guidance |
| `site/` | Historical static website kept for compatibility, not the deployed React source |

New work belongs on a task branch; read the [agent agreement](../AGENTS.md), inspect the open PRs, and never delete someone else's unmerged work to simplify the directory tree.
