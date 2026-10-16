# Run and repair standalone Luau (draft design)

This is an extension to the opt-in, server-only Luau sandbox from PR #145. The
replacement branch is based on today's `star/next`; **no execution is enabled
by default**. Both the desktop owner setting and the independent server operator
flag are required. The model must never select the server address, credentials,
VM binary, timeout, or environment.

## Answer path

1. `star.desktop_core.run_task` passes the owner setting to
   `star.doc_grounding.finalize` after the model has produced an answer.
   With the setting disabled, the exact old prompt, stream behavior, answer,
   messages, and archive paths are left unchanged.
2. The existing `review_luau` static compilation/typecheck and optional static
   repair run first. The opt-in runtime stage then takes **only the first closed,
   exactly labelled pure Lua/Luau code fence**, before the answer is saved or
   streamed to the user. Token streaming is withheld only when opted in.
3. A separate background model call writes **2–4 deterministic assertions** for
   `result` (the returned first value of the Luau module); no untrusted model
   source is permitted to choose what will execute outside the sandbox. Tests
   are parsed and bounded, and never persisted in the answer. This is fallible:
   the model may test the wrong behavior. A green verdict is not proof of
   correctness against the owner's actual requirements.
4. The existing authenticated `KnowledgeClient.luau_run(code, tests=...)`
   sends code and tests to the separately enabled server sandbox. Missing
   runner, invalid response, deadline expiration or absent VM is **skipped /
   unavailable**, never claimed as a pass. The original answer is kept.
5. If assertions fail without a timeout/resource/output limit, the model receives
   only the original request, candidate code and **bounded failure locations and
   error categories**, not raw untrusted stdout or arbitrary diagnostic text.
   At most **two** repairs are attempted; each candidate must pass the original
   static check if that check is available, and the **same assertions** must pass
   on a fresh standalone VM run before it replaces the fenced code. A failed
   repair is never silently shipped as verified.
6. Append a narrowly scoped review note and saved nonsecret run metadata;
   never describe pure-VM checks as verified Roblox engine behavior.

## Limits and trust boundaries

- One code block; at most three VM attempts (initial + two repairs); 2–4
  independent `assert(result...)` lines; tests capped at 2,000 UTF-8 bytes,
  code plus tests <= 65,536 bytes and without NULs; no rewriting non-Luau prose.
- One VM call at a time; each request uses 3 s execution, 256 MiB, 64 KiB output,
  <= 15 s HTTP transport, shared <= 40 s review budget with a >= 10 s save
  reserve. A timed-out HTTP worker is **never retried**.
- Server requires explicit `STAR_KB_LUAU_RUN=1`, Linux, an installed standalone
  Luau binary, non-root user and `prlimit`. No server or key is contacted in
  tests. The inherited PR #145 security warning remains: resource limits alone
  are **not** a native-code isolation boundary; deploy inside the existing
  unprivileged isolated container only.
- The night-school scorer already handles `auto.unit_test`, and its
  `LocalSandbox` uses the same standalone VM, under resource limits. We reuse
  the **test-body convention and result binding**, not its SSH/client machinery.
  There is no reusable Roblox-engine emulator in the checked-in night-school
  pool: the default prelude is empty. We do **not** invent a second set of
  `Instance`, `game`, `DataStore`, `CFrame` or service stand-ins. This
  first version tests pure Luau arithmetic/table-returning modules only; physics,
  Studio state, network remotes, timing, persistence, engine APIs, replication,
  real class identity and animations **cannot be simulated**.
- The language runtime has an allowlisted environment; tests are a separate
  `loadstring` chunk and see `result` plus copied standard builtins. Runtime
  output is untrusted and never placed in a model prompt or stored as a lesson.

## Existing-tool comparison

| Option | License | Upkeep | Runtime cost | Decision |
|---|---|---|---|---|
| Existing STAR night-school scorer + PR #145 Luau sandbox | Repository license and Luau MIT | Reuse maintained scorer, review sandbox integration | No new provider; existing operator VM/CPU | **Chosen** |
| Standalone Lune interpreter | MIT | Separate sandbox/compatibility audit and version maintenance | Additional binary/CPU | Not adopted |
| Pure Python fake checker | PSF-2.0 | Low but cannot observe actual Luau semantics | Minimal CPU | Used only for offline deterministic regression tests |

## Proof and measurement

Automated tests cover the real `finalize` path, the default-off identity,
no-VM skip, invalid assertions, bounded attempts, correct unchanged code,
timeouts, and error-free code replacement. Ten original, non-golden pure Luau
wrong-logic practice scenarios use a deterministic **fake VM**, with paired
known-wrong and known-correct variants; the reported table distinguishes
simulated detection/repair from actual Luau execution. Real VM end-to-end
containment and model-generated assertions require a separate explicitly
authorized isolated-server verification before owner enablement. No change to
golden/holdout suites, night-school enrollment or runtime defaults.
