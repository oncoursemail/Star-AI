# OpenGameEval: independent benchmark integration plan

Research snapshot: 2026-10-11. This is a plan, **not** a benchmark result. "Not stated" means the reviewed primary sources do not substantiate a claim.

## 1. Distribution, license and publication

- Primary announcement (2025-12-17): https://about.roblox.com/en-nz/newsroom/2025/12/opengameeval-benchmark-agentic-ai-assistants-roblox-studio
- Paper (posted 2026-10-01): https://arxiv.org/abs/2610.02563
- Source, task scripts, place files and plugin: https://github.com/Roblox/open-game-eval ; task directories `Evals/`, `DebugEvals/`, `Places/`, `EvalPlugin/`; runner `invoke_eval.py`.
- Instructions: https://github.com/Roblox/open-game-eval/blob/main/README.md ; releases: https://github.com/Roblox/open-game-eval/blob/main/EVAL_RELEASE_LOG.md
- License: MIT, including permission to use, modify and publish copies with the copyright and permission notice retained: https://github.com/Roblox/open-game-eval/blob/main/LICENSE.txt . This does **not** establish a license for Roblox Studio, third-party models, or their hosted services.
- The project publishes model comparisons openly. An explicit external-results submission/verification policy, permission to claim an *official* leaderboard placement, and restrictions on publishing independently measured results: **not stated**. Publish only reproducible, clearly labeled independent scores (task-set commit, number of attempts, model/version, configuration, failed jobs, date), never imply Roblox endorsement.

## 2. Running an evaluation

The README documents a **Roblox account** and **Open Cloud API key** with `studio-evaluations` / `create`, plus a **model-provider API key** when not in reference mode. It submits jobs to `https://apis.roblox.com/open-eval-api/v1/eval` and polls `/eval-records/{job_id}`. A local Roblox Studio installation is **not required by the documented remote CLI flow**; the framework evaluates in a Roblox-hosted Studio-like environment. The local `EvalPlugin/` exists for authoring/testing; exact requirements for running that plugin: consult its separate guide. Server OS: **not stated**. Client CLI uses Python/uv and supplies macOS/Linux installation instructions; a supported-OS matrix: **not stated**. CPU, GPU, memory and dedicated local hardware minimums: **not stated**.

The README says a typical job takes **3–4 minutes**, its quick start describes a **10-minute** timeout while current `invoke_eval.py` actually sets **900 seconds**; do not conflate typical duration with deadline. Max submit rate: **50/hour/key**, **100/day/key**, **100/day/IP**. Poll limit: **60/minute/key** and **60/minute/IP**. Concurrency can be bounded using `--max-concurrent`.

Counts refer to different editions: original announcement **47** curated tests, original code-generation batch **47** (release log), expanded leaderboard **87** core evals, plus **30** debugging evals, while the paper analyzes **84** human-curated core tasks and **16 attempts/task** across **13** frontier models. The April 2026 release log documents 40 further core tests. Categories in announcement: mechanics, environment building, animation, UI and sound; paper distinguishes script-authoring and scene-change tasks; debugging tasks are separate. Do not treat 84 and 87 as interchangeable.

## 3. Agent and model interface

The paper describes **eight** tools, categorized as **observation** versus **editing/action**. The names recorded in the project's detailed model reports are:

| Observation (read-only) | Action (mutating) |
| --- | --- |
| `search_game_tree` | `multi_edit` |
| `script_search` | `execute_luau` |
| `inspect_instance` | `insert_from_creator_store` |
| `script_grep` | |
| `script_read` | |

Source: https://github.com/Roblox/open-game-eval/blob/main/Detailed%20Reviews/Fable_report.md . The task annotation README mentions `game_tree`, which differs from report's `search_game_tree`; this **must not** be silently normalized into a callable schema.

The **documented client transport** is HTTP JSON for evaluation submission, *not* a public agent-tool bridge. Request uses `input_script`, `name`, `description`, and `custom_llm_info: {name, api_key, model_version, url}`. Supported provider names documented are `claude`, `gemini`, `openai`. The user prompt is represented inside a task's Lua `prompt` table as `{role = "user", content = "..."}`. Result polling returns `record.jobStatus` and `record.evalSucceeded`. Exact **internal model messages, tool-call envelope, argument schemas, response bodies, and call IDs** for all eight tools: **not stated in README or the examined published examples**. The tool-name list is not a wire protocol.

Crucially, README says `--llm-url` is **"Not yet supported"**; `invoke_eval.py` forwards the value but this does not prove the hosted evaluator uses it. **No:** arbitrary OpenAI-compatible endpoints, including a LAN llama.cpp server, **cannot be claimed supported**. Server-to-LAN reachability, callback authentication and a custom agent-loop injection hook: **not stated**. A `custom_llm_info.name = "openai"` selection describes Roblox's supported provider integration, not arbitrary endpoint interoperability.

## 4. Scoring and current public comparison

