# STAR improvement research, October 2026

Status: research plus two small implemented items (this branch, `research/star-improvements`). Written 2026-10-13 against
`origin/star/next` at `64c1982c` and the ~80 open PRs of that day. Everything below is a proposal unless it says
**implemented**. Nothing here was measured on brain 1, brain 2 or the owner's PC: every number is a published or
upstream number, not a STAR measurement.

## How this list was made

1. Inventory of what STAR already has, plans or measured and rejected: every `star/*.py` module on `star/next`,
   `server/` (brain presets, starkb, night school, GPU pilot), the planning docs (`RESEARCH_ROADMAP.md`,
   `FRONTIER_*`, `GITHUB_FRONTIER_BACKLOG.md`, `ISSUE_BACKLOG.md`, `STAR_CODE_SPEED_RESEARCH_20261011.md`,
   `docs/agents/*`, `docs/research/*`) and the research docs of open PRs #278, #306, #325 and #275.
2. Web research (model cards, llama.cpp docs and PRs, arXiv, vendor changelogs). The search budget ran out part-way;
   claims that could not be re-checked against a primary page are marked **[unverified]**.
3. Anything already DONE, already in an open PR, or already MEASURED AND REJECTED (MTP/DFlash on star-fast, KV q8_0,
   ik_llama.cpp, one instance per NUMA node, a 122B tier, self-consistency voting) is left out. Items that are
   PLANNED but not started are kept only when this research adds a concrete, cheaper design, and are marked
   "(planned as ...)".

Score = impact (1-5) x ease (1-5). Impact means "more correct Roblox/Luau work per owner-minute"; ease counts code,
risk and the measurement it needs on the real machines.

## Ranked list

| # | Idea | Area | Impact | Ease | Score | Status |
|---|---|---|---|---|---|---|
| 1 | Whitespace-tolerant find/replace edits + `workspace_edit` tool | Agent tools | 4 | 5 | 20 | **implemented** |
| 2 | Lint-on-edit: written Luau comes back with lint findings | Agent tools | 4 | 5 | 20 | **implemented** |
| 3 | n-gram speculative decoding for code-rewrite requests (+ LF prompts) | Inference | 4 | 4 | 16 | listed in server-inference §8, never measured |
| 4 | Rights-clean distillation: RFT from the local Apache-2.0 brain into a 4B QLoRA specialist | Self-improvement | 5 | 3 | 15 | new (unblocks W10b) |
| 5 | Project rules files (AGENTS.md, nested; `.cursorrules`, `CLAUDE.md` fallbacks) | UX / context | 3 | 5 | 15 | absent |
| 6 | JSON-schema / llguidance-constrained tool arguments for star-quick and Studio steps | Inference / tools | 4 | 3 | 12 | absent |
| 7 | Tool examples inside tool definitions (Studio MCP paths, CFrame, Vector3) | Tools | 3 | 4 | 12 | absent |
| 8 | Lune tier-1 test runner + LuauLeetcode as an outside benchmark | Evaluation | 4 | 3 | 12 | Lune scouted only |
| 9 | Reasoning budget for star-deep and thinking requests | Inference | 3 | 4 | 12 | absent |
| 10 | File-edit checkpoints and rewind, joined to the Studio undo journal | UX / safety | 4 | 3 | 12 | (planned as "patch staging with file-level undo", P0) |
| 11 | Qwen3.8-Flash-Next GSQ-RCO Coder GGUF as a code-route candidate | Models | 4 | 3 | 12 | new |
| 12 | Unsloth Dynamic `UD-Q4_K_XL` instead of plain `Q4_K_M` for star-fast | Models | 3 | 4 | 12 | new |
| 13 | Rojo `syncback`: "import my existing place" | Roblox | 3 | 4 | 12 | absent |
| 14 | `luau-lsp analyze --sourcemap` as the type gate | Roblox | 4 | 3 | 12 | (planned, RESEARCH_ROADMAP §8) |
| 15 | Per-task flip rate and a continuous secondary metric in the eval gate | Evaluation | 3 | 4 | 12 | new on top of `eval_stats.py` |
| 16 | Context meter in tokens and seconds-to-read, using `/tokenize` | UX | 3 | 3 | 9 | absent (budgets are characters) |
| 17 | Code-embedding A/B (CodeRankEmbed 137M, jina-code-0.5b) for user code and worked examples | Retrieval | 3 | 3 | 9 | absent |
| 18 | `--n-cpu-moe` so the PC runs the same 35B-A3B brain on 8 GB VRAM + RAM | Models | 3 | 3 | 9 | absent |
| 19 | Parakeet-TDT-0.6B-v3 in the voice ASR benchmark | Voice | 2 | 4 | 8 | absent |
| 20 | Structured fixed-camera Studio shots for "look" steps | Vision / Studio | 3 | 3 | 9 | check against Studio Lab #268/#292 first |
| 21 | GRPO on a 1.7-4B model with analyzer/lint rewards | Self-improvement | 3 | 2 | 6 | absent |
| 22 | Owner hooks (`.star/hooks.json`, PostToolUse/Stop) | UX | 3 | 2 | 6 | absent; process-execution policy review needed |
| 23 | FIM / next-edit autocomplete (Luau-Qwen3-4B-FIM, Zeta2) | UX | 2 | 1 | 2 | absent; STAR has no editor surface |

