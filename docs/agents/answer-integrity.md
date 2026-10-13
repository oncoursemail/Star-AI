# Advisory answer-integrity detector

**Status: not wired into STAR's answer path; no change to defaults.** This is a pure, offline analysis helper in `star/answer_integrity.py`, returning structured issue codes, reasons and one-line repair instructions. It does not execute Luau or call a model.

## Evidence, and what the labels mean

- [The failure ledger](../FAILURE_LEDGER.md) classifies **13 failed attempts** as *self-check error left unrepaired* and **11** as *answer cut off* across repeated stored attempts. These are primary labels, not independently reviewed diagnoses or evidence of model intent.
- [Baseline NET-07](../../evals/results/baseline-v2.json#L1430) recorded a failed Luau diagnostic in `luau_check[1]`; a reported static error is not a successful self-check.
- [Creation baseline ANI-07](../../evals/results/baseline-creation-v1.json#L4) was a failed model/tool response with no usable code, illustrating why a truncated/nonanswer verdict is distinct from a Lua syntax defect.
- [Luau syntax](https://luau.org/syntax) documents control structures and comments; [Roblox Luau documentation](https://create.roblox.com/docs/luau) covers the language context. The detector recognizes only a bounded subset of this grammar.

A real recorded failure does not prove that a new heuristic would have caught the exact historic output. These functions detect only *observable output patterns* with independently tested positive/negative fixtures; no recall or precision benchmark has been measured. No holdout data was used.

## What the functions check

`inspect_answer(answer, *, self_check="", previous_code=None) -> IntegrityVerdict` reports zero or more `IntegrityIssue(code, reason, repair_instruction)` values, with `ok`, `reason`, and `repair_instruction` convenience properties.

1. **Unclosed Markdown fence:** reuses `star/code_answer_completion.py`'s existing fence-state logic, including run length. This detects a rendering/incomplete-answer risk, not missing Luau syntax.
2. **Unclosed Luau block:** lexes only labeled Lua/Luau fences (and obviously code-like unlabelled fences), using the existing `star/eval_checks.py:strip_luau(strings=True)` to skip comments, short/long quoted strings and backtick strings. A tiny keyword stack covers `function`, `if/elseif/else`, `for/do`, `while/do`, standalone `do`, `end` and `repeat/until`. It deliberately does **not** interpret a word in normal prose as Luau.
3. **Trailing sentence fragment:** conservative final-line connector/punctuation check; it does not mark an ordinary sentence missing a period as truncated.
4. **Self-check errors left unrepaired:** requires both a *positive error diagnostic* (e.g. failed assertion or error line) **and** a comparable `previous_code` snapshot. The final code must match after removing comments and trailing-space noise. With no snapshot, it **does not** invent an unchanged-code conclusion. A changed final code is not proof the error was fixed.

The one-line instructions tell an optional caller to finish the text, close a construct, or repair and rerun a failed self-check. They never mark an answer as having actually passed.

## Possible future integration (requires owner opt-in and evaluation gate)

The current `star/agent.py` assembly already uses opt-in `star/code_answer_completion.py` to request bounded continuations for responses ending in length/fence truncation; the final answer is subsequently processed and checked before presentation. A future owner-approved integration could invoke `inspect_answer` after the completion step and before finalization, with both the previous code snapshot and the model's genuine self-check result, then route detected issues into an existing bounded repair path. This PR **does not** add that call and must not turn any setting on. `star/eval_checks.py:looks_truncated` and `star/code_answer_completion.py:open_fence` remain the existing authoritative utilities for their own workflows.

## Limits and validation

- This is a lightweight lexer, **not** a full Luau parser. It may miss invalid tokens, syntax inside backtick interpolation, unbalanced parentheses, incomplete expressions or malformed type syntax. A balanced `end` structure is not proof of syntax validity.
- Heuristic trailing prose and self-check error-word detection have false positives/negatives, especially in mixed prose/code.
- Static checks cannot verify Roblox engine behavior, replication or a real **Roblox Studio** run. A repaired output must still be compiled, tested and, where relevant, exercised in Studio.
- Tests cover more than 25 missing/complete/negative-control cases, including strings, long strings, comments, fence size, snapshot absence, changed code, and unrepaired diagnostics. Those are authored assertions until GitHub checks execute them.
- No new source in `evals/` or changes to finalization, model routing, feature flags or CI workflows.