Tasks provide `setup`, optional reference, `check_scene` (edit), and `check_game` (play). Results list check passes/fails; a task passes **only when all checks pass**. `evalSucceeded` is the job's success verdict. Metrics: Pass@1 (one attempt), Pass@5 (any of five), Cons@5 (at least three of five), All@5 (all five); separately average tool error rate. An incomplete/errored run must not be silently counted as success.

The public [87-eval leaderboard](https://github.com/Roblox/open-game-eval/blob/main/LLM_LEADERBOARD.md), **read on 2026-10-11**, lists these core Pass@1 values: Claude Fable 5 **50.34%**, Claude Opus 4.6 **48.05%**, Gemini 3.5 Flash **48.05%**, Gemini 3 Flash Preview **47.82%**, Claude Opus 4.7 **43.45%**, GPT-5.5 (Reasoning: M) **40.69%**, GPT-5.4 (Reasoning: M) **40.23%**. Its lead entry has Pass@5 **62.07%**, Cons@5 **51.09%**, All@5 **39.52%**, average tool error **1.40%**. The leaderboard does **not state a measurement date** per entry. The paper's best reported single-attempt result **51.7%** belongs to its 84-task study, not the expanded leaderboard. Quote from benchmark README: **"The eval is considered as a pass only if all checks are passed."**

## 5. STAR implementation decision and minimum real measurement

STAR's `star/agent.py` implements a guarded, OpenAI-style tool-call loop using selected Studio tool catalogs and streamed responses. `docs/STAR_LOCAL_MCP.md` documents the in-process local MCP bridge, explicit Studio selection, guard policies, and refusal of uncontrolled input; `docs/ROBLOX_ACCESS.md` documents a separate saved-version cloud build/test route. Neither is a demonstrated substitute for Roblox's hosted evaluation's own per-task Studio session.

**Preferred first real measurement**: use the upstream `invoke_eval.py` as-is for one unmodified `Evals/001_make_cars_faster.lua` with a documented supported hosted-model provider and separately provisioned evaluation and model keys; record job ID, task commit, result, and elapsed time. This validates infrastructure, **not STAR**, and needs credentials and a live network; do not run in offline CI. Use the upstream `--use-reference-mode` separately to validate check operation, not model ability. Do not claim either as STAR's score.

To measure **STAR**, obtain and verify an upstream-supported model/agent integration contract, or negotiate a supported external agent harness with Roblox. Two distinct approaches: (A) model-only evaluation if the evaluator officially supports connecting to STAR's model endpoint; this measures its model, **not STAR's guarded tool loop**. (B) agent-level evaluation if the harness can invoke STAR's own loop in isolated disposable tasks with per-task Studio bindings, tool-schema translation, edit permissions and result provenance; this measures STAR but requires substantially more protocol and safety work. For both, build recorded fixtures and exhaustive mapping tests before exposing mutations. Never bypass STAR's guard or retrofit unsupported private endpoints.

**Adapter implementation decision: no `star/opengameeval_adapter.py` now.** The public examples checked document the evaluation job HTTP envelope and only illustrative tool-name annotations, **not recorded full eight-tool message/argument/result schemas nor a documented external agent callback**. Missing: versioned invocation/reply contract, argument schemas, internal tool-call IDs, initialization/session lifecycle, error conventions, mutation semantics, and supported injection mechanism. Implementing a purported correct tool-name translator would be guessing; therefore no adapter and no corresponding artificial unit tests. Documentation-only change needs no production behavior tests.

## 6. Validity, privacy, cost and terms

- **Leakage:** Public tasks, place files, examples and even human reference-related annotations permit training contamination; disclose dataset commit, whether a model could have seen tasks, and evaluate with held-out/private tasks when available. Do not optimize on disclosed checks and report it as independent generalization.
- **Cost:** Model API inference is billed under provider terms; Roblox evaluation service pricing, quota increases, GPU cost and Studio cloud-resource charges: **not stated** in checked documentation. Initial task cost is not zero merely because scripts are MIT licensed.
- **Credentials:** Keep Roblox and model API keys out of git, traces, log statements and CI fixture files. The upstream service receives the configured provider key in `custom_llm_info`; obtain owner consent before submission. Treat task text and Studio content as untrusted.
- **Restrictions:** Respect published API throttles; automated job submission is explicitly described in the README, but a complete service ToS, restrictions on automated volume beyond rate limits, eligibility for public leaderboard submissions and retention of submitted credentials or prompts: **not stated** in the checked benchmark materials. Review Roblox's current service terms and obtain permission before sustained automated testing; do not infer unrestricted access from MIT source licensing.

## Verification provenance

Read: upstream README, `invoke_eval.py`, `LICENSE.txt`, `LLM_LEADERBOARD.md`, paper abstract, official announcement and detailed model-report tool inventory; STAR `star/agent.py`, `docs/ROBLOX_ACCESS.md`, `docs/STAR_LOCAL_MCP.md`. No live job submitted, no external credentials used, and no model score measured in this work.