---

## 1. Whitespace-tolerant find/replace edits (**implemented**)

**Problem.** STAR's Studio script edits (`studio_loop.GuardedStudio._edit_script`) refused any `old_string` that was
not a byte-exact substring, and the workspace had no edit tool at all, only whole-file `workspace_write` (at 8-10
tok/s on star-fast, rewriting a 300-line file costs minutes). Small models very often reproduce the code correctly
but the indentation wrong.

**Evidence.**
- Aider's edit-format benchmarks: flexible patching (ignoring leading whitespace, re-indenting) was introduced
  because exact matching failed far more often with weaker models (https://aider.chat/docs/more/edit-formats.html,
  https://aider.chat/docs/benchmarks.html).
- SWE-agent ablation (arXiv 2405.15793, Table 3): removing the edit command entirely drops SWE-bench Lite from
  18.0% to 10.3%; an edit tool is worth more than any other single interface element.
- Diff-XYZ (arXiv 2510.12487) and arXiv 2510.13859: small open models gain little from fancy diff formats and
  burn their retries on diff-application failures, so the cheapest gain is a more forgiving matcher, not a new
  format.

**What was built.** `star/edit_match.py` (pure, no I/O):
- `apply_edit(source, old, new, replace_all=False)` tries exact, then the file's `\r\n` line endings, then
  whole-line matching that ignores trailing whitespace and a *uniform* indentation shift (the new text is
  re-indented by the same shift, so the file keeps its own style).
- Every strategy must find exactly one place; two candidate places are refused as ambiguous. Partial-line text is
  never matched loosely, and relative indentation must agree.
- A miss returns the closest run of lines (difflib, similarity >= 0.5) so the next attempt can copy it.
- `workspace_edit` tool in `star/workspace.py` (same edit-mode gate as `workspace_write`, via a new
  `WRITE_TOOLS` set that `star/agent.py` now uses in both of its checks); Studio `multi_edit` goes through the same
  matcher. Behaviour change: an exact `old_string` found twice without `replace_all` is now refused as ambiguous in
  Studio instead of silently editing the first occurrence.
- Tests: `tests/test_edit_match.py` (21 cases, including the Studio path through `tests/studio_fake.py`).

**Next step to prove it.** Count `Edit refused: old_string ...` tool results in the audited event log before and
after, and run the 50-task suite's edit tasks through the paired gate (`star/eval_stats.py`).

## 2. Lint-on-edit (**implemented**)

**Evidence.** SWE-agent (arXiv 2405.15793): the same agent without the lint check after edits drops from 18.0% to
15.0% on SWE-bench Lite. Claude Code and Codex now ship PostToolUse hooks mostly used for exactly this
(https://code.claude.com/docs/en/hooks).

**What was built.** `workspace_write` and `workspace_edit` on a `.lua`/`.luau` file return up to 8 findings from
STAR's own offline `luau_lint.lint()` (rule, line, message, fix) in the tool result. Advisory only: the write has
happened, a checker exception never fails the call, and non-Luau files are unchanged.

**Follow-ups.** Add `luau_analyze` findings when that opt-in checker is enabled (it already runs offline), and the
same for Studio `multi_edit` results (needs a small change to how `studio_loop` reports edit results).

## 3. n-gram speculative decoding for code rewrites

STAR measured MTP and DFlash as slower on star-fast and correctly turned them off. n-gram drafting is a different
mechanism: no draft model, the "draft" is a lookup of text already in the prompt or earlier output, so a rejected
draft costs one verify batch and nothing else. It only pays when the output repeats input, which is precisely a
whole-file rewrite, a fix-this-function answer, or a Studio script re-emitted with small changes.

**Evidence.**
- llama.cpp `docs/speculative.md`: `--spec-type ngram-mod` (plus `ngram-simple`, `ngram-map-k`, `ngram-map-k4v`,
  `ngram-cache`), shared 16 MB hash pool across slots.
- PR #18471: rewriting a Python file, gpt-oss-120b 181 -> 446 tok/s (acceptance 0.77); Qwen3-235B with heavy RAM
  offload 11.8 -> 21.0 tok/s.
- PR #19164: Devstral 123B on an aarch64 CPU, **2.3 tok/s with CRLF prompts vs 29.8 tok/s with LF** (acceptance
  0.11 vs 0.83).
- PR #29924 (merged 2026-10-04) fixed a regression where drafts near the end were fully rejected at temperature > 0;
  Qwen3.6-35B-A3B acceptance 0.377 -> 0.514 on a GPU. **[unverified]** whether b11541 contains it; check the commit.
- Unknown for STAR: a MoE verify batch on this CPU touches more experts than a single token, which is what hurt MTP.
  The acceptance rates above are much higher than MTP's, so the trade may differ; only a measurement decides.

**Sketch.**
- `server/brain/models.ini`: a commented, measured-only preset alias (e.g. `star-code-edit`) of the star-fast
  weights with `spec-type = ngram-mod` and `spec-draft-n-min` > 0 (one report of constant resets at 0).
- Measure with the existing `server/brain/bench/ab.sh` on three prompt kinds: free chat, "rewrite this file with X",
  Studio `multi_edit` follow-ups. Adopt only for the edit kind if it wins there.
- Client side: normalise file content to LF before it enters the prompt (workspace reads already do; Studio reads
  should be checked), and route "rewrite/fix this code" prompts to the alias in `brain_router.py`.

## 4. Rights-clean distillation into a small specialist

W10b (generator QLoRA) is blocked on "no rights-clean set of verified worked examples" because night school's 136
examples answer prompts that Claude/Codex wrote. The way out: let STAR's own Apache-2.0 brain write both the tasks
and the answers, and keep only what a harness-owned checker verifies.

**Evidence.**
- ReST-EM (arXiv 2312.06585) and STaR (arXiv 2203.14465): sample many, keep the verified, fine-tune, repeat; gains
  over human-data-only SFT, saturating after about 2-3 rounds **[the saturation detail is unverified]**.
- Qwen3.6-35B-A3B and Mellum2.1 are Apache-2.0 (model cards), so their outputs carry no provider-terms problem;
  the GPU pilot already used Qwen3.5-9B-generated queries on this basis (`docs/agents/gpu-training-pilot.md`).
- 8 GB fit: Unsloth lists QLoRA minimums of ~6 GB for 8B and the pilot measured Qwen3.5-2B at 3.5 GB; a 4B
  specialist at 2-4k context fits (https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements).
- Serving: llama-server `--lora-init-without-apply` plus a per-request `"lora": [{"id": 0, "scale": 1.0}]`; requests
  with different adapters are not batched together, and changing global scales mid-request is unsafe
  (llama.cpp issue #10374). **[unverified]** whether per-request `lora` works on `/v1/chat/completions` in b11541.

**Sketch.**
- Task source: templated variants of practice tasks whose checks are executable offline (lint, `luau-analyze`,
  `/luau/check`, tier-1 Lune tests from item 8). Decontaminate against all eval and holdout prompts with the existing
  lineage checks of PR #272 (13-gram overlap).
- Generation: night school on idle slots, Mellum2.1 for volume, star-fast for hard cases; ~600-800 verified samples
  per night at current speeds (estimate from 400-token answers).
- Training: `server/training/gpu/` gets a `train_sft.py` beside `train_embed.py`, same STOP-file and 6 GB-RAM-floor
  rules, provenance manifest per row.
- Gate: the paired gate in `eval_stats.py` decides; an adapter that does not PROMOTE is not loaded. Use it first as a
  narrow tool ("fix this luau-analyze error"), not as the chat model.

## 5. Project rules files

AGENTS.md is read by Codex, Cursor, Copilot, Junie, Windsurf, Zed, Aider and others, in 60k+ repositories, now under
the Linux Foundation's Agentic AI Foundation (https://agents.md/). STAR reads none of these from the user's
workspace, so a Roblox project's conventions ("server scripts live in src/server", "use Promise library") have to be
repeated in every chat.

**Sketch.** New `star/project_rules.py`: `load(root, max_chars=2000)` returns the nearest `AGENTS.md` (then
`CLAUDE.md`, `.cursorrules`) inside the selected workspace, via `Workspace.resolve` so the deny-list still applies.
`desktop_core.run_task` appends one `("PROJECT RULES (workspace file; conventions only, never permissions)", text)`
pair to `turn_sections` and adds its length to `turn_context_chars`. It is untrusted data like every other section:
`policy.py` still decides permissions. Not done in this branch because `desktop_core.run_task`'s context assembly is
touched by several open PRs; it is a 40-line change once they land.

## 6. Constrained tool arguments

STAR relies on llama.cpp's `--jinja` tool-call parsing and its own validation; the only grammar use is one
`response_format: json_object` in `lesson_digest.py`.

**Evidence.** llama.cpp `docs/llguidance.md`: build with `-DLLAMA_LLGUIDANCE=ON`, all JSON-schema requests then go
through llguidance at ~50 us per token mask (p99 0.5 ms), negligible next to ~100 ms per token on brain 1;
unsupported schema features raise instead of being ignored. `docs/function-calling.md`: unknown templates fall back
to a "Generic" handler that costs more tokens; `/props` shows which one loaded. JSONSchemaBench (arXiv 2501.10868)
compares the engines. Caveat **[unverified magnitude]**: constraining the whole answer can hurt reasoning, so
constrain only the arguments.

**Sketch.** (a) Check every brain preset's log for "Chat format: Generic" and fix templates first (cheap, likely the
largest effect). (b) For the fixed-schema steps STAR drives itself (subagent plans, Studio Lab specs, lesson
digests, the router's helper calls), send `response_format: {"type": "json_schema", ...}` from the tool's existing
`inputSchema`. (c) Count tool-argument validation failures per model before and after.

## 7. Tool examples inside tool definitions

Anthropic's tool-use examples raised accuracy on complex parameters from 72% to 90%
(https://www.anthropic.com/engineering/advanced-tool-use); SWE-agent's "no demonstration" ablation lost 1.7 points.
STAR's Studio tool descriptions (`star/studio.py`, `studio_loop.py`) carry no example call. **Sketch:** one canonical
call per Studio tool where the arguments are error-prone (`file_path` like `game.ServerScriptService.Main`,
`execute_luau` datamodel types, Vector3/CFrame strings), appended to the description text. Keep the tool list
byte-stable (the examples are fixed text), so the prompt cache is unaffected.

## 8. Lune tier-1 tests and an outside benchmark

STAR runs Luau unit tests in the standalone VM on the server sandbox, and full behaviour in Studio. Missing is a
seconds-fast tier with a Roblox-shaped library for pure-logic modules, and any outside Luau benchmark.

**Evidence.** Lune 0.11 (Luau 0.740): standalone runtime with fs/stdio and a `roblox` library for place/model files
and Instances, no physics (https://github.com/lune-org/lune/releases). Jest-Lua still runs only inside Roblox
(https://github.com/jsdotlua/jest-lua). LuauLeetcode (https://huggingface.co/datasets/TorpedoSoftware/LuauLeetcode)
has ~2.6k problems with unit tests and a test split of 226 **[licence to check before use]**; no independent scores
exist for the Luau fine-tunes trained on it.

**Sketch.** Run the LuauLeetcode test split once through `star.evals` as an outside, contamination-checked number
(server sandbox, never the PC). Add a Lune runner to `eval_sandbox.py` only for tasks that need the `roblox` library
offline. Both feed item 4's verifier.

## 9. Reasoning budget

`llama-server --reasoning-budget N` with `--reasoning-budget-message` caps thinking tokens and tells the model to
finish (llama.cpp server README). star-deep runs at 2.3-5.5 tok/s; an unbounded think of 3,000 tokens is 10-20
minutes. **Sketch:** set a budget on the star-deep preset (e.g. 1,500) and on any thinking-mode request STAR makes,
measure answer quality on the creation suite with and without.

## 10. File-edit checkpoints and rewind (planned as P0 "patch staging with file-level undo")

Claude Code snapshots files before every prompt, keeps 100 checkpoints, and offers restore code / conversation / both
plus "summarize from here" (https://code.claude.com/docs/en/checkpointing); Cursor's CLI added `/checkpoint` in
July 2026 **[secondary source]**. STAR has undo for chats, lessons and Studio edits, not for workspace files.
**Sketch:** `Workspace._replace` (added in this branch) is now the single write path; before replacing, copy the old
bytes into a content-addressed store under the app-data profile keyed by conversation and turn. A "Rewind this turn"
action restores the files of that turn and, through the existing journal, its Studio edits.

## 11. Qwen3.8-Flash-Next (GSQ-RCO Coder) as a code-route candidate

Qwen3.8-Flash-Next: ~125B total, 6B active, plus 51B of n-gram embedding parameters that are a table lookup; card
scores SWE-bench Pro 62.5 (Qwen3.8-27B 61.7, Qwen3.6-35B-A3B 49.5), LiveCodeBench v6 91.9. ISTA-DASLab's GSQ-RCO
GGUF "Coder" variant keeps 256 of 512 experts at 58.4 GB plus a 28.8 GB n-gram shard, standard GGUF
(https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF). Licence `qwen-community-1.0`, not Apache:
read it before any distillation use (item 4). **No CPU speed figure exists**; 6B active suggests roughly half of
star-fast's speed **[estimate]**. **Sketch:** download to `models-candidates`, add a `ram-gb`-checked preset, run the
50-task suite and the paired gate against star-fast. Keep only if it wins on quality per minute, not quality alone.

## 12. Unsloth Dynamic quant for star-fast

Unsloth's Dynamic GGUFs calibrate on real data and keep sensitive layers at higher precision; for Qwen3.6-35B-A3B
they claim the size/quality Pareto front in 21 of 22 sizes (https://unsloth.ai/docs/models/qwen3.6). Their KLD
table for Qwen3.6-27B: 4-bit 0.0227 vs MXFP4 0.0479, so MXFP4 only for natively-MXFP4 models. **Sketch:** same RAM
class, swap `Q4_K_M` for `UD-Q4_K_XL`, measure tok/s with `bench/validate.py` (I-quant-style tensors can decode
slower on CPU) and quality with the paired gate.

## 13. Rojo syncback

Rojo 7.7 `rojo syncback project --input place.rbxl` pulls an existing place into files, with `syncbackRules`
(https://github.com/rojo-rbx/rojo/releases). STAR already pins Rojo 7.7.1 (`star/roblox_place.py`). **Sketch:** an
"Import an existing place" action that runs syncback into a new workspace folder (owner-chosen file, never a live
game), then points `workspace` at it, so every workspace tool, repo map and lint applies to existing projects.

## 14. luau-lsp analyze with a sourcemap (planned)

luau-lsp 1.70.1 (2026-09-27): `luau-lsp analyze` resolves string requires with a Rojo sourcemap and knows the Roblox
API definitions, unlike bare `luau-analyze` (https://github.com/JohnnyMorganz/luau-lsp/releases). STAR's own CI
smoke showed bare `luau-analyze` in stdin mode returning 0 on malformed source. **Sketch:** a `star/luau_lsp.py`
twin of `luau_analyze.py` behind the same opt-in, fed by `rojo sourcemap` for Rojo workspaces; add its findings to
item 2's lint-on-edit result.

## 15. Flip rate and a continuous metric in the eval gate

`eval_stats.py` already does paired sign tests, cluster bootstrap and MDE, and says INCONCLUSIVE honestly. Two
cheap additions from AI2's "Signal and Noise" (arXiv 2508.13144, 30 benchmarks x 375 models): (a) record each task's
flip rate across repeated unchanged baseline runs and report/weight down the noisiest tasks; (b) a continuous
secondary metric (fraction of a task's checks passed, analyzer error count), which carries more signal per task than
pass/fail. Anthropic's "Adding Error Bars to Evals" (arXiv 2411.00640) gives the sample sizes: at a 15% flip rate,
detecting +5 points needs about 470 paired tasks **[derived by the researcher, not quoted]**, so growing the suite
with verified variants (item 4's task generator) matters more than any gate change.

## 16. Context meter in tokens and seconds

Budgets are characters (`model_context_char_budget`). llama-server exposes `/tokenize`; at a measured 60-71 tok/s
prompt reading, the useful number for the owner is "seconds to read this turn". **Sketch:** tokenize the assembled
request once per turn (cached for the stable prefix), show tokens and estimated seconds in the composer, and use the
real token count for trimming instead of a character estimate.

## 17. Code-embedding A/B

Only the docs embedder exists (embeddinggemma-300m, fine-tuned ft1 pending deploy). For user code and worked
examples: CodeRankEmbed 137M (MIT, CoIR 60.1) and jina-code-embeddings-0.5b (MTEB-Code 78.72; Qwen3-Embedding-0.6B
74.69) (https://huggingface.co/nomic-ai/CodeRankEmbed, arXiv 2508.21290). **Sketch:** run the starkb eval harness
with each as the vector side for the worked-examples store only; no change to the docs index.

## 18. The 35B-A3B brain on the owner's PC

`--n-cpu-moe N` / `-ot` keeps routed experts in system RAM and attention plus shared experts on the GPU; Unsloth
puts Qwen3.6-35B-A3B at ~23 GB RAM+VRAM at 4-bit. The PC has 8 GB VRAM and 32 GB RAM, so the PC-local brain could be
the same model as brain 1 when the server is busy or away. **No tok/s figure for this setup [unverified]**.
**Sketch:** a `cpu_moe_layers` argument in `local_runtime.LocalRuntime.arguments` next to `gpu_layers`, then a
`brain_benchmark` run. RPC (`--rpc`) to combine PC and server is documented as a fragile, insecure proof of concept:
do not build on it.

## 19. Parakeet in the ASR benchmark

Voice picked faster-whisper small.en after a 120-clip benchmark. Parakeet-TDT-0.6B-v3: CC-BY-4.0, Open ASR average
WER 6.34%, ~2 GB RAM (https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3); CPU speed via sherpa-onnx int8 is
**[unverified]**. Add it to the same 120-clip benchmark; switch only on a measured WER and latency win.

## 20. Fixed-camera Studio shots

The official Studio MCP's `screen_capture` takes an optional camera position and target
(https://create.roblox.com/docs/studio/mcp). Three or four fixed poses per build make "look" steps comparable across
attempts and across nights. Check Studio Lab v2/v3 (#277, #292) first; only propose if they still use whatever is on
screen.

## 21-23. Lower-ranked

- **GRPO** (Unsloth RL guide: ~5 GB for models <= 1.5B, >= 300 steps before reward rises) on narrow sub-skills with
  millisecond rewards (analyzer errors fixed, deprecated API replaced). Do item 4 first; GRPO without a working SFT
  baseline is unlikely to clear the gate.
- **Owner hooks** like Claude Code/Codex (PostToolUse, Stop). Valuable, but running owner scripts is new process
  execution and needs the policy/security review gate in `AGENTS.md`; items 2 and 14 cover the main use (auto lint)
  without it.
- **FIM / next-edit completion** (Zed accepts any llama.cpp `/v1/completions`, https://zed.dev/docs/ai/edit-prediction;
  `TorpedoSoftware/Luau-Qwen3-4B-FIM-v0.1`). STAR has no editor surface, so this only makes sense if one is added.

## Checked and left out

- Self-consistency / majority voting: rejected by STAR in favour of test-based selection (best-of-N, PR #270).
- Multi-agent fan-out for coding: Anthropic's research system used ~15x the tokens of chat
  (https://www.anthropic.com/engineering/multi-agent-research-system); at 8-10 tok/s that is prohibitive. STAR's
  read-only specialists already follow the "one writer" rule.
- Tool RAG / deferred tool search (RAG-MCP, arXiv 2505.03275: 13.6% -> 43.1% tool-selection accuracy): already
  proposed as `star_tool_search` in `docs/agents/chat-speed-20261013.md`; the evidence supports doing it.
- ACE playbooks (arXiv 2510.04618) and GEPA: already W6 and W12 of the self-improvement plan.
- Tree-sitter repo map and AST chunking: already P0/P1 in `STAR_CODE_SPEED_RESEARCH_20261011.md`.
  `polychromatist/tree-sitter-luau` (MIT) exists; test it on strict-typed files before relying on it.
- RPC across PC and server, EAGLE-3 and DSpark on CPU, DeepSeek-V4-Flash (13B active, too slow on CPU),
  GLM-4.7-Flash (weaker than the current brain on the card numbers).

## Sources (primary unless noted)

- llama.cpp: docs/speculative.md, docs/llguidance.md, docs/function-calling.md, tools/server/README.md; PRs #18471,
  #19164, #29924; issue #10374 (github.com/ggml-org/llama.cpp).
- Models: huggingface.co/Qwen/Qwen3.6-35B-A3B, /Qwen/Qwen3.8-27B, /Qwen/Qwen3.8-Flash-Next,
  /ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF, /JetBrains/Mellum2.1-12B-A2.5B-Thinking,
  /TorpedoSoftware/Luau-Devstral-24B-Instruct-v0.2; unsloth.ai/docs/models/qwen3.6.
- Agents: arXiv 2405.15793 (SWE-agent), 2407.01489 (Agentless), 2510.12487 (Diff-XYZ), 2510.13859, 2402.01030
  (CodeAct), 2505.03275 (RAG-MCP), 2510.04618 (ACE); aider.chat edit-format and repomap docs;
  anthropic.com/engineering (context engineering, advanced tool use, multi-agent research system).
- Training and evals: arXiv 2312.06585 (ReST-EM), 2203.14465 (STaR), 2411.00640 (error bars), 2508.13144 (Signal and
  Noise), 2107.03374 (pass@k); unsloth.ai requirements and RL guide; github.com/Roblox/open-eval;
  github.com/SWE-agent/mini-swe-agent.
- Roblox and tools: create.roblox.com/docs/studio/mcp, create.roblox.com/docs/assistant/guide,
  github.com/rojo-rbx/rojo/releases, github.com/lune-org/lune/releases, github.com/JohnnyMorganz/luau-lsp/releases,
  github.com/Roblox/luau/releases, agents.md, code.claude.com/docs (checkpointing, hooks), zed.dev/docs/ai/edit-prediction.
- Voice: huggingface.co/nvidia/parakeet-tdt-0.6b-v3, huggingface.co/hexgrad/Kokoro-82M.
