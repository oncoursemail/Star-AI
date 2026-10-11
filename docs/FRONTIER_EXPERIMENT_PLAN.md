# STAR Frontier Lab — First reproducible experiments

**Status:** experimental designs. Local policy code and tests exist; real Roblox fixtures are **not yet implemented**. Run only on a disposable Roblox Studio place.

## E1: Model + hardware audit

Goal: select the best **measured** local inference configuration for Windows 11 / RTX 3060 Ti 8 GB / RAM 32 GB.

Keep the exact same ten input prompts. Include one image with tiny UI text, one long-project code query, one malformed tool-call challenge, a simple Luau fix, and a remote-security design task. Try a Qwen3.5 4B GGUF quant first, then another verified available candidate. Test approximately 4K, 8K and 16K context where the hardware allows; never infer token capacity from model catalog context max. Collect:

* Installed model ID and quantization checksum
* VRAM peak (e.g. NVIDIA tools) and peak process/system RAM
* Prompt/prefill rate, decode rate, and total wall-clock time
* Tool-call schema compliance and final task correctness
* Number of crashes/OOM, load/unload time, and required CPU offload

**Comparison:** success and time per task, not merely raw tokens/sec. **Hard fail:** incorrect Studio target, invalid permission request, corrupt final output, unsupported visual conclusion. **Unknown until executed:** model winner and achievable runtime context.

## E2: Reference-to-native-GUI test

Inputs: five user-owned/approved interface reference images and independent descriptions of intended behavior. Build disposable places with empty `StarterGui` except protected seed fixtures. Save the original reference hashes. Give one condition images only and another both images and instrumented tree/rect data, each with equal budgets. Require:

* Native `ScreenGui` descendants with working `GuiButtons`, proper controllers and interaction states
* Style tokens shared across components, no one-image fake GUI
* No overlap of independently designated text and icon regions
* Device Simulator screenshots of desktop and target mobile/console modes
* Same-state visual comparison plus actual `AbsolutePosition`/`AbsoluteSize` telemetry
* No change to protected controls or unrelated game logic

Run at least three independent seeds. Produce explicit error types and linked screenshots. **Success is unknown before Studio execution.**

## E3: Adversarial Luau validator

Create a miniature owned server-authoritative inventory test place with deterministic fixtures. Request implementation of purchases, equip/unequip and persistence fallback; run simple valid behaviors first. Freeze candidate patch before creating fresh tests. Independently generate malformed values, duplicate remote calls, rapid requests, delayed acknowledgments, player departure mid-operation, and denied permissions. Count confirmed invariant violations and time-to-repair. Blind initial hidden tests from coding worker. No real player currency or production databases.

## E4: Animation/rig truth test

Inputs: an owned, fixed R6 rig, an approved action reference with motion frames, and a handheld asset with known attachment transforms. Ask STAR to produce a wave, turn, and idle transition. Compare only against in-engine captured animation plus rig metadata. Do not use the generated video's apparent movement as proof of an editable animation. Store:

* Skeleton and rest-pose identifiers
* Keyframe/clip asset evidence
* Hold-grip displacement statistics during turns
* Transition and loop motion discontinuity
* Marker-to-sound delay and interruption behavior
* Multiview screenshots/video at normal playback speed

This is a **future fixture** until STAR implements a real animation authoring adapter.

## E5: Compaction and project truth

Create two unrelated sample Roblox projects with conflicting approved colors, characters, rigs and game rules. In a long synthetic task, approve a UI change, then reject a later suggestion; force compaction. Reopen after simulated process restart. Ask for exact decisions and source image hashes, then modify another project's unrelated design. Reject on cross-project memory leaks, superseded facts presented as current, missing original files, or duplicate replayed mutations.

## E6: Candidate selection with existing code

`star/frontier_lab.py` accepts externally supplied *trial results* and compares baseline with candidate on matched, held-out, repeated cases. It is designed to stop candidate promotion when:

* The holdout results are missing or unpaired
* A candidate result has a hard failure
* A trial was blocked or never executed
* The measured pass rate is not above baseline
* A holdout task the baseline passed fails on every repeat for the candidate (a regression vetoes even when other tasks improved; a failure that passes on its repeat is reported as flaky and counts against the net). This verdict is not a copy: the module hands the holdout trials to the evaluation gate itself (`star/eval_gate.py`, `gate_change`; the recorded repeats are the gate's confirming re-run) and reports its answer under `gate`. When the gate gives no verdict (a blocked trial, nothing paired) the candidate is not promoted either
* Fewer than 5 net task wins: tasks the baseline failed on every repeat and the candidate passed on every repeat, minus tasks that got worse. The gate only says "no worse"; this floor is the module's own rule on top of it, because a higher pass rate alone (one flipped task) is not evidence. The floor of 5 can be raised with `--min-net-wins`, never lowered
* The candidate is much slower than baseline under the configured threshold

To run the module on a **real** dataset (after writing the trusted runner):

```powershell
py -m star.frontier_lab .\trusted_trial_results.json --baseline star-baseline --candidate star-candidate
```

Result is always *provisional* `candidate_for_independent_review` or `do_not_promote`. The module does not execute Roblox, validate screenshot evidence, or cryptographically verify evaluator identities. It is not a complete release gate.

## Experiment logging and promotion checklist

* Collect `base_commit`, `candidate_commit`, `fixture_revision`, `runner_version`, `project_id`, `studio_id`, `device_profile`, `media_hashes`, `model_id`, `quant_checksum`, `context`, `seed`, `tool_budget`, `peak_vram`, `seconds`, `verdict`, `evidence_path/hash`.
* Keep fixtures in a trusted location with separate write permission. No testing agent or self-builder may modify or choose which hidden test is required.
* Separate `development` and `holdout` datasets by project or problem family, with hidden holdout withheld from candidate generation.
* Use paired tests across equal conditions. If outcomes are noisy, run more trials and report uncertainty; do not report a single run as statistically meaningful.
* Hard failures never average out. User approval remains required for aesthetic direction and material external publishing.
* Save negative results and failure explanations. A failed experiment can improve the scientific process, but is not evidence that the candidate became stronger.
