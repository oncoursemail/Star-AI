# LLM-assisted decompilation — reverse-engineering case study (researched 2026-10-13)

From 2024 to 2026, research moved from "an LLM translates assembly to C" to "an LLM proposes and a verifier disposes." LLM4Decompile, Decompile-Bench, DecompileBench and Idioms measure whether output re-compiles and re-executes. Hands-on matching-decomp experiments show agents reach high match rates only inside tight compile-and-diff loops. Every source agrees that unverified LLM output is often wrong while looking right.

## 1. What it is and its 2026 state

- LLM4Decompile (EMNLP 2024, arXiv 2403.05286):
  - Open models from 1.3B to 33B parameters.
  - "End" models decompile binaries directly. "Ref" models refine Ghidra's pseudocode.
  - The paper says both beat GPT-4o and Ghidra by "over 100%" in re-executability rate, and that Ref improves on End by 16.2%.
- The GitHub README's model table lists re-executability as: 1.3B-v1.5 at 27.3%, 6.7B-v1.5 at 45.4%, 6.7B-v2 (Ref) at 52.7%, and 9B-v2 at 64.9%.
  - The table does not name the benchmark. The 9B figure is described as being on the "Decompile benchmark."
  - The arXiv abstract names HumanEval and ExeBench as its evaluation sets. The label "HumanEval-Decompile" is widely used for the HumanEval-based set, but neither fetched page uses it (unverified).
  - Later news items: decompile-bench (2025-05-20) and SK²Decompile (2025-10-04), a two-phase method that recovers structure and then names identifiers.
- Decompile-Bench (arXiv 2505.12668):
  - About 2M binary-source function pairs, distilled from 100M collected pairs (450 GB of binaries) from permissively licensed GitHub projects.
  - The eval set uses HumanEval, MBPP and post-2025 GitHub repositories to limit leakage.
  - The paper reports about 20% better re-executability after fine-tuning on it.
- DecompileBench (arXiv 2505.11340): 23,400 functions from 130 real programs, scored with runtime-aware validation plus LLM-as-judge readability. The paper finds LLM methods beat commercial decompilers on understandability but were "52.2% lower on functional correctness."
- Idioms (arXiv 2502.04536, CMU):
  - Predicts code and user-defined type definitions together, and introduces the Realtype benchmark.
  - The abstract reports 54.4% on ExeBench, against 46.3% for LLM4Decompile and 37.5% for Nova (a neural decompiler, not the NVIDIA driver).
- 2026: an ICML 2026 workshop paper frames matching decompilation as a "verifier-guided task." I found no peer-reviewed aggregate success rate.

## 2. How the original was reversed

- Training data comes from compiling permissive source at several optimisation levels and pairing each function's assembly or pseudocode with its source (LLM4Decompile, Decompile-Bench).
- There are two pipelines:
  - End-to-end: assembly to source.
  - Refinement: a classic decompiler (Ghidra) does control-flow and data-flow recovery, and the LLM cleans up names, types and idioms.
- Idioms argues that a function is "underspecified" without its struct definitions, so types must be predicted jointly with code.

## 3. Workflow: matching, non-matching or clean-room

- Non-matching (research benchmarks): success means the output compiles and passes the original function's tests. These are re-executability metrics.
- Matching (game decomp), Chris Lewis's Snowboard Kids 2 workflow:
  - A human picks functions. A script pulls a decomp.me scratch into a folder with a CLAUDE.md, and an agent loops: build, score 0-100%, read the asm diff, hypothesise, and write a new numbered attempt file.
  - decomp-permuter is used only near completion.
  - Simon Willison relays that after a switch to Claude Opus 4.5 with a `claude -p` loop over functions ranked easiest-first, the decomp.dev chart rose from about 25% to about 45% between mid-November and 2 December 2025.
- The "Mizuchi" benchmark (gambiconf Substack): 60 functions from Sonic Advance 3 (GBA) and Animal Forest (N64), using Claude Sonnet 4.6 with at most 12 attempts each.
  - The pipeline runs m2c, objdiff and the permuter before the AI phase.
  - The author reports a 74% average match rate, a best run of 80%, and 88% of functions with the same outcome across runs.
  - Nearly half of AI matches came on the first attempt. After the third attempt, the odds fell to about one in four.

