# STAR Fast Brain v0.9 candidate — research, architecture and acceptance

**Status:** PR candidate only; not benchmarked, Windows-verified, merged or released. Local weights remain Qwen/llama.cpp by default. Free API usage is limited and changes with provider policy. Do not promise STAR outperforms frontier closed models without matched evaluation results.

## Root-cause findings in v0.8.1

1. \`star/desktop_core.py\` always instantiated workspace tools or Studio MCP when configured, even for unrelated user questions. The simple chat path thus got tool definitions and full non-streamed completions.
2. \`star/agent.py\` streamed only if there were no tool definitions; agent mode had up to 12 sequential model calls with per-call 180s timeout, leaving the UI apparently hung for minutes. The new routing bypasses unneeded tools; Fast responses stream immediately, Agent stays multi-step and deliberately slower.
3. The local Qwen vision model is intended to fit consumer Windows PCs; its throughput depends strongly on GPU layers, RAM/VRAM, context tokens and cold starts. Replacing the UI cannot make a 7B-class local model equivalent to frontier server models.
4. \`star/react_shell.py\` handled failed model-chat probes inside a broad startup retry loop. Unsupported templates could be swallowed repeatedly. Startup now reports a verified template failure promptly.
5. \`star/comfy.py\` already offered a bounded local ComfyUI workflow runner but the React chat had no generation action. This candidate connects a specific configured API workflow to a safe inline preview.
6. \`star/orchestration.py\` defined dependency task plans but no active subagent executor. This candidate adds limited, read-only draft-delegation in **Agent**, not unrestricted autonomous tool execution.

## Providers researched (October 2026)

| Provider | Role | Cost/limits to disclose | Source |
| --- | --- | --- | --- |
| llama.cpp / LM Studio | Private default, local offline text/vision | No per-token API fee; user hardware/energy and model downloads | https://github.com/ggml-org/llama.cpp |
| GroqCloud | Fast first-token/throughput for hosted open-weight models | Free plan is rate limited per model; current limits must be checked against the console | https://console.groq.com/docs/rate-limits |
| OpenRouter | Free models, discovery, optional paid routing | Free accounts: 50 requests per day according to pricing page; actual quotas and model availability change | https://openrouter.ai/pricing |
| Gemini Developer API | Cloud model alternative, multimodal | Only certain models have free-tier access; tier/model/quota restrictions vary. Free tier usage may be used to improve products | https://ai.google.dev/gemini-api/docs/billing |
| Cerebras Inference | Very high-throughput hosted open-weight model inference | Advertised $5 promotional credit requires a payment method, expires, and is *not* an unlimited ongoing free plan | https://www.cerebras.ai/pricing |
| Hugging Face Inference Providers | Future alternative multi-provider router | Free users receive only $0.10 monthly credits (subject to change), not unlimited inference | https://huggingface.co/docs/inference-providers/pricing |
| Cloudflare Workers AI | Future scalable text/vision/image path | Free allocation 10,000 neurons/day; some models require billing | https://developers.cloudflare.com/workers-ai/platform/pricing/ |

**API compatibility:** This candidate uses documented fixed OpenAI-compatible URLs for Groq, OpenRouter, Gemini and Cerebras; no user-controlled arbitrary remote inference URLs and no transparent automatic off-device switch.

### Web search (requires an owner-provided key)

- Brave Search offers $5 in monthly free search credits; currently Search pricing is $5 per 1,000 requests. Activation may require a payment method. https://brave.com/search/api/
- Tavily currently advertises 1,000 free API credits per month without a credit card. Searches consume credits depending on depth/features. https://www.tavily.com/pricing
- STAR returns HTTPS URLs with titles and 1,050-character maximum untrusted snippets. Model responses should cite the matching URLs and never pretend the full site has been retrieved when only the excerpt was fetched.
- Auto and Fast support an **explicit Web toggle** for first-pass grounded search. Agent + Web additionally exposes a narrowly scoped \`star_web_search\` function for follow-up queries.
- No generic arbitrary URL fetch, private-account search or scraping bypass. User input and remote results cannot change agent permissions.

### Generated images

- Uses existing approved local ComfyUI API workflow export; user enters the workflow JSON path, local port (default 8188) and CLIPTextEncode prompt node ID.
- Only approved core ComfyUI nodes are permitted by \`star/comfy.py\`; third-party custom Python nodes are not silently installed or executed.
- Image generation is opt-in via the **Image** chat control; originals persist to the STAR data directory, never the installation tree.
- Preview is resized to max 960px and encoded into a WebP data URI for the trusted Qt WebChannel. No arbitrary \`file://\` paths are handed to React.
- Generating images requires appropriate local diffusion models, hardware and ComfyUI installation. It is not immediate/free cloud image inference.

### Real delegated analysis

- **Agent mode only:** up to two invocations with two or three bounded independent read-only subquestions.
- Uses the same model with separate system/user turns but **no tool list**, no Studio, filesystem, GitHub, shell, secrets or search access in subagents.
- Parallel hosted calls at most 2, local at most 1 (parallel GPU requests generally harm throughput). Supervising model must synthesize and verify.
- This is not an always-on autonomous agent fleet. Use deterministic \`TaskPlan\` dependency and ownership contracts before exposing state-changing subagent workflows.

## Performance plan and measurable acceptance

*Before merge*, instrument time-to-first-visible-token (TTFT), p50/p95 total chat latency, error rate, maximum busy time, model tokens/s, model calls/turn, GPU/RAM budget, actual web/search cost and source-citation completeness. Use at least 30 warm queries and 10 cold starts per profile across:
- Local small-talk: no Studio/Workspace/web schemas, <=1 model call, streaming visible.
- Local selected Workspace+Studio question: only authorized tools, proper tool-call IDs, no unsupported template/malformed roles.
- Cloud fast chat: no accidental retries after partial stream; explicit credential opt-in; 429/403/timeout returned clearly.
- Agent mode complex tasks: delegated tasks are tagged unverified; never permit self-executed code, write access or privilege escalation.
- Web research: confirm source URLs, cite actual results, protect against malicious search snippets, provider 429, missing credentials, malformed API output.
- ComfyUI image: confirms actual output exists in user directory, preview survives restart, original accessible, cancel/restart and malformed workflow handled.

**Performance targets (aspirational, not measurements):** warm hosted TTFT <2s p50 for simple chat; 95% of short chat requests finish <15s for healthy hosted provider; local speed reported by measured GPU profile rather than an unsupported universal target; zero "indefinite pending" task runs thanks to overall task budgets.

## Setup and privacy

1. Open **Settings → AI providers** and select **Local** (private) or a fixed hosted provider. Hosted inference sends prompt/context/media to that external API.
2. For hosted inference and web search, paste the provider key into the credential section, click **Save key**, choose a model, **Save settings**, then **Test actual response**. Secrets are stored with \`keyring\` in the OS credential vault, or read from documented environment variables.
3. In Chat, **Fast** bypasses all tools, **Auto** enables tools only for explicit project-edit/inspect intents, and **Agent** makes the scoped local tools and optional read-only delegation available. **Web** is opt-in and needs Brave or Tavily; **Image** uses ComfyUI.
4. Existing conversations, checkpoints, reviewed project knowledge, references, models and updater files remain in the user data directory. Installing a new version must not erase them.
5. GitHub access remains via separately approved GitHub App installation tokens and review-gated draft PRs. Do not give model code unchecked ability to force-push, manage credentials, change branch protection, merge itself, rewrite evaluation cases or auto-publish Roblox places.

## Stop and GitHub source intelligence

- Active chat requests now use an explicit **Stop** control. The desktop sends a \`cancelMessage\` request, sets a local cancellation event and the async model task cancels during its next <=150ms poll. ComfyUI local image generation stops polling at the next step; its already enqueued generation **may keep running** in ComfyUI, so cancellation is not a remote queue deletion.
- Warm text-chat task budgets: up to 55s for configured hosted providers and up to 85s for slow local inference (including initial model load); complicated Auto remains 180s and explicit Agent 480s. These are limits, not latency promises.
- In explicit **Agent + GitHub** mode the model can request **read-only** source file lists and content from the **public \`oncoursemail/Star-AI\` repository at main**, not from this unmerged feature branch. No GitHub API credentials are exposed to the model, and no arbitrary repository URLs, secret files, write, force push, merge, or release actions are available through these tools.
- GitHub App branch/PR authoring exists separately in \`star/github_app.py\` and requires owner setup and limited installation permissions. Source-reading does **not** grant autonomous GitHub writes. Any future AI-proposed source edits must be made as isolated draft candidates, scanned/tested and independently reviewed.
- The currently open Obsidian/Graphify/Agent Skills PR #26 overlaps with this branch. Feature integration must retain existing memory, UI permission checks and the conservative skill execution boundaries.


## Known limitations and release blockers

- No access to private cloud accounts without owner credentials; no model/API keys bundled in public builds.
- No self-modifying base model weights, learned frontier intelligence, or automatic knowledge promotion without review and evidence.
- Free models vary in vision/tool-calling capability; some backends reject OpenAI-compatible tool schemas or token parameters.
- Agent tool-turn output is still non-streaming for protocol safety; ordinary Fast/Auto no-tool turns stream. A separate robust streamed-function-call parser is future work.
- No live GPU, Windows installer/updater, credential manager or ComfyUI tests performed in this drafting environment.
- Open draft PR #26 modifies overlapping files for Obsidian/Graphify/Agent Skills; resolve by deliberate rebase/review rather than overwriting changes.
- The GitHub Pages and public Windows download version must be checked after shipping; a PR is not a release.
