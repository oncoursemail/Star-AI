# Luau lint rule matrix and measured limitations

## Scope

`star/luau_lint.py` has **12 distinct baseline rule IDs** discovered by
the new test from the AST of the real `add(...)` call sites. The prior
`tests/test_luau_lint.py` already had one firing and one clean
example per ID: **0 of 12 completely untested**, but **12 of 12 lacked two
independent cases with enforced line, severity and nonempty suggested fix**.
The new matrix adds **24 firing** and **24 clean** cases. Its coverage assertion
fails if an ID is added or removed without updating the matrix.

| Rule | Original firing/clean examples | New firing/clean examples |
| --- | ---: | ---: |
| deprecated-task-global | 1 / 1 | 2 / 2 |
| instance-parent-argument | 1 / 1 | 2 / 2 |
| service-property | 1 / 1 | 2 / 2 |
| humanoid-load-animation | 1 / 1 | 2 / 2 |
| datastore-unprotected | 1 / 1 | 2 / 2 |
| unchecked-find-child | 1 / 1 | 2 / 2 |
| loop-without-yield | 1 / 1 | 2 / 2 |
| loop-connection | 1 / 1 | 2 / 2 |
| mixed-client-server | 1 / 1 | 2 / 2 |
| datastore-read-set | 1 / 1 | 2 / 2 |
| touched-debounce | 1 / 1 | 2 / 2 |
| remote-unvalidated | 1 / 1 | 2 / 2 |

## Gaps from source review

| Kind | Count | Witness | Resolution or limitation |
| --- | ---: | --- | --- |
| False positives | 2 | A local function called `wait` and a harmless `print(target)` in a remote callback were flagged | Targeted guards distinguish local shadowing and target mutation from passive reads; real `lint()` negatives test both |
| False negatives | 1 | A `for` loop's counter assignment masked an unowned `Touched:Connect` call | Ignore distant loop-counter assignments for the connection-ownership heuristic; real `lint()` matrix asserts the hit |
| Baseline missing-rule coverage | 0 | All 12 IDs had one positive and one negative | Added 2x matrix and static AST ID-set guard |
| Baseline cases lacking precise diagnostics | 12 rule IDs | Prior table only compared membership | All matrix positives require exact line, rule ID, severity and nonempty suggestion |
| Remaining observed false negatives | 0 in the curated cases after repair | 24 independent firing snippets | These are illustrative syntactic patterns, not exhaustive proof |
| Fundamental approximation | Not counted as measured defect | Aliasing, dynamic calls, branches and receiver types | Needs native Luau analysis or Studio verification; no automatic correctness claim |

The matrix also exercises line/block comments, quoted/long strings, a shadowed
local function, methods on other objects, CRLF source locations, empty and
non-string input, external analyzer enable/disable, opt-in safety and
server-security modes, and a 50,000-character single identifier with a
bounded token-match count rather than timing thresholds.

`luau_safety` and `luau_server_security` have their own
opt-in suites; the 12-ID baseline matrix deliberately does not treat those
separate modules' conditional findings as always-on rules. A passing
Python unit test is static pattern evidence, not proof of Roblox Studio API
behavior, game safety or source type-correctness. No Lua/Roblox execution,
network call, GPU, new dependency, protected evaluation edit or rule expansion
is involved.

## Approach comparison

| Option | Licence / monetary cost | Upkeep | Decision |
| --- | --- | --- | --- |
| Native Python `pytest` matrix over existing STAR tokenizer | Python PSF-2.0 and existing pytest dependencies, zero added cost | A small row per new rule | Selected: proves real lint path and diagnostics without tooling changes |
| Official Luau CLI/analyzer | MIT, free | Pinned binary versions and setup; different rule taxonomy | Useful additional correctness check, not a substitute for these heuristic contracts |
| Selene | MPL-2.0, free | Separate binary and Roblox rule configuration | Complementary linting, not equivalent to STAR's existing rules |

Test execution is through PR GitHub Actions, not a local test or Roblox Studio run.