## 4. Testing and verification

- The metrics differ in strength:
  - Re-compilability is the weakest.
  - Re-executability against tests is stronger.
  - Byte-identical object match is strongest, and only available when the original compiler and flags are known.
- Readability judged by an LLM (DecompileBench) is soft. Pair it with functional checks.
- Failure modes observed:
  - Arithmetic slips such as struct offsets.
  - C89 declaration-order mistakes.
  - Goto-heavy or deeply nested control flow.
  - Register allocation that the permuter brute-forces better (Lewis).
  - Resubmitting identical code 49 times, and claiming matches that did not exist when the agent lacked a diff tool (Mizuchi).
  - Permuter output at low match percentages being "implausible" code.

## 5. Structuring a large legacy codebase

- Lewis keeps context on demand: a per-function folder, a focused instruction file, and no repo-root runs (which burned tokens). He found RAG less useful with large context windows.
- Rank work by difficulty and do the low-hanging fruit first (`score_functions.py` in Willison's account; logistic-regression tiers in Mizuchi).
- The ICML harness adds setup diagnostics, run history and dashboards. It reports the matching prefix and first mismatch offset, and commits only changes that measurably improve the verifier.

## 6. Engine architecture insights

- Optimisation levels, inlining and complex build settings make binary-to-source mapping hard (Decompile-Bench). Models trained "without knowledge of optimization levels" were a separate LLM4Decompile variant.
- Composite types are where neural decompilers fail silently. Joint type prediction (Idioms) is the current answer.

## 7. Legal history and lessons

- The research datasets deliberately use permissively licensed source (Decompile-Bench). Benchmarks built on proprietary binaries would inherit licensing problems.
- Model and code licences: LLM4Decompile is "MIT and DeepSeek License" plus a separate model licence (README). Check before shipping weights.
- Decompiling a third-party binary still falls under the usual analysis: fair-use disassembly precedent (Sega v. Accolade) and 17 U.S.C. §1201(f) interoperability limits. LLM assistance changes none of that.

## 8. Transferable lessons for STAR

1. Never declare success without the oracle's output. Mizuchi's false "match" claims happened when the agent lacked a diff tool. STAR must run the compiler, tests or diff and quote the result, or say "not verified."
2. Use a bounded loop with stall detection. Cap attempts (about 3-12), detect duplicate submissions by hashing candidates, and change strategy or escalate to the human when the score stops improving.
3. Number and keep every attempt. Never overwrite the best candidate. Keep a scoreboard so regressions can be rolled back.
4. Choose the strongest available metric: byte or behaviour equality over "it compiles" over "it reads well."
5. Let deterministic tools go first. Run m2c, the permuter and type tooling before the LLM, and use the LLM for the parts tools cannot do: hypotheses, naming and idioms.
6. Ask for types with code. When reconstructing a module, emit the struct or type definitions it depends on. In Luau, return `export type` declarations alongside the function so `--!strict` can check them.
7. Roblox/Luau parallel: when "re-creating" behaviour of an old free-model script, write TestEZ or Jest-Lua specs from observed behaviour first (re-executability). Then let the model refactor until the specs pass.

## Sources

- [arXiv 2403.05286 — LLM4Decompile](https://arxiv.org/abs/2403.05286)
- [LLM4Decompile GitHub README](https://github.com/albertan017/LLM4Decompile)
- [arXiv 2505.12668 — Decompile-Bench](https://arxiv.org/abs/2505.12668)
- [arXiv 2505.11340 — DecompileBench](https://arxiv.org/abs/2505.11340)
- [arXiv 2502.04536 — Idioms](https://arxiv.org/abs/2502.04536v2)
- [Chris Lewis — Using coding agents to decompile N64 games](https://blog.chrislewis.au/using-coding-agents-to-decompile-nintendo-64-games/)
- [Simon Willison — one-shot decompilation note (Dec 2025)](https://simonwillison.net/2025/Dec/6/one-shot-decompilation/)
- [gambiconf — Can LLMs really do matching decompilation?](https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation)
- [ICML 2026 workshop — Matching Decompilation as a Verifier-Guided Task](https://icml.cc/virtual/2026/82758)
- [Wikipedia — Sega v. Accolade](https://en.wikipedia.org/wiki/Sega_v._Accolade)
