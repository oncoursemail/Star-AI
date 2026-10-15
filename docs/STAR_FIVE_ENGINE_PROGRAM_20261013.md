# STAR Five-Engine Intelligence Program — self-play, skill evolution, verified learning

**Research and implementation checkpoint: October 13, 2026.**
**Status: draft PR #275. No automated release, model installation, public Roblox publication, or GPU fine-tuning was performed in this work.**
The program's objective is **independently verified successful creator tasks per hour**, while controlling hardware usage, data rights, regressions and user permissions. It is not a claim that STAR has solved arbitrary game development or become a frontier foundation model.

## Existing pieces — do not duplicate or confuse draft with shipped

| Requested engine | Status at this checkpoint | Boundary |
| --- | --- | --- |
| 1. Generate, test, select | Draft [PR #270](https://github.com/oncoursemail/Star-AI/pull/270): opt-in 2–8 candidates, Luau/static/mock sandbox grading, fallback repair, progress events | Not a guarantee that winner works in a real Studio place or for multiplayer |
| 2. RAM/KV knowledge banks | Draft [PR #274](https://github.com/oncoursemail/Star-AI/pull/274): opt-in save/restore of existing llama.cpp warm-up prefix | Does not preload complete Roblox docs. KV restore may be broken on certain llama.cpp builds |
| 3. Self-play game builder | Draft [PR #268](https://github.com/oncoursemail/Star-AI/pull/268): guarded Studio plan/apply/look/robot physics test/fix loop. **This PR #275** adds bounded seeded curricula, approved campaigns and a durable uncertain-run ledger | Only owner-approved pinned disposable Studio test place; no unattended publication |
| 4. Evolvable skills | Existing [star/frontier_lab.py](https://github.com/oncoursemail/Star-AI/blob/star/next/star/frontier_lab.py) and [star/eval_gate.py](https://github.com/oncoursemail/Star-AI/blob/star/next/star/eval_gate.py). **This PR #275** adds development-feedback mutation, sealed holdout comparison, candidate-only proposal | No model access to hidden test contents, evaluation code or automatic skill promotion |
| 5. Learn from verified wins | Existing draft [PR #148](https://github.com/oncoursemail/Star-AI/pull/148) generates curated examples, and existing GPU embedding trainer is a different task. **This PR #275** adds rights/evidence-filtered SFT data and a separately approved offline-only small-Qwen QLoRA runner | A test pass does not prove licensing or originality; trained adapters remain candidates pending independent tests |

### Why this architecture

The CodeT research paper (https://arxiv.org/abs/2207.10397) supports sampling multiple code solutions and ranking them using generated tests and agreement. But generated tests can share a blind spot with generated code. STAR must distinguish:

- **compiles**: Luau syntax/parser passed;
- **sandbox tested**: independent checks ran in a safe executable sandbox, but not Roblox's full engine;
- **Studio tested**: a pinned, authorized Roblox Studio test ran with real gameplay physics, read-back and event receipts;
- **visually reviewed**: screenshots/rendering/animation are inspected independently, not merely saved;
- **safe, rights-approved**: operator and license review permit learning from the code.

The final answer must show the *highest actually reached level*, and if all candidates fail it should say no passing implementation was verified, not display a fabricated perfect answer.

GEPA (https://github.com/gepa-ai/gepa) and DSPy (https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/GEPA/overview.md) demonstrate reflective mutation based on detailed feedback and a Pareto/validation search. Google's AlphaEvolve (https://deepmind.google/blog/alphaevolve-impact/) illustrates code search guided by programmatic evaluators. Their published improvements are not STAR-specific speed or correctness benchmarks. The module here reuses STAR's existing held-out gate instead of installing a separate optimizer or letting a model invent its score.

## Engine 3: bounded self-play curriculum

File: star/selfplay_curriculum.py. This is a **real deterministic offline course generator** producing small playable-style Studio Lab specs, not arbitrary large games. Three difficulty levels vary routes, platform heights and possible jump-clearance blockers. Every map must pass STAR's existing map-plan static preflight before execution.

Owner preview (no model inference and no Studio connection):

    python -m star.selfplay_curriculum preview --project STAR --rounds 3 --seed 12 --difficulty 2

Once separate Studio Lab PR #268 has been integrated, the owner may run a bounded campaign using STAR's existing pinned test-place configuration:

    python -m star.selfplay_curriculum run --project STAR --rounds 3 --seed 12 --difficulty 2 --home "PRIVATE_STAR_APP_DATA" --i-approve-studio-test-place

Without the installed Studio Lab adapter, a run returns unavailable rather than impersonating Studio. Only Studio Lab's guarded connector may edit the selected disposable place. A campaign never publishes a public game or changes another user's place. It caps rounds (6), fix iterations (5) and play time (150 seconds per iteration). A private SQLite ledger prevents overlapping/uncertain replays on one target and limits to four campaigns per target over a rolling day. If the remote run times out, mark it unknown and require human inspection before continuing.

The trusted runtime proof requires the exact approved place ID, a successful Studio read-back, a full build hash, a completed robot probe, stopped playtest and zero console errors. Screenshot hashes provide evidence that images were captured, but **do not** imply human quality review. A test-injected fake runner is labelled simulated and cannot claim Studio verification or produce trusted learning candidates.

Unknown run acknowledgement, **only after independently checking Studio state**:

    python -m star.selfplay_curriculum acknowledge-unknown --home "PRIVATE_STAR_APP_DATA" --campaign 12 --i-reviewed-the-studio-state

A campaign result may become a review candidate in the next learning step. This module never promotes a lesson or trains weights by itself. As the next step, increase curriculum variety to UI, animations, round systems, remote events and multiplayer, each with an actual engine-specific test harness and quality acceptance, not only physics obbies.

Roblox documentation establishes separate plugin-restricted StudioTestService modes and up to eight simulated clients:
https://create.roblox.com/docs/reference/engine/classes/StudioTestService
Single-client built-in MCP playtests are not a full multiplayer acceptance test.

## Engine 4: reflective skill evolution

File: star/skill_evolution_lab.py. The trusted application supplies three callbacks:

1. A candidate-mutating model reads only the current skill and diagnostic **development** feedback.
2. A development grader returns executed test counts, hard failures and a bounded feedback summary.
3. After all mutations are frozen, an independent sealed holdout evaluator runs baseline and candidate under the same frozen cases/repeats.

Candidates are restricted to docs/skills/*.md, with size and secret/policy-injection checks; no edits are made here. The evaluator consumes existing star.frontier_lab.Trial records and the real star.eval_gate verdict; at least five net held-out task wins across paired repeats are needed. It requires separate approval even after a favorable verdict. No skill text is committed, deployed, auto-merged or loaded into live model prompts by this component.

A model cannot lower the threshold, edit the grading logic, see sealed holdout inputs, or promote an unsupported skill. The host must attest that trials came from the true independent runner; a JSON dictionary saying "pass" is insufficient.

A practical follow-up is to connect this candidate interface to the existing host-owned night-school evaluator while preserving the protected grader and hidden corpus outside the model workspace. Compare with a frozen prompt baseline and measure p50/p95 latency, safety failures and verified success count before accepting anything.

## Engine 5: verified learning, rights and offline QLoRA

Files: star/verified_training.py and star/lora_training_job.py.

Before an example enters a proposed training dataset, the owner and independent evaluation host must establish:

- **provenance**: original user-authored or STAR-generated content with a reviewed license and model identity;
- **consent**: permission to train on that project's prompt and answer, not merely permission to use them in chat;
- **actual test evidence**: separate exact answer SHA-256, runner ID, immutable suite/artifact references, at least one executed test, zero failed tests and a trusted completed result;
- **no test contamination**: separate frozen holdout project/question fingerprints and a suite ID that cannot reappear as the training suite; duplicate prompts excluded across projects;
- **project-disjoint splits**: all examples from one project remain in one partition, never split randomly across train/validation/test.

The curator rejects records that lack a trusted host-owned receipt. A model-generated string claiming success is not an acceptable source. Rights review is **mandatory even if STAR itself generated the text**: prompts, source references and generated fragments may contain third-party intellectual property, confidential material or license restrictions. Developer/model terms must also be checked.

An explicitly authorized private export stores only the approved train, validation and test JSONL files under STAR's private training/verified directory, plus hashed manifest metadata. No dataset or weights are committed to the public GitHub repository. Training is not started automatically.

The optional QLoRA pilot is deliberately **not** part of normal STAR desktop dependencies. The operator separately installs compatible CUDA, PyTorch, TRL, PEFT, Transformers, Datasets and bitsandbytes into a dedicated, trusted GPU environment. It only accepts an owner-installed local SafeTensors base model in the explicitly supported small-Qwen architecture family, with disabled remote code and local-only model loading. It validates each exact approved dataset SHA-256 before GPU admission.

Owner preflight, **no GPU libraries loaded**:

    python -m star.lora_training_job --home "PRIVATE_STAR_APP_DATA" --local-model "TRUSTED_LOCAL_SMALL_QWEN_MODEL_FOLDER"

Owner-triggered run (not a scheduled overnight process):

    python -m star.lora_training_job --home "PRIVATE_STAR_APP_DATA" --local-model "TRUSTED_LOCAL_SMALL_QWEN_MODEL_FOLDER" --run --i-approve-training

The default small-GPU pilot uses 4-bit NF4 base quantization, a bounded LoRA rank, one epoch, a capped sequence length and gradient accumulation; actual memory use depends on the specific model and CUDA stack. Its output is **an unactivated adapter candidate**, requiring separate held-out Luau, Studio and latency comparisons before STAR is permitted to use it. QLoRA on 8 GB VRAM is a candidate feasibility target, not a guarantee.

Hugging Face TRL's current [PEFT integration](https://huggingface.co/docs/trl/peft_integration) documents LoRA/QLoRA with SFTTrainer; API/library versions should be pinned and validated on the target GPU first. The existing GPU embedding fine-tune is for retrieval quality and **not** this code-generation adapter.

## Engine 2: KV and CAG verification priority

The native prompt prefix and warmup already work without saved file banks. The additional persistent snapshot prototype is default-off in [PR #274](https://github.com/oncoursemail/Star-AI/pull/274). Do not allocate "80 GB" as an assumed spare resource or preload every Roblox document into context. The model's true maximum context, tokenizer/template and GPU/RAM constraints are independent of server free memory.

Recent llama.cpp issues report successful saved-state restore responses that do **not** yield cache reuse on some hybrid/recurrent or Qwen configurations. Verify the subsequent request's real cache_n and prompt evaluation time before adopting any restored snapshot:
https://github.com/ggml-org/llama.cpp/issues/25913
https://github.com/ggml-org/llama.cpp/issues/26676

A future content-addressed bank requires reviewed version-pinned doc subsets, hashes, stable system/context formatting, per-project access boundaries, citation provenance, TTL and invalidation when source docs change. The current code is not that full feature. Prompt bank save/restore itself does not improve generation accuracy unless the retrieved/preloaded evidence is correct and relevant.

## Quality gates for all five engines

1. **Functional**: Luau compilation, protected server-side behavior, API checks and actual Studio/playback/camera evidence appropriate to the requested capability.
2. **Evaluation**: frozen independent hidden tasks, versioned baseline, repeated paired trials, no scorer edits, no regression or score inflation.
3. **Performance**: actual hardware p50/p95 first-token and total completion, verified successful tasks/hour, GPU/VRAM/CPU/power use. Increasing candidate count may be slower if the server has fewer free inference slots.
4. **Trust**: no unapproved model downloads, project crossings, remote public exposure, privilege growth, leaking other users' data, hidden promotions or automatic publication.
5. **Learning**: accepted lessons and LoRA adapters retain exact provenance, owner consent, expiry/revert controls and regression evidence; only an independent gate can activate an improved strategy.

### Work still not implemented here

- No claim of a measured STAR coding improvement or successful all-day self-play, and no promise of continuously running work without a real operator-approved scheduler and machine access.
- No guaranteed general gameplay generation beyond the initial authored obby curriculum.
- No Studio Lab code copied into this branch: use separate reviewed PR #268.
- No live GEPA/DSPy package invocation; the candidate proposal/referee interfaces make that integration possible later.
- No nightly GPU service installation and no actual fine-tune execution or deployment.

Research basis: CodeT (https://arxiv.org/abs/2207.10397), Self-Refine (https://arxiv.org/abs/2303.17651), GEPA (https://github.com/gepa-ai/gepa), AlphaEvolve (https://deepmind.google/blog/alphaevolve-impact/), Roblox StudioTestService (https://create.roblox.com/docs/reference/engine/classes/StudioTestService), llama.cpp slot caching (https://github.com/ggml-org/llama.cpp/discussions/13606) and Hugging Face TRL/PEFT (https://huggingface.co/docs/trl/peft_integration).

**Definition of success:** an accepted, reviewed set of components proven on the owner's actual STAR installation, not just a green prototype CI run.
